#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-


import argparse
import asyncio
from datetime import datetime, timedelta
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


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost:8080',
                        help='Host:Port to connect to.')
    parser.add_argument('--yaxis', type=int, default=300,
                        help='Y axis max value.')
    return parser.parse_args()


#############################################################################
#  Support functions
#############################################################################

# Useful for debugging
pprint = pp.PrettyPrinter(indent=4).pprint


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


# Function to copy a dictionary except specified keys
def dict_copy_except(d, keys):
    return {k: v for k, v in d.items() if k not in keys}


# Function convert a list of string with the format "key=value" to a dictionary
def str_to_dict(l):
    d = {}
    for s in l:
        k, v = s.split('=')
        d[k] = int(v)
    return d


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

        parameters = data['parameters']
        parameters['requests-count'] = 0
        stop = parameters.get('stop', 0)
        req_count = 0
        more_requests = True

        # Start initial n_p number of tasks
        for _ in range(0, parameters['n_p']):
            tasks.add(asyncio.create_task(task_function(**data)))
            req_count += 1
            if stop > 0 and req_count >= stop:
                more_requests = False
                break

        while not close_flag and len(tasks) > 0:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                global_parameters['requests-count'] += 1
                parameters['requests-count'] += 1
                result = await d
                last_result = (datetime.now().isoformat(), result)
                if result[1] != 'ok':
                    last_error = last_result
                if parameters['add_to_graph']:
                    # Push results to graph_handler
                    q.put(result)
            # Start new tasks to keep a total of n_p number of tasks running.
            # Calculate number of free task slots
            if more_requests:
                tasks_to_start = data['parameters']['n_p']-len(tasks)
                if tasks_to_start > 0:
                    # Start tasks in available slots
                    for _ in range(0, tasks_to_start):
                        tasks.add(asyncio.create_task(task_function(**data)))
                        req_count += 1
                        if stop > 0 and req_count >= stop:
                            more_requests = False
                            break
    except asyncio.CancelledError:
        # TODO: More graceful shutdown and collect results?
        pass
    except Exception as e:
        print("EXCEPTION", e)
    finally:
        for t in tasks:
            t.cancel()
        await teardown(data)


#############################################################################
#  JOBS
#############################################################################


# NOTE: Non-primitive datatypes will be shared between the running jobs as
#       they are passed by reference.
global_parameters = {
    'host': 'localhost:8080',
    'n_p': 1,
    'delay': 0,
    'requests-count': 0,
    'add_to_graph': 1,
}


