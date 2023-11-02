#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

# TODO:
# * Command console
#  - Multiple tasks
#  - Job handler
# * Dict to pass parameters to running transaction task?!


import argparse
import asyncio
from datetime import datetime
import io
import queue
import random
import re
import socket
import sys
import time
from threading import Thread

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion, NestedCompleter

from stress_testing.stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue, single_request


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost:8080',
                        help='Host:Port to connect to.')
    parser.add_argument('--yaxis', type=int, default=300,
                    help='Y axis max value.')
    return parser.parse_args()


class DataQueue(queue.Queue):
    """
    DataQueue provides a FIFO type queue where, where the get
    method return all currently queued items in one chunk.
    It uses a socketpair to provide the synchronization needed
    to get the number of currently queued items.
    """
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        # It might be possible to use a diggre
        self.r, self.w = socket.socketpair()
        self.r.setblocking(False)
    def get(self, block=True, timeout=None):
        try:
            results = []
            data = self.r.recv(self.maxsize)
            for _ in data:
                results.append(super().get())
            return results
        except io.BlockingIOError:
            return []
    def put(self, item):
        super().put(item)
        self.w.send(b'.')
    def fileno(self):
        return self.r.fileno()


gargs = {
    'n_p': 20,
    'delay': 5000,
}
last_result = None
last_error = None
# TODO: Rename function, like sliding_window ...
async def stress_requests_stream(q, task, args):
    global close_flag, gargs, last_result, last_error
    tasks = set()

    await setup(args)

    try:
        # TODO: Cleanup function, more readable
        # Start initial n_p tasks
        for _ in range(0, gargs['n_p']):
            tasks.add(asyncio.create_task(task(**args)))

        while len(tasks)>0 and not close_flag:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                result = await d
                last_result = (datetime.now().isoformat(), result)
                if result[1] != 'ok':
                    last_error = last_result
                # Push results to graph_handler
                q.put(result)
            # Start new tasks, but no more than n_p in total.
            tasks_to_start = gargs['n_p']-len(pending)  # Calculate number of free task slots
            if tasks_to_start>0:
                for _ in range(0, tasks_to_start): # Start tasks in available slots
                    pending.add(asyncio.create_task(task(**args)))
            tasks = pending
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(e)

    await teardown(args)



async def job_model_a(args, rq):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
    })
    parameters.update(gargs)
    data = {
        'host': args.host,
        'op': 'update',
        'url': '/model-a:model-a/model-a:list=K<<id>>',
        'data': '''{
                    "list":{
                        "str-value":"Changed string data <<data>>"
                    }
                }''',
        'parameters': parameters
    }

    # Just run for a very long time...
    await stress_requests_stream(rq, default_task, data)


async def job_python_service_create(args, rq):
    parameters = Parameters({
        "id": SequenceRequest(0),
        "data": RandomValue(0, 4000000000),
        "delay": 0
    })
    parameters.update(gargs)
    data = {
        'host': args.host,
        'op': 'create',
        'url': '/python-service:python-service',
        'data': '''{
                    "service":{
                        "name":"K<<id>>",
                        "delay":<<delay>>,
                        "str-value":"String data <<id>>"
                    }
                }''',
        'parameters': parameters
    }

    # Just run for a very long time...
    await stress_requests_stream(rq, default_task, data)


async def job_python_service_delete(args, rq):
    parameters = Parameters({
        "id": SequenceRequest(0)
    })
    data = {
        'host': args.host,
        'op': 'delete',
        'url': '/python-service:python-service/python-service:service=K<<id>>',
        'parameters': parameters
    }

    # Just run for a very long time...
    await stress_requests_stream(rq, default_task, data)


jobs = {
    'model_a': job_model_a,
    'python_service_create': job_python_service_create,
    'python_service_delete': job_python_service_delete,
    'python_service_update': None, #job_model_update_python_service,
}

running_jobs = {}

class DictKeyCompleter(Completer):
    def __init__(self, d):
        self.d = d
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        for k in self.d.keys():
            if k.startswith(word):
                yield Completion(k, start_position=-len(word))


completer = NestedCompleter.from_nested_dict(
    {
        "start": set(jobs),
        "stop": DictKeyCompleter(running_jobs),
        "exit": None,
        "show": None,
        "set": {"n_p", "delay"},
        "show": None,
        "jobs": None,
        "last": None,
        "zoom": None,
        "clear": None,
        "help": None,
    }
)

