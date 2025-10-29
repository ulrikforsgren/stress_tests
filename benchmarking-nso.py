#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
from collections import deque
from datetime import datetime, timedelta
import importlib.util
import os
import pprint as pp
import re
import sys
import time
import traceback

from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion, NestedCompleter

from stress_testing.executors import sliding_window_executor
from stress_testing.parameters import Parameters, Parameter
from stress_tests.argparser import parseArgs

import grpc
import ui_pb2
import ui_pb2_grpc


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
#  JOBS
#############################################################################


# NOTE: Non-primitive datatypes will be shared between the running jobs as
#       they are passed by reference.
global_parameters = {
    'close_flag': 0, # Need to handle this outside the parameters in some way
    'host': 'localhost:8080',
    'concurrency': 1,
    'requests-per-second': 0, # 0 means no limit
    'delay': 0,
    'requests-count': 0,
    'add_to_metrics': True,
    'stop': 0  # Run job until stopped
}

last = {
    'result': None,
    'error': None,
    'success': None,
    'exc': None
}


def get_jobs(path):
    jobs_directory_path = f'{os.path.dirname(os.path.abspath(__file__))}/{path}'
    files = os.listdir(jobs_directory_path)
    jobs = dict()
    for filename in files:
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename.removesuffix('.py')
            spec = importlib.util.spec_from_file_location(f'jobs.{module_name}', f'{jobs_directory_path}/{filename}')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'intent'):
                jobs[module_name] = (module.intent, module.parameters)
            elif hasattr(module, 'job'):
                jobs[module_name] = module.job
            else:
                print(f"ERROR: Module {module_name} does not contain 'intent' or 'job' function")
                sys.exit(1)
    return jobs

    
async def job(args, parameters, job_data, cmd_params=None, result_queue=None):
    global global_parameters, last
    try:
        cmd_params = cmd_params or {}
        intent, job_parameters = job_data
        task_args = intent.copy()
        task_args['host'] = global_parameters['host'] if 'host' not in task_args else task_args['host'] # Sometimes we set host as args.host. Why?
        parameters.update(job_parameters)
        parameters.set(cmd_params)
        await sliding_window_executor(args, task_args, parameters,
                                      global_parameters=global_parameters, last=last,
                                      want_results=False,
                                      result_queue=result_queue)
    except Exception as e:
        print(f"Error in job: {e}")
        print(traceback.format_exc())


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
        print(word)
        if start2 is None and not (start is not None and word == ''):
            for k in self.d.keys():
                if k.startswith(word):
                    yield Completion(k, start_position=-len(word))


class DictDictKeyCompleter(Completer):
    def __init__(self, d):
        self.d = d

    def get_completions(self, document, complete_event):
        # Treat only spaces as separators to avoid splitting on '-'
        text = document.text_before_cursor
        ends_with_space = bool(text) and text[-1].isspace()
        stripped = text.rstrip()
        tokens = re.split(r"\s+", stripped) if stripped else []

        # Current word prefix (only space-separated)
        word = '' if ends_with_space else (tokens[-1] if tokens else '')

        # If no tokens yet, or we're typing the first token: complete job names
        if len(tokens) <= 1 and not (len(tokens) == 1 and ends_with_space):
            for k in self.d.keys():
                if k.startswith(word):
                    yield Completion(k, start_position=-len(word))
        else:
            # tokens[0] is the job name; complete its ctx keys next
            name = tokens[0] if tokens else ''
            if name in self.d:
                for k in self.d[name]['ctx'].keys():
                    if k.startswith(word):
                        yield Completion(k, start_position=-len(word))

def get_commands(jobs):
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
    return commands, completer


async def command_handler(args, result_queue, cq):
    global global_parameters, last, jobs
    req_task = None
    commands, completer = get_commands(jobs)
    cmd_history = FileHistory(".benchmarching_nso_history")
    with patch_stdout():
        session = PromptSession("benchmarking-nso> ", history=cmd_history)
        try:
            try:
                while not global_parameters['close_flag']:
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
                                global_parameters = Parameters(dict_copy_except(
                                    global_parameters, ['requests-count']))
                                cmd_params = str_to_dict(cmdargs[1:])
                                if not callable(job_data):
                                    global job
                                    running_jobs[cmdargs[0]] = {
                                        'task': asyncio.create_task(
                                            job_executor(cmdargs[0], job(args, global_parameters, job_data, cmd_params=cmd_params, result_queue=result_queue))),
                                        'ctx': global_parameters
                                    }
                                else:
                                    running_jobs[cmdargs[0]] = {
                                        'task': asyncio.create_task(
                                            job_executor(cmdargs[0], job_data(args, global_parameters, cmd_params=cmd_params, result_queue=result_queue))),
                                        'ctx': global_parameters
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
                                        if isinstance(v, Parameter):
                                            print(f'{k:<20}: {repr(v)}')
                                        else:
                                            print(f'{k:<20}: {v}')
                                else:
                                    print('Invalid job name.')
                            elif cmdargs[0] == 'completed':
                                if cmdargs[1] in completed_jobs:
                                    for k, v in completed_jobs[cmdargs[1]].items():
                                        if isinstance(v, Parameter):
                                            print(f'{k:<20}: {repr(v)}')
                                        else:
                                            print(f'{k:<20}: {v}')
                                else:
                                    print('Invalid job name.')
                            else:
                                print('Invalid argument.')
                        elif cmd == 'set':
                            idx = 0
                            if cmdargs[0] == 'global':
                                global_parameters = global_parameters
                                idx = 1
                            elif cmdargs[0] == 'job':
                                if cmdargs[1] in jobs:
                                    global_parameters = running_jobs[cmdargs[1]]['ctx']
                                    idx = 2
                                    #cq.put({'cmd': 'set'})
                                    #cq.join()
                                else:
                                    print('Invalid job name.')
                            if idx:
                                if cmdargs[idx] in global_parameters:
                                    v = global_parameters[cmdargs[idx]]
                                    if type(v) is int:
                                        global_parameters[cmdargs[idx]] = int(cmdargs[idx+1])
                                    elif type(v) is str:
                                        global_parameters[cmdargs[idx]] = cmdargs[idx+1]
                                    elif type(v) is float:
                                        global_parameters[cmdargs[idx]] = float(
                                            cmdargs[idx+1])
                                    elif isinstance(v, Parameter):
                                        global_parameters[cmdargs[idx]].set(
                                            int(cmdargs[idx]))
                                else:
                                    print('Invalid parameter name.')
                        elif cmd == 'clear':
                            c = {'cmd': 'clear'}
                            #cq.put(c)
                            #cq.join()
                        elif cmd == 'last':
                            print('result:', last['result'])
                            print('error:', last['error'])
                            print('success:', last['success'])
                            print('exception:', last['exc'])
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
        global_parameters['close_flag'] = 1
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
    global global_parameters, metrics_history

    # Current strategy is all items from the queue once per second and assume
    # the this task is able to do that. If not, we need to change the strategy.

    t_prev = time.time()
    while global_parameters['close_flag'] == 0:
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

async def amain(args, rq, cq):
    global request_task
    try:
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
    except asyncio.CancelledError:
        pass

async def stop_request_task():
    request_task.cancel()


def main(args):
    try:
        global global_parameters, jobs
        global_parameters['host'] = args.host
        jobs = get_jobs(args.path)
        rq = asyncio.Queue(maxsize=8192)
        asyncio.run(amain(args, rq, None))
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    main(parseArgs(options='benchmarking', path='jobs'))
