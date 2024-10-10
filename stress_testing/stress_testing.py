#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import copy
from datetime import datetime, timedelta
import json
import os
import os.path as path
import pprint as pp
import random
import re
import rstr
import sys
import time
import traceback
from xmlrpc.client import boolean

from .restconf_api import REQ_DISPATCH, setup, teardown, restconf_request
from .gen_chart import generate_html

# Some default values
#  
HOST = 'localhost'
PORT = 8080

# Some global variables
#
pprint = pp.PrettyPrinter(indent=4).pprint

# Some coloring for the terminal
#
class ansi:
    RST = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    REVERSE = '\033[7m'
    NREVERSE = '\033[27m'
    PINK = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'


###############################################################################
#  ARGUMENTS PARSER FUNCTIONS
###############################################################################
#

def parseArgs(args=None, extra_cmds=[], options='old-crud', path=None):
    commands = []
    if isinstance(options, str):
        options = [options]
    if {'old-crud', 'crud'}.intersection(options):
        options += [
            'basic',
            'scale',
            'params',
            'commit-params',
            'json',
            'report',
            'highlight',
        ]
        commands += ['clean', 'create', 'read', 'update', 'delete', 'crud', 'cud']
    elif 'old-crud' in options:
        options += ['single']
    elif 'benchmarking' in options:
        options += ['basic']
    elif 'scripted' in options:
        options += [
            'basic',
            'state'
        ]
        commands += ['clean', 'run']
    elif 'single' in options:
        options += [
            'basic',
            'scale',
            'params',
            'commit-params',
            'action'
        ]

    parser = argparse.ArgumentParser()
    if commands:
        parser.add_argument('cmd', nargs='+', choices=commands + extra_cmds)
    if {'crud', 'action'}.intersection(options):
        parser.add_argument('test', type=str,
                            help='Test to run.')
    if 'action' in options:
        parser.add_argument('operation', type=str,
                            help='Operation to run.')
    if 'basic' in options:
        parser.add_argument('--host', type=str,
                            help='host[:port]',
                            default='localhost:8080')
        parser.add_argument("--dry-run", required=False, action='store_true', default=False,
                            help="Run sequence but do not send request over network.")
        parser.add_argument("--echo", required=False, action='store_true', default=False,
                            help="Echo request to console.")
        parser.add_argument("-q", required=False, action='store_true',
                            default=False, help='Silent mode.')
        parser.add_argument("-v", required=False, action='store_true',
                            default=False, help='Verbose mode. Show result of each request.')
    if 'state' in options:
        parser.add_argument("--keep-state", required=False, action='store_true', default=False,
                            help="Loads state if state files exist and saves after run.")
    if 'single' in options:
        parser.add_argument("--single", required=False, action='store_true', default=False,
                        help="Run one iteration of one operation with one windows size.")
    if 'scale' in options:
        parser.add_argument("-n", required=False, type=int,
                            help='Number of total requests.')
        parser.add_argument("-w", required=False, type=int, default=40,
                            help='Max window size. Starting 1, 2, 5, .., max')
        parser.add_argument("-s", required=False, type=str,
                            help='Window size(s) comma sepated.')
    if 'params' in options:
        parser.add_argument("-p", required=False, type=str, action='append',
                            help='Alter parameters.')
    if 'commit-params' in options:
        parser.add_argument("--no-networking", required=False, action='store_true',
                            default=False, help='Commit with no-networking.')
        parser.add_argument("--commit-queue", required=False, action='store_true',
                            default=False, help='Commit to commit-queue.')
    if 'json' in options:
        parser.add_argument("-o", required=False, type=str,
                            help='Output result in json format to file.')
    if 'report' in options:
        parser.add_argument("--html", required=False, action='store_true',
                            help='Output results as graphs in html.')
        parser.add_argument("--open", required=False, action='store_true',
                            help='Open generated html.')
    if 'benchmarking' in options:
        parser.add_argument('--history', type=int, default=3600,
                             help='How many seconds to keep history data.')
    if 'highlight' in options:
        parser.add_argument("--highlight", required=False, action='store_true',
                            default=False, help='Highlight output to make it more readable.')
    if path:
        parser.add_argument("--path", required=False, type=str, action='append',
                            default=path, help='Path to search for modules.')
    
    parsed_args = parser.parse_args(args)
    if 'state' not in options:
        parsed_args.keep_state = False
    return parsed_args



