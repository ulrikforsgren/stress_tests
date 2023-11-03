#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-


import argparse
import asyncio
from datetime import datetime
import io
import pprint as pp
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
                           Sequence, SequenceRequest, RandomValue, single_request


pprint = pp.PrettyPrinter(indent=4).pprint


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


#############################################################################
#  SLIDING WINDOW JOB EXECUTOR
#############################################################################


last_result = None
last_error = None


async def sliding_window_executor(q, task_function, data):
    global close_flag, last_result, last_error
    await setup(data)
    try:
        tasks = set()

        # Start initial n_p number of tasks
        for _ in range(0, data['parameters']['n_p']):
            tasks.add(asyncio.create_task(task_function(**data)))

        while not close_flag:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                result = await d
                last_result = (datetime.now().isoformat(), result)
                if result[1] != 'ok':
                    last_error = last_result
                # Push results to graph_handler
                q.put(result)
            # Start new tasks to keep a total of n_p number of tasks running.
            tasks_to_start = data['parameters']['n_p']-len(pending)  # Calculate number of free task slots
            if tasks_to_start>0:
                # Start tasks in available slots
                for _ in range(0, tasks_to_start):
                    pending.add(asyncio.create_task(task_function(**data)))
            tasks = pending
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
    except:
        print(e)
    finally:
        await teardown(data)


async def default_task2(client=None, parameters=Parameters(), host='', op='',
                       url='', data='', resource_type='data', params=None):
    url = re_sub.sub(lambda m: str(parameters[m.group(1)]), url)
    data = re_sub.sub(lambda m: str(parameters[m.group(1)]), data)
    parameters.update_request()
    st = time.monotonic()
    resp = await restconf_request(client,
                                  host,
                                  op,
                                  url,
                                  data,
                                  resource_type,
                                  params)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)


#############################################################################
#  JOBS
#############################################################################


# NOTE: Non-primitive datatypes will be shared between the running jobs.
#       n_p is shared when it comes to the jobs window size.
global_parameters = {
    'n_p': 20,
    'delay': 0,
    'numvlan': 100,
}