async def job_model_a(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
    })
    ctx.set(extra_params)
    data = {
        'host': ctx['host'],
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


async def job_python_service_create(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0),
        "data": RandomValue(0, 4000000000),
        "delay": 0
    })
    ctx.set(extra_params)
    data = {
        'host': ctx['host'],
        'op': 'create',
        'url': '/python-service:python-service',
        'data': '''{
                    "service":{
                        "name": "K<<id>>",
                        "delay": <<delay>>,
                        "str-value": "String data <<data>>"
                    }
                }''',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_list_create_no_networking(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0),
        "data": RandomValue(0, 4000000000),
        "delay": 0,
        "numvlan": 1,
        "stop": 1000
    })
    ctx.set(extra_params)
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
                        "str-value": "<<data>>"
                    }
                }''',
        'parameters': ctx,
        'params': {'no-networking': 'true'}
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_list_update_no_networking(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
        "delay": 0,
        "numvlan": 1
    })
    ctx.set(extra_params)
    data = {
        'host': args.host,
        'op': 'update',
        'url': '/python-service:python-service/service=K<<id>>',
        'data': '''{
                    "service":{
                        "delay": <<delay>>,
                        "template": "vlans",
                        "device": "r<<id>>",
                        "num-vlan": <<numvlan>>,
                        "str-value": "<<data>>"
                    }
                }''',
        'parameters': ctx,
        'params': {'no-networking': 'true'}
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_list_update_commit_queue(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
        "delay": 0,
        "numvlan": 1
    })
    ctx.set(extra_params)
    data = {
        'host': args.host,
        'op': 'update',
        'url': '/python-service:python-service/service=K<<id>>',
        'data': '''{
                    "service":{
                        "delay": <<delay>>,
                        "template": "vlans",
                        "device": "r<<id>>",
                        "num-vlan": <<numvlan>>,
                        "str-value": "<<data>>"
                    }
                }''',
        'parameters': ctx,
        'params': {'commit-queue': 'sync'}
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_list_update(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0, wrap=1000),
        "data": RandomValue(0, 4000000000),
        "delay": 0,
        "numvlan": 1
    })
    ctx.set(extra_params)
    data = {
        'host': args.host,
        'op': 'update',
        'url': '/python-service:python-service/service=K<<id>>',
        'data': '''{
                    "service":{
                        "delay": <<delay>>,
                        "template": "vlans",
                        "device": "r<<id>>",
                        "num-vlan": <<numvlan>>,
                        "str-value": "<<data>>"
                    }
                }''',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_python_service_delete(args, ctx, rq, extra_params={}):
    ctx.update({
        "id": SequenceRequest(0)
    })
    ctx.set(extra_params)
    data = {
        'host': args.host,
        'op': 'delete',
        'url': '/python-service:python-service/python-service:service=K<<id>>',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_devices_sync_from(args, ctx, rq, extra_params=None):
    ctx.update({
        "id": SequenceRequest(0),
        'stop': 1000
    })
    ctx.set(extra_params)
    data = {
        'host': args.host,
        'op': 'action',
        'url': '/tailf-ncs:devices/device=r<<id>>/sync-from',
        'parameters': ctx
    }
    await sliding_window_executor(rq, default_task, data)


async def job_dummy(args, ctx, rq, extra_params=None):
    ctx.update({
        "id": RandomValue(0, 4000000000),
        "value": SequenceRequest(0),
        "requests-count": 0
    })
    ctx.set(extra_params)
    try:
        while not close_flag:
            ctx['requests-count'] += 1
            await asyncio.sleep(ctx['delay']/1000)
    except asyncio.CancelledError:
        pass

jobs = {
    'model_a': job_model_a,
    'python_service_create': job_python_service_create,
    'python_service_list_create_no_networking': job_python_service_list_create_no_networking,
    'python_service_list_update_no_networking': job_python_service_list_update_no_networking,
    'python_service_list_update_commit_queue': job_python_service_list_update_commit_queue,
    'python_service_list_update': job_python_service_list_update,
    'python_service_delete': job_python_service_delete,
    'python_service_update': None,  # job_model_update_python_service,
    'devices-sync-from': job_devices_sync_from,
    'dummy': job_dummy
}


#############################################################################
#  COMMAND PROMPT HANDLER
#############################################################################

# Dictionary  str -> { 'task': task, 'ctx': dict)
running_jobs = {}
# Dictionary  str -> dict
completed_jobs = {}


async def job_executor(name, task):
    global running_jobs, completed_jobs
    starttime = datetime.now()
    start = time.monotonic()
    await task
    runtime = time.monotonic()-start
    completed_jobs[name] = {
        'start': starttime.isoformat(),
        'end': (starttime+timedelta(seconds=runtime)).isoformat(),
        'runtime': runtime
    }
    print(f"JOB DONE: {name} {runtime} seconds", flush=True)
    if name in running_jobs:
        completed_jobs[name].update(running_jobs[name]['ctx'])
        del running_jobs[name]


class DictKeyCompleter(Completer):
    def __init__(self, d):
        self.d = d

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        start = document.find_previous_word_beginning(1)
        start2 = document.find_previous_word_beginning(2)
        if start2 is None and not (start is not None and word == ''):
            for k in self.d.keys():
                if k.startswith(word):
                    yield Completion(k, start_position=-len(word))


class DictDictKeyCompleter(Completer):
    def __init__(self, d):
        self.d = d

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor()
        start = document.find_previous_word_beginning(1)
        start2 = document.find_previous_word_beginning(2)
        start3 = document.find_previous_word_beginning(3)

        if start2 is None and not (start is not None and word == ''):
            for k in self.d.keys():
                if k.startswith(word):
                    yield Completion(k, start_position=-len(word))
        elif start3 is None and not (start2 is not None and word == ''):
            s = start if start2 is None else start2
            e = -1 if start2 is None else start-1
            name = document.text_before_cursor[s:e]
            if name in self.d:
                for k in self.d[name]['ctx'].keys():
                    if k.startswith(word):
                        yield Completion(k, start_position=-len(word))


commands = {
    "start": (set(jobs), "Start a named job."),
    "stop": (DictKeyCompleter(running_jobs), "Stop named jobs."),
    "exit": (None, "Exit program."),
    "show": ({
        'global': None,
        'job': DictKeyCompleter(running_jobs),
        'completed': DictKeyCompleter(completed_jobs)
    }, "Show job parameters."),
    "set": ({
            'global': DictKeyCompleter(global_parameters),
            'job': DictDictKeyCompleter(running_jobs)
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
    with patch_stdout():
        session = PromptSession("benchmarking-nso> ", history=cmd_history)
        try:
            try:
                while not close_flag:
                    cmdline = await session.prompt_async(
                        completer=completer)  # ,
                    # complete_style=CompleteStyle.READLINE_LIKE)
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
                                ctx = Parameters(dict_copy_except(
                                    global_parameters, ['requests-count']))
                                extra_params = str_to_dict(cmdargs[1:])
                                running_jobs[cmdargs[0]] = {
                                    'task': asyncio.create_task(
                                        job_executor(cmdargs[0], co(args, ctx, rq, extra_params=extra_params))),
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
                                # del running_jobs[cmdargs[0]]
                        elif cmd == 'jobs':
                            if running_jobs:
                                print('Running jobs:')
                                # TODO: Increasing number for each job
                                for i, name in enumerate(running_jobs.keys(), 1):
                                    print(f'{i}: {name}')
                            else:
                                print("No running jobs.")
                        elif cmd == 'show':
                            if cmdargs[0] == 'global':
                                for k, v in global_parameters.items():
                                    print(f'{k:<20}: {v}')
                            elif cmdargs[0] == 'job':
                                if cmdargs[1] in jobs:
                                    for k, v in running_jobs[cmdargs[1]]['ctx'].items():
                                        if isinstance(v, Sequence):
                                            print(f'{k:<20}: {v.current()}')
                                        else:
                                            print(f'{k:<20}: {v}')
                                else:
                                    print('Invalid job name.')
                            elif cmdargs[0] == 'completed':
                                if cmdargs[1] in completed_jobs:
                                    for k, v in completed_jobs[cmdargs[1]].items():
                                        if isinstance(v, Sequence):
                                            print(f'{k:<20}: {v.current()}')
                                        else:
                                            print(f'{k:<20}: {v}')
                                else:
                                    print('Invalid job name.')
                            else:
                                print('Invalid argument.')
                        elif cmd == 'set':
                            idx = 0
                            if cmdargs[0] == 'global':
                                ctx = global_parameters
                                idx = 1
                            elif cmdargs[0] == 'job':
                                if cmdargs[1] in jobs:
                                    idx = 2
                                else:
                                    print('Invalid job name.')
                                    ctx = running_jobs[cmdargs[1]]['ctx']
                            if idx:
                                if cmdargs[idx] in ctx:
                                    v = ctx[cmdargs[idx]]
                                    if type(v) is int:
                                        ctx[cmdargs[idx]] = int(cmdargs[idx+1])
                                        print(ctx[cmdargs[idx]])
                                    elif type(v) is str:
                                        ctx[cmdargs[idx]] = cmdargs[idx+1]
                                    elif type(v) is float:
                                        ctx[cmdargs[idx]] = float(
                                            cmdargs[idx+1])
                                    elif isinstance(v, Sequence):
                                        ctx[cmdargs[idx]].set(
                                            int(cmdargs[idx]))
                                else:
                                    print('Invalid parameter name.')

                        elif cmd == 'zoom':
                            c = {'cmd': 'zoom', 'y': (
                                int(cmdargs[0]) if len(cmdargs) > 0 else 0)}
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
    # event_loop.set_exception_handler(exception_handler)
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
    global x, y, y2, n

    def handle_close(evt):
        global close_flag
        close_flag = 1

    plt.ion()
    figure = plt.figure('Transactional Throughput Stress Test', figsize=(9, 6))
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
                ok += 1
            else:
                nok += 1
        t_now = time.monotonic()
        elapsed = t_now-t_prev
        y += [ok/elapsed]
        y2 += [nok/elapsed]
        n += 1

        if len(y) <= 300:
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
        if nt > t:
            func_animate()
            t = nt+2
            figure.canvas.draw()  # draw the figure
        time.sleep(0.1)  # wait a little bit of time

        try:
            c = cq.get(block=False)
            if c['cmd'] == 'zoom':
                if c['y'] == 0:
                    maxy = int(max(max(y), max(y2))*1.2)
                else:
                    maxy = c['y']
                if maxy == 0:
                    maxy = 100
                plt.axis([0, 300, 0, maxy])
                figure.canvas.draw()  # draw the figure
            elif c['cmd'] == 'clear':
                x = []
                y = []
                y2 = []
                n = 0
            cq.task_done()
        except queue.Empty:
            pass

        figure.canvas.flush_events()  # flush the GUI events for the figure.

        if close_flag == 1:
            break


#############################################################################
#  MAIN
#############################################################################

def main(args):
    global close_flag

    global_parameters['host'] = args.host

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