###############################################################################
#  HELPER FUNCTIONS
###############################################################################
#

async def setup_task(args, client, host):
    # Reading an arbitrary leaf to force the client to setup a connection.
    resource = '/tailf-ncs:devices/global-settings/read-timeout'
    op = 'read'
    st = time.monotonic()
    resp = await restconf_request(args, client,
                                  host,
                                  op,
                                  resource)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)


# Calculate the average execution time for all "ok" requests and
# count number of result types "ok"/"nok"/"exception".
def calc_average(results):
    total_ok = 0.0
    count_ok = 0
    count_wrong = 0
    count_exc = 0
    for r in results:
        rid, res, *rest = r
        if res == 'ok':
            st, _, el = rest
            total_ok += el
            count_ok += 1
        elif res == 'nok':
            count_wrong += 1
        elif res == 'exception':
            count_exc += 1

    return count_ok, total_ok, count_wrong, count_exc


def set_flags(args, d):
    flags = {}
    if args.no_networking:
        flags['no-networking'] = 'true'
    if args.commit_queue:
        flags['commit-queue'] = 'sync'
    if 'query_parameters' in d:
        d['query_parameters'].update(flags)
    else:
        d['query_parameters'] = flags


# Generator for 1,2,5,10,20,... sequence
def np_gen(max_p):
    n = 1
    m = 1
    while n <= max_p:
        for s in [1, 2, 5]:
            np = s*m
            if np < max_p:
                yield np
            else:
                yield max_p
                return
        m *= 10


# Function to replace any of the characters in the string s with the character c
def replace_chars(s, c, chars):
    for ch in chars:
        s = s.replace(ch, c)
    return s


def json_to_tuple(json_str):
    def convert(obj):
        if isinstance(obj, list):
            return tuple(convert(item) for item in obj)
        elif isinstance(obj, dict):
            return {key: convert(value) for key, value in obj.items()}
        else:
            return obj

    return convert(json.loads(json_str))


def number_of_open_connections(conn):
    if len(conn._conns):
        key = list(conn._conns.keys())[0]  # Assuming only one key
        return len(conn._conns[key])
    else:
        return 0



###############################################################################
#  PARAMETERS
###############################################################################
#
# Classes to inject dynamic values for stressing requests.
#
#  Paramaters that can be updated on multiple levels when iterating:
#   - Each request
#   - Each batch
#   - Each reference
#
# Example:
#
# parameters = Parameters({
#     "id": SequenceRequest(0),
#     "vid": Sequence(0),
#     "group": SequenceBatch(0)
# })
#

def format_parameters(parameters, string, update=True):
    re_sub = re.compile(r'<<(\w+)>>')
    def update_str(parameters, key):
        p = parameters[key]
        if update:
            if isinstance(p, Parameter):
                p.update_str()
        return str(p)
    return re_sub.sub(lambda m: update_str(parameters, m.group(1)), string)


