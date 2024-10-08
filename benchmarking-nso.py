#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-


import argparse
import asyncio
from collections import deque
from datetime import datetime, timedelta
import importlib.util
import io
import json
import os
import pprint as pp
import queue
import random
import re
import socket
import sys
import time
from threading import Thread
import traceback

from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion, NestedCompleter

from stress_testing.stress_testing import setup, teardown, default_task, Parameters, \
    Sequence, SequenceRequest, RandomValue, single_request

import grpc
import ui_pb2
import ui_pb2_grpc


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost:8080',
                        help='Host:Port to connect to.')
    parser.add_argument('--history', type=int, default=3600,
                         help='How many seconds to keep history data.')
    return parser.parse_args()


#############################################################################
#  Support functions
#############################################################################

# Useful for debugging
pprint = pp.PrettyPrinter(indent=4).pprint


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
last_success = None
last_exc = None


async def sliding_window_executor(q, task_function, task_args):
    global close_flag, last_result, last_error, last_success, last_exc
    await setup(task_args)
    try:
        tasks = set()

        parameters = task_args['parameters']
        parameters['requests-count'] = 0
        parameters['ok'] = 0
        parameters['nok'] = 0
        parameters['exc'] = 0
        stop = parameters.get('stop', 0)
        req_count = 0
        more_requests = True

        # Start initial concurrency number of tasks
        for _ in range(0, parameters['concurrency']):
            tasks.add(asyncio.create_task(task_function(**task_args)))
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
                if result[1] == 'ok':
                    parameters['ok'] += 1
                    last_success = last_result
                elif result[1] == 'nok':
                    parameters['nok'] += 1
                    last_error = last_result
                else:
                    parameters['exc'] += 1
                    last_exc = last_result
                if parameters['add_to_metrics']:
                    # Push results to metrics_handler
                    await q.put((time.time(), result))
            # Start new tasks to keep a total of concurrency number of tasks running.
            # Calculate number of free task slots
            if more_requests:
                tasks_to_start = task_args['parameters']['concurrency']-len(tasks)
                if tasks_to_start > 0:
                    # Start tasks in available slots
                    for _ in range(0, tasks_to_start):
                        tasks.add(asyncio.create_task(task_function(**task_args)))
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
        await teardown(task_args)


#############################################################################
#  THROTTLING JOB EXECUTOR
#############################################################################

async def throttling_executor(q, task_function, task_args):
    global close_flag, last_result, last_error, last_success, last_exc
    await setup(task_args)
    try:
        tasks = set()

        parameters = task_args['parameters']
        parameters['requests-count'] = 0
        parameters['task-wait-dept'] = 0
        parameters['ok'] = 0
        parameters['nok'] = 0
        parameters['exc'] = 0
        req_count = 0

        # NOTE: Only one concurrent task is supported

        # Start initial concurrency number of tasks
        stop = parameters.get('stop', 0)
        for _ in range(0, parameters['concurrency']):
            tasks.add(asyncio.create_task(task_function(**task_args)))
            req_count += 1
            if stop > 0 and req_count >= stop:
                more_requests = False
                break

        while not close_flag and len(tasks) > 0:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            stop = parameters.get('stop', 0)
            rps = parameters.get('requests-per-second', 0)
            add_to_metrics = parameters.get('add_to_metrics', False)
            concurrency = parameters.get('concurrency', 1)
            for d in done:
                global_parameters['requests-count'] += 1
                parameters['requests-count'] += 1
                result = await d
                rid, rstatus, rcode, rresult, rtime = result
                last_result = (datetime.now().isoformat(), result)
                if rstatus == 'ok':
                    parameters['ok'] += 1
                    last_success = last_result
                elif rstatus == 'nok':
                    parameters['nok'] += 1
                    last_error = last_result
                else:
                    parameters['exc'] += 1
                    last_exc = last_result
                if add_to_metrics:
                    # Push results to metrics_handler
                    await q.put((time.time(), result))

                d = 1/(rps/concurrency)-rtime if rps>0 else 0
                if d < 0:
                    # This means that concurrency may need to be increased
                    parameters['task-wait-dept'] -= d
                # Start tasks in available slots
                if stop == 0 or req_count < stop:
                    async def new_task():
                        if d > 0:
                            await asyncio.sleep(d)
                        return await task_function(**task_args)
                    tasks.add(asyncio.create_task(new_task()))
                    req_count += 1

    except asyncio.CancelledError:
        # TODO: More graceful shutdown and collect results?
        pass
    except Exception as e:
        print("EXCEPTION", e)
        # Print traceback
        print(traceback.format_exc())
    finally:
        for t in tasks:
            t.cancel()
        await teardown(task_args)


