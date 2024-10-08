#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import copy
import json
import os
import os.path as path
import pprint as pp
import random
import re
import rstr
import sys
import time
from xmlrpc.client import boolean

from .restconf_api import REQ_DISPATCH, setup, teardown, restconf_request
from .gen_chart import generate_html


HOST = 'localhost'
PORT = 8080

pprint = pp.PrettyPrinter(indent=4).pprint


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


def parseArgs(args=None, extra_actions=[]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str,
                        help='host[:port]',
                        default='localhost:8080')
    parser.add_argument('cmd', nargs='+', choices=['clean', 'create', 'read',
                                                   'update', 'delete', 'crud', 'cud']
                        + extra_actions)
    parser.add_argument("--dry-run", required=False, action='store_true', default=False,
                        help="Run sequence but do not send request over network.")
    parser.add_argument("--echo", required=False, action='store_true', default=False,
                        help="Echo request to console.")
    parser.add_argument("--keep-state", required=False, action='store_true', default=False,
                        help="Loads state if state files exist and saves after run.")
    parser.add_argument("--single", required=False, action='store_true', default=False,
                        help="Run one iteration of one operation with one windows size.")
    parser.add_argument("-n", required=False, type=int,
                        help='Number of total requests.')
    parser.add_argument("-w", required=False, type=int, default=40,
                        help='Max window size. Starting 1, 2, 5, .., max')
    parser.add_argument("-s", required=False, type=str,
                        help='Window size(s) comma sepated.')
    parser.add_argument("-p", required=False, type=str, action='append',
                        help='Alter parameters.')
    parser.add_argument("--no-networking", required=False, action='store_true',
                        default=False, help='Commit with no-networking.')
    parser.add_argument("--commit-queue", required=False, action='store_true',
                        default=False, help='Commit to commit-queue.')
    parser.add_argument("-q", required=False, action='store_true',
                        default=False, help='Silent mode.')
    parser.add_argument("-v", required=False, action='store_true',
                        default=False, help='Verbose mode. Show result of each request.')
    parser.add_argument("-o", required=False, type=str,
                        help='Output result in json format to file.')
    parser.add_argument("--html", required=False, action='store_true',
                        help='Output results as graphs in html.')
    parser.add_argument("--open", required=False, action='store_true',
                        help='Open generated html.')
    parser.add_argument("--highlight", required=False, action='store_true',
                        default=False, help='Highlight output to make it more readable.')
    return parser.parse_args(args)


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


#
# Classes to inject dynamic values for stressing requests.
#
"""
 Inject paramaters that can be update on multiple levels when iterating:
  - each usage/referenced (Sequence)
  - url and data (SequenceLine)
  - each batch of requests (SequenceBatch)

Example:

parameters = Parameters({
    "id": SequenceRequest(0),
    "vid": SequenceLine(0),
    "group": SequenceBatch(0)
})
"""

class Parameter:
    def __init__(self, keep_state=False):
        self.keep_state = keep_state

    def getstate(self):
        raise NotImplementedError()

    def setstate(self, state):
        raise NotImplementedError()

    def set(self, *args):
        pass

    def update_str(self):
        pass

    def update_request(self):
        pass

    def update_batch(self):
        pass

    def reset(self):
        pass

    def current(self):
        return None
    

class Sequence(Parameter):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(keep_state)
        self.n = n
        self.wrap = wrap

    def getstate(self):
        return self.n

    def setstate(self, state):
        self.n = state

    def set(self, n):
        if isinstance(n, str):
            n = int(n)
        self.n = n

    def __str__(self):
        s = str(self.n)
        return s

    def update_str(self):
        s = str(self)
        self.n += 1
        if self.wrap is not None:
            self.n = self.n % self.wrap
        return s

    def update_request(self):
        pass

    def update_batch(self):
        pass

    def __deepcopy__(self, memo):
        return self.__class__(self.n)

    def reset(self):
        self.n = 0

    def current(self):
        return f'Sequence(n={self.n})'


class SequenceRequest(Sequence):
    def __init__(self, n, wrap=None, keep_state=False):
        super().__init__(n, wrap, keep_state)

    def update_str(self):
        return str(self)

    def update_request(self):
        self.n += 1
        if self.wrap is not None:
            self.n = self.n % self.wrap

    def current(self):
        return f'SequenceRequest(n={self.n}, wrap={self.wrap})'


class SequenceRequestRandomized(SequenceRequest):
    def __init__(self, n, wrap=None, seed=None, keep_state=False):
        super().__init__(0, wrap, keep_state)
        self.length = n
        self.seed = seed
        self.rnd = random.Random(seed)
        self.sequence = list(range(self.length))
        self.rnd.shuffle(self.sequence)

    def getstate(self):
        return (self.n, self.sequence)

    def setstate(self, state):
        # NOTE: This will restore the sequence as a tuple and will be immutable.
        # NOTE: The random generator state is not restored.
        self.n, self.sequence = state

    def __str__(self):
        try:
            return str(self.sequence[self.n])
        except IndexError:
            return "No more values ({self.n})"
    
    def update_str(self):
        return str(self.sequence[self.n])

    def current(self):
        return f'SequenceRequestRandomized(n={self.n}, wrap={self.wrap})'