class Parameter:
    def __init__(self, keep_state=False):
        self.keep_state = keep_state
        self.current = '<no value>'

    def __deepcopy__(self, memo):
        new = self.__class__(self.keep_state)
        new.current = s.current
        return new

    # Save the current state.
    def getstate(self):
        raise NotImplementedError

    # Restore to a stored state.
    def setstate(self, state):
        raise NotImplementedError

    # Implemented by LookupValue
    # TODO: Usage unknown
    def get(self, parameters, key):
        raise NotImplementedError
    
    # Set/update from e.g. benchmarking-nso cli.
    def set(self, *args):
        raise NotImplementedError

    # Update when a new value is requested
    # and return the new value.
    def update_str(self):
        pass

    # Update the value after each request.
    def update_request(self):
        pass

    # Update after a batch of requests.
    def update_batch(self):
        pass

    # Restore to initial state.
    def reset(self):
        pass

    # Return the current value.
    def current(self):
        return None
    
    # Return the calculated value.
    # Implemented by Calc
    # TODO: Should this be merged with update_str?
    def val(self, parameters):
        raise NotImplementedError()
    
    # Return current value as a string.
    def __str__(self):
        return str(self.current)

    # Return the representative value of the parameter. 
    def __repr__(self):
        return 'Parameter{}'


class Sequence(Parameter):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(keep_state)
        self.n = n
        self.wrap = wrap

    def __repr__(self):
        return f'{self.__class__.__name__}(start={self.n}, wrap={self.wrap}, current={self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.n)

    def getstate(self):
        return self.n

    def setstate(self, state):
        self.n = state

    def set(self, n):
        if isinstance(n, str):
            n = int(n)
        self.n = n

    def update_str(self):
        if self.current == '<no value>':
            self.current = self.n
        else:
            self.current += 1
            if self.wrap is not None:
                self.current = self.current % self.wrap

    def reset(self):
        self.n = 0


class SequenceRequest(Sequence):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(n, wrap, keep_state)

    def update_str(self):
        pass

    def update_request(self):
        super().update_str()


class SequenceBatch(Sequence):
    def __init__(self, n, keep_state=False):
        super().__init__(n, keep_state)

    def update_str(self):
        pass

    def update_batch(self):
        if self.current == '<no value>':
            self.current = self.n
        else:
            self.current += 1
            if self.wrap is not None:
                self.current = self.current % self.wrap


class SequenceRequestRandomized(SequenceRequest):
    def __init__(self, length, wrap=None, seed=None, keep_state=False):
        super().__init__(0, wrap, keep_state)
        self.length = length
        self.seed = seed
        self.rnd = random.Random(seed)
        # TODO: Maybe it is better to do this in update otherwise it will be
        # done in the runner but not used.
        self.sequence = list(range(self.length))
        self.rnd.shuffle(self.sequence)
        self.n = 0

    def __repr__(self):
        return f'SequenceRequestRandomized(seed={self.seed} length={self.length}, values left={len(self.sequence)} current={self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.length, self.wrap, self.seed)
    
    def getstate(self):
        raise RuntimeWarning('Implementation must be update to support updating scheme')
        return (self.n, self.sequence)

    def setstate(self, state):
        # NOTE: This will restore the sequence as a tuple and will be immutable.
        # NOTE: The random generator state is not restored.
        self.n, self.sequence = state
        raise RuntimeWarning('Implementation must be update to support updating scheme')
    
    def update_request(self):
        try:
            self.current = self.sequence[self.n]
        except IndexError:
            self.current = f'<no more values>{self.n}'
        self.n += 1
        if self.wrap is not None:
            self.n = self.n % self.wrap
        


class RandomParameter(Parameter):
    def __init__(self, seed=None, keep_state=False):
        super().__init__(keep_state)
        self.seed = seed
        self.rnd = random.Random(seed)

    def getstate(self):
        return self.rnd.getstate()

    def setstate(self, state):
        self.rnd.setstate(state)