#############################################################################
#  JOBS
#############################################################################


# NOTE: Non-primitive datatypes will be shared between the running jobs as
#       they are passed by reference.
global_parameters = {
    'host': 'localhost:8080',
    'concurrency': 1,
    'delay': 0,
    'requests-count': 0,
    'add_to_metrics': True,
    'stop': 0  # Run job until stopped
}

def get_jobs():
    jobs_directory_path = f'{os.path.dirname(os.path.abspath(__file__))}/jobs'
    files = os.listdir(jobs_directory_path)
    jobs = dict()
    for filename in files:
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename.removesuffix('.py')
            spec = importlib.util.spec_from_file_location(f'jobs.{module_name}', f'{jobs_directory_path}/{filename}')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'DATA'):
                jobs[module_name] = module.DATA
            elif hasattr(module, 'job'):
                jobs[module_name] = module.job

    return jobs

async def job(args, ctx, rq, data, extra_params={}):
    try:
        print(rq)
        print(data)
        print(extra_params)
        # TODO: Clean up context parameters mixup
        task_args = data.copy()
        task_args['host'] = ctx['host'] if 'host' not in task_args else task_args['host'] # Sometimes we set host as args.host. Why?
        ctx.update(data['parameters'])
        ctx.set(extra_params)
        task_args['parameters'] = ctx
        task_args['ctx'] = ctx
        task_args['data'] = json.dumps(data['data'])
#        await sliding_window_executor(rq, default_task, d)
        await throttling_executor(rq, default_task, task_args)
    except Exception as e:
        print(f"Error in job: {e}")
        print(traceback.format_exc())


jobs = get_jobs()


#############################################################################
#  COMMAND PROMPT HANDLER
#############################################################################

# Dictionary  str -> { 'task': task, 'ctx': dict)
running_jobs = {}
# Dictionary  str -> dict
completed_jobs = {}


class Runtime:
    def __init__(self):
        self.starttime = time.monotonic()
    def __str__(self):
        return f"{self.value:.2f} seconds"
    @property
    def value(self):
        return time.monotonic()-self.starttime


class Throughput:
    def __init__(self, ctx, counter, runtime):
        self.ctx = ctx
        self.counter = counter
        self.runtime = runtime
    def __str__(self):
        return f"{self.value:.2f} requests/second"
    @property
    def value(self):
        try:
            return self.ctx[self.counter]/self.runtime.value
        except:
            return 0.0

async def job_executor(name, task):
    global running_jobs, completed_jobs
    starttime = datetime.now()
    start = time.monotonic()
    running_jobs[name]['ctx']['start'] = starttime.isoformat()
    rt = Runtime()
    running_jobs[name]['ctx']['runtime'] = rt
    tp = Throughput(running_jobs[name]['ctx'], 'requests-count', rt)
    running_jobs[name]['ctx']['throughput'] = tp
    await task
    runtime = time.monotonic()-start
    running_jobs[name]['ctx']['runtime'] = rt.value
    running_jobs[name]['ctx']['throughput'] = tp.value
    completed_jobs[name] = {
        #'start': starttime.isoformat(),
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
    "clear": (None, "Clear graph data."),   # TODO: Fix for webui
    "help": (None, "Show this help."),
}


completer = NestedCompleter.from_nested_dict({
    cmd: cmpltr for cmd, (cmpltr, _) in commands.items()
})