async def command_handler(args, rq, cq):
    global close_flag, gargs
    req_task = None
    cmd_history = FileHistory(".sustain_graph")
    session = PromptSession("stress-tests> ", history=cmd_history)
    try:
        while not close_flag:
            cmdline = await session.prompt_async(
                    completer=completer,
                    complete_style=CompleteStyle.READLINE_LIKE)
            try:
                cmd, *cmdargs = re.split(r'\s+', cmdline.strip())
                if cmd in ['exit', 'quit', 'q']:
                    break
                elif cmd in ['h', 'help']:
                    print('Available commands:')
                    print('quit, q')
                    print('help, h')
                    print('start')
                    print('stop')
                    print('jobs')
                    print('show')
                    print('set')
                    print('zoom')
                    print('clear')
                    print('last')

                elif cmd == 'start':
                    if not cmdargs:
                        print("Available jobs:")
                        for name in jobs:
                            print(f'- {name}')
                    elif cmdargs[0] not in jobs:
                        print('Invalid job name.')
                    elif cmdargs[0] in running_jobs:
                        print('Job is already running.')
                    else:
                        co = jobs[cmdargs[0]]
                        running_jobs[cmdargs[0]] = asyncio.create_task(co(args,
                                                                          rq))
                elif cmd == 'stop':
                    if cmdargs[0] not in jobs:
                        print('Invalid job name.')
                    elif cmdargs[0] not in running_jobs:
                        print('Job is not running.')
                    else:
                        task = running_jobs[cmdargs[0]]
                        task.cancel()
                        del running_jobs[cmdargs[0]]
                elif cmd == 'jobs':
                    if running_jobs:
                        print('Running jobs:')
                        for name in running_jobs.keys():
                            print(f'- {name}')
                    else:
                        print("No running jobs.")
                elif cmd == 'show':
                    for k,v in gargs.items():
                        print(f'{k}: {v}')
                elif cmd == 'set':
                    gargs[cmdargs[0]] = int(cmdargs[1])
                elif cmd == 'zoom':
                    c = {'cmd': 'zoom'}
                    cq.put(c)
                    cq.join()
                elif cmd == 'clear':
                    c = {'cmd': 'clear'}
                    cq.put(c)
                    cq.join()
                elif cmd == 'last':
                    print('result:', last_result)
                    print('error:', last_error)
                else:
                    print("Unknown command.")
            except KeyboardInterrupt as e:
                raise e
            except Exception as e:
                print(f"Error parsing command: {e}")
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    close_flag = 1
    if req_task is not None:
        req_task.cancel()


event_loop = None
request_task = None
async def amain(args, rq, cq):
    global event_loop, request_task
    event_loop = asyncio.get_event_loop()
    request_task = asyncio.create_task(command_handler(args, rq, cq))
    await request_task
    request_task = None


async def stop_request_task():
    request_task.cancel()


def async_handler(args, rq, cq):
    asyncio.run(amain(args, rq, cq))


x = []
y = []
y2 = []
n = 0
close_flag = 0


def graph_handler(args, rq, cq):
    global close_flag
    global x,y,y2,n

    def handle_close(evt):
        global close_flag
        close_flag = 1

    plt.ion()
    figure = plt.figure('Transactional Throughput Stress Test', figsize=(4,3))
    figure.canvas.mpl_connect('close_event', handle_close)
    ax = figure.add_subplot()
    ax.set_title('RESTCONF requests throughput')
    ax.set_ylabel('Requests/second')
    ax.set_xlabel('Seconds')
    line, = ax.plot(x, y)
    line2, = ax.plot(x, y)
    plt.axis([0, 300, 0, args.yaxis])
    ax.legend((line, line2), ('ok', 'nok'), loc='lower right', shadow=True)

    t_prev = time.monotonic()

    def func_animate():
        nonlocal t_prev
        global n, x, y, y2
        results = rq.get()
        l = len(results)
        ok = 0
        nok = 0
        for r in results:
            if r[1] == 'ok':
                ok +=1
            else:
                nok +=1
        t_now = time.monotonic()
        elapsed = t_now-t_prev
        y += [ok/elapsed]
        y2 += [nok/elapsed]
        n += 1

        if len(y)<=300:
            x += [n]
        else:
            y.pop(0)
            y2.pop(0)

        line.set_data(x, y)
        line2.set_data(x, y2)

        t_prev = t_now


    t = time.monotonic()+2
    while close_flag == 0:
        # Update every two seconds
        nt = time.monotonic()
        if nt>t:
            func_animate()
            t = nt+2
            figure.canvas.draw() # draw the figure
        time.sleep(0.1) # wait a little bit of time

        try:
            c = cq.get(block=False)
            if c['cmd'] == 'zoom':
                maxy = int(max(max(y), max(y2))*1.2)
                if maxy == 0:
                    maxy = 100
                plt.axis([0, 300, 0, maxy])
                figure.canvas.draw() # draw the figure
            elif c['cmd'] == 'clear':
                x = []
                y = []
                y2 = []
                n = 0
            cq.task_done()
        except queue.Empty:
            pass

        figure.canvas.flush_events() # flush the GUI events for the figure.

        if close_flag == 1:
            break


def main(args):
    global close_flag

    rq = DataQueue(maxsize=8192)
    cq = queue.Queue()

    async_thread = Thread(target=async_handler, args=(args, rq, cq))
    async_thread.start()

    try:
        graph_handler(args, rq, cq)
    except KeyboardInterrupt:
        pass

    if request_task:
        asyncio.run_coroutine_threadsafe(stop_request_task(), event_loop)
    print('stopped')

    close_flag = 1
    sys.exit(0)

if __name__ == '__main__':
    main(parseArgs())