class RandomValue(RandomParameter):
    def __init__(self, lower, upper, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.lower = lower
        self.upper = upper

    def __repr__(self):
        return f'RandomValue({self.lower}..{self.upper}, {self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.lower, self.upper, self.seed)
    
    def update_str(self):
        self.current = random.randint(self.lower, self.upper)



class RandomValueRequest(RandomParameter):
    def __init__(self, lower, upper, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.lower = lower
        self.upper = upper
        self.n = random.randint(self.lower, self.upper)

    def __repr__(self):
        return f'RandomValueRequest({self.lower}..{self.upper}, {self.current})'

    def __deepcopy__(self, memo):
        return self.__class__(self.lower, self.upper, self.seed)
    
    def update_request(self):
        self.current = random.randint(self.lower, self.upper)

    

class RandomString(RandomParameter):
    def __init__(self, length, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.length = length
        self.rstr = rstr.Rstr(self.rnd)
        self.value = self.rstr.letters(self.length)

    def __repr__(self):
        return f'{self.__class__}(seed={self.seed}, length={self.length}), current={self.current}'

    def __deepcopy__(self, memo):
        return self.__class__(self.length, self.seed)

    def getstate(self):
        return (super().getstate(), self.value)

    def setstate(self, state):
        state, self.value = state
        super().setstate(state)

    def set(self, n):
        # NOTE: This is a hack to allow changing the length of the string,
        #       but it breaks the pseudo random sequence.
        if isinstance(n, str):
            n = int(n)
        self.length = n

    def update_str(self):
        self.current = self.rstr.letters(self.length)


class RandomStringRequest(RandomString):
    def __init__(self, length, seed=None, keep_state=False):
        super().__init__(length, seed, keep_state)

    def update_str(self):
        pass

    def update_request(self):
        self.current = self.rstr.letters(self.length)


class LookupValue(Parameter):
    def __init__(self, values, format, attr):
        super().__init__()
        self.values = values
        self.format = format
        self.attr = attr

    def __repr__(self):
        return f'LookupValue(key={self.key})'

    def __deepcopy__(self):
        return self.__class__(self.values, self.format)
    
    def __str__(self):
        raise NotImplementedError("LoopupValue should not be converted to string")
        
    def get(self, parameters, key):
        try:
            name = format_parameters(parameters, self.format)
            inst = self.values[name]
            return inst[self.attr]
        except Exception as e:
            print(f'ERROR: {e}')
            print(f'ERROR: {self.format}')
            return "ERROR"



class Calc(Parameter):
    def __init__(self, key, wrap, mul, add):
        self.key = key
        self.wrap = wrap
        self.mul = mul
        self.add = add

    def __repr__(self):
        return f'Calc(key={self.key}, mul{self.mul}, add={self.add}, current={self.current})' 
    
    def update_str(self, parameters):
        i = parameters[self.key].n
        self.current = i//self.wrap*self.mul+self.add
    
    
"""
class Parameters is a dict of values and Parameter objects.
Makes it possible provide parameters in the form of <<x>> in
resource and data strings.
"""


class Parameters(dict):
    def set(self, d):
        for k, v in d.items():
            if k in self:
                ov = self[k]
                if isinstance(ov, Parameter):
                    ov.set(v)
                elif ov is int:
                    self[k] = int(v)
                elif ov is float:
                    self[k] = float(v)
                else:
                    self[k] = v

    def __missing__(self, key):
        return "<<" + key + ">>"

    def update_request(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.update_request()

    def update_batch(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.update_batch()

    def update_cmdline(self, cmd_p):
        if cmd_p is None:
            return
        if isinstance(cmd_p, str):
            k, v = cmd_p.split('=')
            self.update({k: v})
        elif isinstance(cmd_p, list):
            for p in cmd_p:
                k, v = p.split('=')
                self.update({k: v})
        else:
            raise TypeError(f'Invalid type: {type(cmd_p)}')

    def reset(self):
        for v in self.values():
            if isinstance(v, Parameter):
                v.reset()

    def save_state(self):
        for k,v in self.items():
            if isinstance(v, Parameter) and v.keep_state:
                with open(f'{k}.state', 'w') as f:
                    f.write(json.dumps(v.getstate()))

    def load_state(self):
        n = 0
        s = 0
        for k,v in self.items():
            if isinstance(v, Parameter) and v.keep_state:
                n += 1
                try:
                    with open(f'{k}.state', 'r') as f:
                        v.setstate(json_to_tuple(f.read()))
                        s += 1
                except FileNotFoundError:
                    pass
        if s and n != s:
            print(f'ERROR: Inconsistent states. Loaded {s} of {n} states. Remove state files to start fresh.')
            sys.exit(1)



###############################################################################
#  TASKS
###############################################################################
#
##### Default Task
#
# parameters (dict) has following keys:
# - concurrency: number of concurrent requests (int) (optional)
# - stop: stop after number of requests (int) (optional)
# - requests-per-second: number of requests per second (int) (optional)
#
# task_args (dict) keys:
# - host: host to connect to (ip:port)
# - op: operation (create, read, update, delete, action)
# - resource: resource path
# - data: request payload (dict/string) (optional)
# - resource_type: RESTCONF resource type (data, operations) (optional) 
# - query_parameters: RESTCONF query parameters (dict) (optional)
#

async def default_task(args, parameters, client=None,
                       host='', op='', resource='', data='',
                       resource_type='data', query_parameters=None):
    if isinstance(data, dict):
        data = json.dumps(data)
    # Update parameters for this request
    parameters.update_request()
    # Substitute request parameters 
    resource = format_parameters(parameters, resource)
    data = format_parameters(parameters, data)
    # Schedule request and measure execution time
    st = time.monotonic()
    resp = await restconf_request(args,
                                  client,
                                  host,
                                  op,
                                  resource,
                                  data,
                                  resource_type,
                                  query_parameters)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)



###############################################################################
#  EXECUTORS
###############################################################################
#
# Executes the requested task until the number of parameter['stop'] requests 
# have been performed. If stop is 0 (default), it will continue forever.
#
# batch_executor (currently not implemented) executes requests in batches',
# with the size of parameter['concurrency'], and waits for them to complete.
#
# sliding_window_executor executes requests using a window, of the size:
# parameter['concurrency'], and starts a new requests as soon one has completed.
# The parameter['requests-per-second'] can be used to limit the rate,
# 0 (default) means as fast a possible.
#

async def batch_executor(args, task_args, parameters, setup_func=setup,
                                teardown_func=teardown, task_func=default_task):
    results = []
    n = parameters.get('n', 1)
    n_p = parameters.get('n_p', 1)
    while n > 0:  # Execute requests in batches of n_p in parellel.
        if n < n_p:
            n_p = n
        await setup_func(task_args)
        st = time.monotonic()
        tasks = [asyncio.create_task(task_func(args, parameters, **task_args))
                 for p in range(0, n_p)]
        results += await asyncio.gather(*tasks)
        await teardown_func(task_args)
        parameters.update_batch()
        n -= n_p
    elapsed = time.monotonic()-st
    return elapsed, results


async def sliding_window_executor(args, task_args, parameters,
                              global_parameters=None, last=None, want_results=True, 
                              setup_func=setup, teardown_func=teardown,
                              task_func=default_task, result_queue=None, request_cb=None):
    if setup_func is not None:
        await setup_func(task_args)
    try:
        tasks = set()

        parameters['requests-count'] = 0
        parameters['task-wait-dept'] = 0
        parameters['ok'] = 0
        parameters['nok'] = 0
        parameters['exc'] = 0
        req_count = 0

        task_func = task_func or default_task
        start = time.monotonic()

        # Start initial concurrency number of tasks
        stop = parameters.get('stop', 0)
        rps = parameters.get('requests-per-second', 0)
        concurrency = parameters.get('concurrency', 1)
        for _ in range(0, concurrency):
            if req_count%concurrency == 0:
                parameters.update_batch() # Update batched parameters
                # TODO: Is this guaranteed to be executed directly in relation
                #       to the call to task_func below?
            tasks.add(asyncio.create_task(task_func(args, parameters, **task_args)))
            if rps > 0:
                await asyncio.sleep(1/(rps/concurrency))
            req_count += 1
            if stop > 0 and req_count >= stop:
                break
        # TODO: Must find a better way to handle close_flag
        close_flag = 0
        results = []
        n = 0
        new_task_delays = []
        while not close_flag and len(tasks) > 0:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            stop = parameters.get('stop', 0)
            rps = parameters.get('requests-per-second', 0)
            add_to_metrics = parameters.get('add_to_metrics', False)
            concurrency = parameters.get('concurrency', 1)
            for d in done:
                if global_parameters:
                    global_parameters['requests-count'] += 1
                result = await d
                if request_cb:
                    request_cb(result)
                if want_results:
                    results.append(result)
                _rid, rstatus, _rcode, _rresult, rtime = result
                if last:
                    last['result'] = last_result = (datetime.now().isoformat(), result)
                    if rstatus == 'ok':
                        parameters['ok'] += 1
                        last['success'] = last_result
                    elif rstatus == 'nok':
                        parameters['nok'] += 1
                        last['error'] = last_result
                    else:
                        parameters['exc'] += 1
                        last_exc = last_result
                if add_to_metrics and result_queue is not None:
                    # Push results to metrics_handler
                    await result_queue.put((time.time(), result))

                d = 1/(rps/concurrency)-rtime if rps>0 else 0
                if d < 0:
                    # This means that concurrency may need to be increased
                    parameters['task-wait-dept'] -= d
                new_task_delays.append(d)
            # Start tasks in available slots (if any)
            for _ in range(concurrency-len(tasks)):
                if stop == 0 or req_count < stop:
                    d = new_task_delays.pop(0) if new_task_delays else 1/(rps/concurrency)
                    async def new_task():
                        if d > 0:
                            await asyncio.sleep(d)
                        return await task_func(args, parameters, **task_args)
                    if req_count%concurrency == 0:
                        parameters.update_batch() # Update batched parameters
                        # TODO: Is this guaranteed to be executed directly in relation
                        #       to the call to task_func below?
                    tasks.add(asyncio.create_task(new_task()))
                    req_count += 1
            if global_parameters:
                close_flag = global_parameters['close_flag']
    except asyncio.CancelledError:
        # TODO: More graceful shutdown and collect results?
        pass
    except Exception as e:
        print("EXCEPTION", e)
        # Print traceback
        print(traceback.format_exc())
        raise e
    finally:
        elapsed = time.monotonic()-start
        for t in tasks:
            t.cancel()
        if teardown_func is not None:
            await teardown_func(task_args)
    return elapsed, results


async def single_request(args, task_args, parameters, setup_func=setup, 
                         teardown_func=teardown, task=default_task):
    # Setup connection pool
    await setup_func(task_args)
    result = await task(args, parameters, **task_args)
    # Cleanup connection pool
    await teardown_func(args)
    return result



###############################################################################
#  RUNNER FUNCTIONS
###############################################################################
#

def do_test(args, task_args, parameters, want_results=True, task_func=None, request_cb=None):
    set_flags(args, task_args)
    elapsed, results = asyncio.run(
        sliding_window_executor(args, task_args, parameters, want_results=want_results, task_func=task_func, request_cb=request_cb))
    if want_results:
        if args.v:
            pprint(results)

        # TODO: Refactor analysis of the results and want_results. No stats is returned when want_results is False.
        count, total, count_wrong, count_exc = calc_average(results)

        return elapsed, count, total, count_wrong, count_exc, results
    return elapsed


#
# Run test in subprocess to ensure proper isolation/cleanup between test iterations.
#
def run_test_in_subprocess(args, test_func, task_args, parameters, task_func=None, do_print=False):
    task_args = copy.deepcopy(task_args)
    parameters = copy.deepcopy(parameters)
    result = test_func(args, task_args, parameters, task_func=task_func)
    elapsed, count, total, count_wrong, count_exc, results = result
    if count:
        average = total/count
    else:
        average = -1.0
    if do_print:
        op = task_args['op'].upper()
        n_p = parameters['concurrency']
        print(f'{op:<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}', flush=True)
    return elapsed, count, total, average, count_wrong, count_exc, results


def run_tests(args, testcases, tests, parameters, no_requests, max_concurrency, task_func=None, do_print=False):
    no_requests = args.n or no_requests

    max_concurrency = min(max_concurrency, no_requests)
    if args.w:
        max_concurrency = min(args.w, no_requests)

    if not args.s:
        n_ps = [n for n in np_gen(max_concurrency)]
    else:
        n_ps = list(map(int, args.s.split(',')))

    print()
    parameters.update_cmdline(args.p)
    parameters['stop'] = no_requests
    if '__info' in tests:
        info = tests['__info']
        if 'name' in info:
            name = format_parameters(parameters, info['name'], update=False)
            if args.highlight:
                print(ansi.BOLD, end='')
                print(ansi.REVERSE, end='')
            print(f'==== {name} ====')
            if args.highlight:
                print(ansi.RST, end='')
            print()

    results = []
    for r, n_p in enumerate(n_ps):
        if args.highlight and r % 2 == 1:
            print(ansi.DIM, end='')
        for op in testcases:
            task_args = tests[op]
            # TODO: Should host be in task_args? parameters is better?
            task_args['host'] = args.host
            parameters['concurrency'] = n_p
            results.append((op, no_requests, n_p, run_test_in_subprocess(
                args, do_test, task_args, parameters, task_func=task_func, do_print=do_print)))
        if args.highlight and r % 2 == 1:
            print(ansi.RST, end='')
    if args.o:
        open(args.o, "w").write(json.dumps(results))
    if args.html:
        dirs, fname = path.split(sys.argv[0])
        name, ext = path.splitext(fname)
        oname = f'{name}-{args.n}-{args.p}-{args.w}-{args.s}.html'
        oname = replace_chars(oname, '_', ',=')
        generate_html(oname, '', oname, results)
        print()
        print("Wrote html file:", oname)
        if args.open:
            import webbrowser
            webbrowser.open(f'file://{path.join(os.getcwd(), oname)}')
    return results


def run_single_test(args, tc, tests, parameters, task_func=None):
    n = args.n or 1
    n_p = args.w or 1
    task_args = tests[tc]
    task_args['host'] = args.host
    if args.keep_state:
        parameters.load_state()
    parameters.update_cmdline(args.p)
    if args.echo:
        print(str(parameters))
    elapsed, count, total, count_wrong, count_exc, results = do_test(
        args, task_args, parameters, task_func=task_func)
    if count:
        average = total/count
    else:
        average = -1
    if args.echo:
        print(str(parameters))
    if args.keep_state:
        parameters.save_state()
    if not args.q:
        print()
        print("Total time:         ", elapsed)
        print("Count OK:           ", count)
        print("Per second:         ", count/elapsed)
        print("Average per request:", average)
        print("Wrong status:       ", count_wrong)
        print("Exceptions:         ", count_exc)

    return elapsed, count, total, average, count_wrong, count_exc, results

#
# Used in legacy tests
#
def run_test(args, tests, parameters, n=500, max_p=40, task_func=None, do_print=True):
    if args.cmd == ['clean']:
        parameters['stop'] = 1
        parameters['concurrency'] = 1
        run_single_test(args, 'clean', tests, parameters)
    else:
        tc = []
        for c in args.cmd:
            if c == 'crud':
                tc += ['create', 'read', 'update', 'delete']
            elif c == 'cud':
                tc += ['create', 'update', 'delete']
            else:
                tc.append(c)

        if args.single:
            run_single_test(args, tc[0], tests, parameters, task_func=task_func)
        else:
            run_tests(args, tc, tests, parameters, n, max_p, task_func, do_print=do_print)