async def command_handler(args, rq, cq):
    global close_flag, global_parameters
    req_task = None
    cmd_history = FileHistory(".benchmarching_nso_history")
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
                                job_data = jobs[cmdargs[0]]
                                ctx = Parameters(dict_copy_except(
                                    global_parameters, ['requests-count']))
                                extra_params = str_to_dict(cmdargs[1:])
                                if not callable(job_data):
                                    global job
                                    running_jobs[cmdargs[0]] = {
                                        'task': asyncio.create_task(
                                            job_executor(cmdargs[0], job(args, ctx, rq, job_data, extra_params=extra_params))),
                                        'ctx': ctx
                                    }
                                else:
                                    running_jobs[cmdargs[0]] = {
                                        'task': asyncio.create_task(
                                            job_executor(cmdargs[0], job_data(args, ctx, rq, None, extra_params=extra_params))),
                                        'ctx': ctx
                                    }
                                # cq.put({'cmd': 'start'})
                                # cq.join()
                        elif cmd == 'stop':
                            if cmdargs[0] not in jobs:
                                print('Invalid job name.')
                            elif cmdargs[0] not in running_jobs:
                                print('Job is not running.')
                            else:
                                task = running_jobs[cmdargs[0]]['task']
                                task.cancel()
                                # del running_jobs[cmdargs[0]]
                                # cq.put({'cmd': 'stop'})
                                # cq.join()
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
                                    ctx = running_jobs[cmdargs[1]]['ctx']
                                    idx = 2
                                    #cq.put({'cmd': 'set'})
                                    #cq.join()
                                else:
                                    print('Invalid job name.')
                            if idx:
                                if cmdargs[idx] in ctx:
                                    v = ctx[cmdargs[idx]]
                                    if type(v) is int:
                                        ctx[cmdargs[idx]] = int(cmdargs[idx+1])
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
                        elif cmd == 'clear':
                            c = {'cmd': 'clear'}
                            #cq.put(c)
                            #cq.join()
                        elif cmd == 'last':
                            print('result:', last_result)
                            print('error:', last_error)
                            print('success:', last_success)
                            print('exception:', last_exc)
                        else:
                            print("Unknown command.")
                    except Exception as e:
                        print(f"Error parsing command: {e}")
                        print(traceback.format_exc())
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
        for name, job in running_jobs.items():
            job['task'].cancel()
        if req_task is not None:
            req_task.cancel()



#############################################################################
#  METRICS HANDLER
#############################################################################

metrics_history = deque()


async def summarize_results(results):
    ok = 0
    nok = 0
    for ts, r in results:
        if r[1] == 'ok':
            ok += 1
        else:
            nok += 1
    return ok, nok

async def metrics_handler(args, rq):
    global close_flag, metrics_history

    # Current strategy is all items from the queue once per second and assume
    # the this task is able to do that. If not, we need to change the strategy.

    t_prev = time.time()
    while close_flag == 0:
        # Update every second
        nt = time.time()
        await asyncio.sleep(1)
        try:
            ok = nok = 0
            results = []
            while True:
                results.append(rq.get_nowait())
        except asyncio.QueueEmpty:
            ok, nok = await summarize_results(results)
        t_now = time.time()
        #print(f"OK: {ok} NOK: {nok} {t_now-t_prev:.2f} sec {len(metrics_history)}")
        metric = (t_now, ok, nok)
        metrics_history.append(metric)
        await notifications.emit(ui_pb2.Metric(
            timestamp=int(t_now),
            ok=ok,
            nok=nok
        ))
        if len(metrics_history) > args.history:
            metrics_history.popleft()
        t_prev = t_now


#############################################################################
#  UI GRPC API
#############################################################################

class ProdCons:
    def __init__(self):
        self.consumers = []

    async def emit(self, notif):
        for s in self.consumers:
            await s.put(notif)

    def subscribe(self):
        q = asyncio.Queue()
        self.consumers.append(q)
        return q

    def unsubscribe(self, q):
        self.consumers.remote(q)


class UIServicer(ui_pb2_grpc.UIServicer):

    def __init__(self, args) -> None:
        self.args = args

    async def Get(self, request: ui_pb2.GetRequest,
                   unused_context) -> ui_pb2.GetResponse:
        global metrics_history
        response = ui_pb2.GetResponse()
        for timestamp, ok, nok in metrics_history:
            metric = ui_pb2.Metric(
                timestamp=int(timestamp),
                ok=ok,
                nok=nok
            )
            response.metrics.append(metric)
        return response
    
    async def Subscribe(self, request: ui_pb2.Empty, unused_context):
        q = notifications.subscribe()
        try:
            while True:
                notif = await q.get()
                yield notif
        except Exception as e:
            print(e)
        finally:
            print("Subscribe stopped")


notifications = ProdCons()

#############################################################################
#  MAIN
#############################################################################

close_flag = 0

async def amain(args, rq, cq):
    global request_task
    request_task = asyncio.create_task(command_handler(args, rq, cq))
    metrics_task = asyncio.create_task(metrics_handler(args, rq))

    server = grpc.aio.server()
    ui_pb2_grpc.add_UIServicer_to_server(UIServicer(args), server)
    server.add_insecure_port('[::]:50052')
    await server.start()
    ui_api = asyncio.create_task(server.wait_for_termination())
    await asyncio.wait([request_task, metrics_task, ui_api], return_when=asyncio.FIRST_COMPLETED)
    request_task = None
    await server.stop(None)
    await server.wait_for_termination()

async def stop_request_task():
    request_task.cancel()


def main(args):
    global global_parameters
    global_parameters['host'] = args.host

    rq = asyncio.Queue(maxsize=8192)
    asyncio.run(amain(args, rq, None))


if __name__ == '__main__':
    main(parseArgs())