class SequenceBatch(Sequence):
    def __init__(self, n, keep_state=False):
        super().__init__(n, keep_state)

    def update_str(self):
        pass

    def update_batch(self):
        self.n += 1


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

    def __deepcopy__(self, memo):
        return self.__class__(self.lower, self.upper, self.seed)
    
    def __str__(self):
        return str(random.randint(self.lower, self.upper))

    def current(self):
        return f'RandomValue({self.lower}..{self.upper})'


class RandomValueRequest(RandomParameter):
    def __init__(self, lower, upper, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.lower = lower
        self.upper = upper
        self.n = random.randint(self.lower, self.upper)

    def __deepcopy__(self, memo):
        return self.__class__(self.lower, self.upper, self.seed)
    
    def __str__(self):
        return str(self.n)

    def update_request(self):
        self.n = random.randint(self.lower, self.upper)

    def current(self):
        return f'RandomValueRequest({self.lower}..{self.upper})'


class RandomString(RandomParameter):
    def __init__(self, length, seed=None, keep_state=False):
        super().__init__(seed, keep_state)
        self.length = length
        self.rstr = rstr.Rstr(self.rnd)
        self.value = self.rstr.letters(self.length)

    def getstate(self):
        return (super().getstate(), self.value)

    def setstate(self, state):
        state, self.value = state
        super().setstate(state)

    def set(self, n):
        # NOTE: This is a hack to allow changing the length of the string, but it breaks the pseudo random sequence.
        if isinstance(n, str):
            n = int(n)
        self.length = n

    def update_str(self):
        s = self.value
        self.value = self.rstr.letters(self.length)
        return s

    def __deepcopy__(self, memo):
        return self.__class__(self.length, self.seed)

    def __str__(self):
        return self.value

    def current(self):
        return f'RandomString(length={self.length})'


class ContextValue(Parameter):
    def __init__(self, values, format, attr):
        super(ContextValue, self).__init__()
        self.values = values
        self.format = format
        self.attr = attr

    def __copy__(self):
        return self.__class__(self.values, self.format)
    
    def __str__(self):
        raise NotImplementedError("ContextValue should not be converted to string")
        
    def get(self, parameters, key):
        try:
            name = format_parameters(parameters, self.format)
            inst = self.values[name]
            return inst[self.attr]
        except Exception as e:
            print(f'ERROR: {e}')
            print(f'ERROR: {self.format}')
            return "ERROR"

    def current(self):
        return f'ContextValue(key={self.key})'


class Calc:
    def __init__(self, key, wrap, mul, add):
        self.key = key
        self.wrap = wrap
        self.mul = mul
        self.add = add
    def val(self, parameters):
        i = parameters[self.key].n
        o = i//self.wrap*self.mul+self.add
        return str(o)
    
    
"""
class Parameters makes it possible provide parameters in the form of <<x>> in
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
            if isinstance(v, Sequence):
                v.update_request()

    def update_batch(self):
        for v in self.values():
            if isinstance(v, Sequence):
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



def number_of_open_connections(conn):
    if len(conn._conns):
        key = list(conn._conns.keys())[0]  # Assuming only one key
        return len(conn._conns[key])
    else:
        return 0


#async def setup_connections(args, n_p, client, host):
#    # Run n_p tasks in parallel to force client to setup n_p connections
#    # This to remove the initial connection time from the results
#    tasks = [asyncio.create_task(setup_task(args, client, host))
#             for p in range(0, n_p)]
#    await asyncio.gather(*tasks)
#    # await asyncio.wait(tasks)


#
# n_p connections are setup for each batch then closed
#
async def stress_requests_batch(args, n, n_p, setup, teardown, task, req, parameters):
    results = []
    while n > 0:  # Execute requests in batches of n_p in parellel.
        if n < n_p:
            n_p = n
        await setup(req)
        st = time.monotonic()
        tasks = [asyncio.create_task(task(args, parameters, **req))
                 for p in range(0, n_p)]
        results += await asyncio.gather(*tasks)
        await teardown(req)
        parameters.update_batch()
        n -= n_p
    elapsed = time.monotonic()-st
    return elapsed, results

#
# n_p connections are setup and new requests and sent as a connection
# becomes available.
#


async def stress_requests_window(args, n, n_p, setup, teardown, task, task_args, parameters, request_cb=None):
    results = []
    tasks = set()
    await setup(task_args)
    conn = task_args['client']._connector
    if not args.dry_run:
        await conn.setup_pool_connections(conn, task_args['host'], n_p)

    st = time.monotonic()
    for _ in range(0, min(n, n_p)):
        tasks.add(asyncio.create_task(task(args, parameters, **task_args)))
    n -= min(n, n_p)  # Started initial tasks

    while len(tasks) > 0:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            result = await d
            results.append(result)
            if request_cb:
                request_cb(result)

        a = n_p-len(pending)  # Calculate number of free task slots
        tasks_to_start = min(a, n)
        for _ in range(0, tasks_to_start):  # Start tasks in available slots
            pending.add(asyncio.create_task(task(args, parameters, **task_args)))
        n -= tasks_to_start
        tasks = pending
    elapsed = time.monotonic()-st
    await teardown(task_args)
    return elapsed, results


async def single_request(args, task_args, parameters, setup=setup, teardown=teardown):
    # Setup connection pool
    await setup(task_args)
    result = await default_task(args, parameters, **task_args)
    # Cleanup connection pool
    await teardown(args)
    return result


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


def format_parameters(parameters, string):
    re_sub = re.compile(r'<<(\w+)>>')
    def update_str(parameters, key):
        p = parameters[key]
        if isinstance(p, Parameter):
            return p.update_str()
        if isinstance(p, Calc):
            return p.val(parameters)
        return str(p)
    return re_sub.sub(lambda m: update_str(parameters, m.group(1)), string)

async def default_task(args, parameters, client=None, host='', op='',
                       resource='', data='', resource_type='data', query_parameters=None):

    resource = format_parameters(parameters, resource)
    if isinstance(data, dict):
        data = json.dumps(data)
    data = format_parameters(parameters, data)
    parameters.update_request()
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

#
# Assert that all results are "ok"
#


def assert_ok(results):
    assertion = True
    for r in results:
        rid, res, *rest = r
        if res == 'ok':
            pass
        elif res == 'nok':
            st, data, el = rest
            print(
                f"ERROR: wrong status returned {rid}: {st} != {expected_status}")
            print(data)
            assertion = False
        elif res == 'exception':
            exc, = rest
            print(f"ERROR: exception {rid}: {exc}")
            assertion = False
        else:
            raise Exception(f"Invalid return result {rid}: {res}")
    assert assertion


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


def set_flags(args, req):
    flags = {}
    if args.no_networking:
        flags['no-networking'] = 'true'
    if args.commit_queue:
        flags['commit-queue'] = 'sync'
    if 'query_parameters' in req:
        req['query_parameters'].update(flags)
    req['query_parameters'] = flags


def do_test(args, n, n_p, req, parameters, task=None, request_cb=None):
    task = task or default_task
    set_flags(args, req)
    elapsed, results = asyncio.run(
        stress_requests_window(args, n, n_p, setup, teardown, task, req, parameters, request_cb=request_cb))
    if args.v:
        pprint(results)

    count, total, count_wrong, count_exc = calc_average(results)

    return elapsed, count, total, count_wrong, count_exc, results


#
# Run test in subprocess to ensure proper cleanup between test iterations.
#
def run_test_in_subprocess(args, func, n, n_p, req, parameters, task=None, do_print=False):
    req = copy.deepcopy(req)
    parameters = copy.deepcopy(parameters)
    result = func(args, n, n_p, req, parameters, task)
    elapsed, count, total, count_wrong, count_exc, results = result
    if count:
        average = total/count
    else:
        average = -1.0
    if do_print:
        op = req['op'].upper()
        print(f'{op:<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}', flush=True)
    return elapsed, count, total, average, count_wrong, count_exc, results


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


def run_tests(args, which, tests, parameters, n, max_p, task=None, do_print=False):
    n = args.n or n

    max_p = min(max_p, n)
    if args.w:
        max_p = min(args.w, n)

    if not args.s:
        n_ps = [n for n in np_gen(max_p)]
    else:
        n_ps = list(map(int, args.s.split(',')))

    print()
    parameters.update_cmdline(args.p)
    if '__info' in tests:
        info = tests['__info']
        if 'name' in info:
            name = format_parameters(parameters, info['name'])
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
        for op in which:
            req = tests[op]
            req['host'] = args.host
            results.append((op, n, n_p, run_test_in_subprocess(
                args, do_test, n, n_p, req, parameters, task, do_print)))
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


def run_crud_tests(args, tests, parameters, n, max_p, task=None, do_print=False):
    return run_tests(['create', 'read', 'update', 'delete'], args, tests, n, max_p, task, do_print)


def run_single_test(args, tc, tests, parameters, task=None):
    n = args.n or 1
    n_p = args.w or 1
    req = tests[tc]
    req['host'] = args.host
    if args.keep_state:
        parameters.load_state()
    parameters.update_cmdline(args.p)
    if args.echo:
        print(str(parameters))
    elapsed, count, total, count_wrong, count_exc, results = do_test(
        args, n, n_p, req, parameters, task)
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

    return (args.cmd, n, n_p, (elapsed, count, total, average, count_wrong, count_exc, results))


def run_test(args, tests, parameters, n=500, max_p=50, task=None, do_print=True):
    if args.cmd == 'clean':
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
            run_single_test(args, tc[0], tests, parameters, task=task)
        else:
            run_tests(args, tc, tests, parameters, n, max_p, task, do_print)