async def job_model_a(args, ctx, rq):
    ctx.update({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
    })
    data = {
        'host': args.host,
        'op': 'update',
        'url': '/model-a:model-a/model-a:list=K<<id>>',
        'data': '''{
                    "list":{
                        "str-value": "Changed string data <<data>>"
                    }
                }''',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_create(args, ctx, rq):
    ctx.update({
        "id": SequenceRequest(0),
        "data": RandomValue(0, 4000000000),
        "delay": 0
    })
    data = {
        'host': args.host,
        'op': 'create',
        'url': '/python-service:python-service',
        'data': '''{
                    "service":{
                        "name": "K<<id>>",
                        "delay": <<delay>>,
                        "str-value": "String data <<id>>"
                    }
                }''',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_list_create(args, ctx, rq):
    ctx.update({
        "id": SequenceRequest(0),
        "data": RandomValue(0, 4000000000),
        "delay": 0,
        "numvlan": 100
    })
    data = {
        'host': args.host,
        'op': 'create',
        'url': '/python-service:python-service',
        'data': '''{
                    "service":{
                        "name": "K<<id>>",
                        "delay": <<delay>>,
                        "template": "vlans",
                        "device": "r<<id>>",
                        "num-vlan": <<numvlan>>,
                        "str-value": "String-<<id>>"
                    }
                }''',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_delete(args, ctx, rq):
    ctx.update({
        "id": SequenceRequest(0)
    })
    data = {
        'host': args.host,
        'op': 'delete',
        'url': '/python-service:python-service/python-service:service=K<<id>>',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


jobs = {
    'model_a': job_model_a,
    'python_service_create': job_python_service_create,
    'python_service_list_create': job_python_service_list_create,
    'python_service_delete': job_python_service_delete,
    'python_service_update': None, #job_model_update_python_service,
}


#############################################################################
#  COMMAND PROMPT HANDLER
#############################################################################

# Dictionary  str -> (coroutine, dict)
running_jobs = {}

class DictKeyCompleter(Completer):
    def __init__(self, d):
        self.d = d
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        for k in self.d.keys():
            if k.startswith(word):
                yield Completion(k, start_position=-len(word))


commands = {
        "start": (set(jobs), "Start a named job."),
        "stop": (DictKeyCompleter(running_jobs), "Stop named jobs."),
        "exit": (None, "Exit program."),
        "show": ({
            'global': None,
            'job': DictKeyCompleter(running_jobs)
            }, "Show job parameters."),
        "set": ({
            'global': None,
            'job': DictKeyCompleter(running_jobs)
            }, "Set job parameters."),
        "jobs": (None, "Show running jobs."),
        "last": (None, "Show last request result and error."),
        "zoom": (None, "Zoom graph."),
        "clear": (None, "Clear graph data."),
        "help": (None, "Show this help."),
    }


completer = NestedCompleter.from_nested_dict({
    cmd: cmpltr for cmd, (cmpltr, _) in commands.items()
})


async def command_handler(args, rq, cq):
    global close_flag, global_parameters
    req_task = None
    cmd_history = FileHistory(".stress_test_graph")
    session = PromptSession("benchmarking-nso> ", history=cmd_history)
    try:
        try:
            while not close_flag:
                cmdline = await session.prompt_async(
                                    completer=completer)#,
                                    #complete_style=CompleteStyle.READLINE_LIKE)
                try:
                    cmd, *cmdargs = re.split(r'\s+', cmdline.strip())
                    if cmd in ['exit', 'quit', 'q']:
                        break
                    elif cmd in ['h', 'help']:
                        print('Available commands:')
                        for cmd, (_, text) in commands.items():
                            print(f'{cmd:<20} {text}')

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
                            ctx = Parameters(global_parameters)
                            running_jobs[cmdargs[0]] = {
                                    'task': asyncio.create_task(co(args, ctx, rq)),
                                    'ctx': ctx
                                    }
                    elif cmd == 'stop':
                        if cmdargs[0] not in jobs:
                            print('Invalid job name.')
                        elif cmdargs[0] not in running_jobs:
                            print('Job is not running.')
                        else:
                            task = running_jobs[cmdargs[0]]['task']
                            task.cancel()
                            del running_jobs[cmdargs[0]]
                    elif cmd == 'jobs':
                        if running_jobs:
                            print('Running jobs:')
                            for i, name in enumerate(running_jobs.keys(), 1):
                                print(f'{i}: {name}')
                        else:
                            print("No running jobs.")
                    elif cmd == 'show':
                        if cmdargs[0] == 'global':
                            for k,v in global_parameters.items():
                                print(f'{k}: {v}')
                        elif cmdargs[0] == 'job':
                            if cmdargs[1] in jobs:
                                for k,v in running_jobs[cmdargs[1]]['ctx'].items():
                                    if isinstance(v, Sequence):
                                        print(f'{k}: {v.current()}')
                                    else:                             
                                        print(f'{k}: {v}')
                            else:
                                print('Invalid job name.')
                        else:
                            print('Invalid argument.')
                    elif cmd == 'set':
                        if cmdargs[0] == 'global':
                            # TODO: Handle other datatypes than int
                            global_parameters[cmdargs[1]] = int(cmdargs[2])
                        elif cmdargs[0] == 'job':
                            if cmdargs[1] in jobs:
                                running_jobs[cmdargs[1]]['ctx'][cmdargs[2]] = int(cmdargs[3])
                            else:
                                print('Invalid job name.')
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
                except Exception as e:
                    print(f"Error parsing command: {e}")
        except KeyboardInterrupt as e:
            raise e
        except BaseException as e:
            print(f"Error parsing command: {e}")
        finally:
            print("Exiting...", flush=True)
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
    #event_loop.set_exception_handler(exception_handler)
    request_task = asyncio.create_task(command_handler(args, rq, cq))
    await request_task
    request_task = None


async def stop_request_task():
    request_task.cancel()


def async_handler(args, rq, cq):
    asyncio.run(amain(args, rq, cq))


#############################################################################
#  GRAPH HANDLER
#############################################################################


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


#############################################################################
#  MAIN
#############################################################################

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
