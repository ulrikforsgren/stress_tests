#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import copy
import json
import pprint as pp
import random
import re
import time
from xmlrpc.client import boolean

from .restconf_api import REQ_DISPATCH, setup, teardown, restconf_request

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


def parseArgs(args, extra_actions=[]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str,
                        help='host[:port]',
                        default='localhost:8080')
    parser.add_argument('cmd', nargs='+', choices=['clean', 'create', 'read',
                                                   'update', 'delete', 'crud', 'cud']
                        + extra_actions)
    parser.add_argument("-n", required=False, type=int,
                        help='Number of total requests.')
    parser.add_argument("-o", required=False, action='store_true', default=False,
                        help="Run only one test instead of a sequence of tests")
    parser.add_argument("-b", required=False, type=int,
                        help='Max batch size. Starting 1, 2, 5, .., max')
    parser.add_argument("-s", required=False, type=str,
                        help='Batch size(s) comma sepated.')
    parser.add_argument("-p", required=False, type=str, action='append',
                        help='Alter parameters.')
    parser.add_argument("--single", required=False, action='store_true',
                        default=False, help='Run single test.')
    parser.add_argument("--no-networking", required=False, action='store_true',
                        default=False, help='Commit with no-networking.')
    parser.add_argument("--commit-queue", required=False, action='store_true',
                        default=False, help='Commit to commit-queue.')
    parser.add_argument("-q", required=False, action='store_true',
                        default=False, help='Silent mode.')
    parser.add_argument("-v", required=False, action='store_true',
                        default=False, help='Verbose mode. Show result of each request.')
    parser.add_argument("--json", required=False, type=str,
                        help='Output result in json format to file.')
    parser.add_argument("--highlight", required=False, action='store_true',
                        default=False, help='Highlight output to make it more readable.')
    return parser.parse_args(args)


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


class Sequence:
    def __init__(self, n):
        self.n = n

    def set(self, n):
        self.n = n

    def __str__(self):
        s = str(self.n)
        self.update_str()
        return s

    def update_str(self):
        self.n += 1

    def update_request(self):
        pass

    def update_batch(self):
        pass

    def __copy__(self):
        return self.__class__(self.n)

    def reset(self):
        self.n = 0

    def current(self):
        return f'Sequence(n={self.n})'


class SequenceRequest(Sequence):
    def __init__(self, n, wrap=None):
        super(SequenceRequest, self).__init__(n)
        self.wrap = wrap

    def update_str(self):
        pass

    def update_request(self):
        self.n += 1
        if self.wrap is not None:
            self.n = self.n % self.wrap

    def current(self):
        return f'SequenceRequest(n={self.n}, wrap={self.wrap})'


class SequenceBatch(Sequence):
    def __init__(self, n):
        super(SequenceBatch, self).__init__(n)

    def update_str(self):
        pass

    def update_batch(self):
        self.n += 1


class RandomValue(Sequence):
    def __init__(self, lower, upper):
        super(RandomValue, self).__init__(0)
        self.lower = lower
        self.upper = upper

    def __str__(self):
        return str(random.randint(self.lower, self.upper))

    def current(self):
        return f'RandomValue({self.lower}..{self.upper})'


"""
class Parameters makes it possible provide parameters in the form of <<x>> in
url and data strings.
"""


class Parameters(dict):
    def set(self, d):
        for k, v in d.items():
            if k in self:
                ov = self[k]
                if isinstance(ov, Sequence):
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
            if isinstance(v, Sequence):
                v.reset()


def number_of_open_connections(conn):
    if len(conn._conns):
        key = list(conn._conns.keys())[0]  # Assuming only one key
        return len(conn._conns[key])
    else:
        return 0


async def setup_connections(n_p, client, host):
    # Run n_p tasks in parallel to force client to setup n_p connections
    # This to remove the initial connection time from the results
    tasks = [asyncio.create_task(setup_task(client, host))
             for p in range(0, n_p)]
    await asyncio.gather(*tasks)
    # await asyncio.wait(tasks)


#
# n_p connections are setup for each batch then closed
#
async def stress_requests_batch(n, n_p, setup, teardown, task, args):
    results = []
    while n > 0:  # Execute requests in batches of n_p in parellel.
        if n < n_p:
            n_p = n
        await setup(args)
        st = time.monotonic()
        tasks = [asyncio.create_task(task(**args))
                 for p in range(0, n_p)]
        results += await asyncio.gather(*tasks)
        await teardown(args)
        if 'parameters' in args:
            args['parameters'].update_batch()
        n -= n_p
    elapsed = time.monotonic()-st
    return elapsed, results

#
# n_p connections are setup and new requests and sent as a connection
# becomes available.
#


async def stress_requests_window(n, n_p, setup, teardown, task, args):
    results = []
    tasks = set()

    await setup(args)
    conn = args['client']._connector
    await conn.setup_pool_connections(conn, args['host'], n_p)

    st = time.monotonic()
    for _ in range(0, min(n, n_p)):
        tasks.add(asyncio.create_task(task(**args)))
    n -= min(n, n_p)  # Started initial tasks

    while len(tasks) > 0:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            result = await d
            results.append(result)
        a = n_p-len(pending)  # Calculate number of free task slots
        tasks_to_start = min(a, n)
        for _ in range(0, tasks_to_start):  # Start tasks in available slots
            pending.add(asyncio.create_task(task(**args)))
        n -= tasks_to_start
        tasks = pending
    elapsed = time.monotonic()-st
    await teardown(args)
    return elapsed, results


async def single_request(args, setup=setup, teardown=teardown):
    # Setup connection pool
    await setup(args)
    result = await default_task(**args)
    # Cleanup connection pool
    await teardown(args)
    return result


async def setup_task(client, host):
    # Reading an arbitrary leaf to force the client to setup a connection.
    url = '/tailf-ncs:devices/global-settings/read-timeout'
    op = 'read'
    st = time.monotonic()
    resp = await restconf_request(client,
                                  host,
                                  op,
                                  url)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)


re_sub = re.compile(r'<<(\w+)>>')


async def default_task(client=None, parameters=Parameters(), host='', op='',
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
    if 'params' in req:
        req['params'].update(flags)
    req['params'] = flags


def do_test(args, n, n_p, req, task=None):
    task = task or default_task
    set_flags(args, req)
    elapsed, results = asyncio.run(
        stress_requests_window(n, n_p, setup, teardown, task, req))

    if args.v:
        pprint(results)

    count, total, count_wrong, count_exc = calc_average(results)

    return elapsed, count, total, count_wrong, count_exc, results


#
# Run test in subprocess to ensure proper cleanup between test iterations.
#
def run_test_in_subprocess(args, func, n, n_p, req, task=None, do_print=False):
    req = copy.deepcopy(req)
    result = func(args, n, n_p, req, task)
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


def run_tests(which, args, tests, n, max_p, task=None, do_print=False):
    n = args.n or n

    max_p = min(max_p, n)
    if args.b:
        max_p = min(args.b, n)

    if not args.s:
        n_ps = [n for n in np_gen(max_p)]
    else:
        n_ps = list(map(int, args.s.split(',')))

    print()
    if '__info' in tests:
        info = tests['__info']
        if 'name' in info:
            if 'parameters' in info:
                params = info['parameters']
                params.update_cmdline(args.p)
            else:
                params = {}
            name = info['name'].format_map(params)
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
            if 'parameters' in req:
                req['parameters'].update_cmdline(args.p)
            results.append((op, n, n_p, run_test_in_subprocess(
                args, do_test, n, n_p, req, task, do_print)))
        if args.highlight and r % 2 == 1:
            print(ansi.RST, end='')
    if args.json:
        open(args.json, "w").write(json.dumps(results))
    return results


def run_crud_tests(args, tests, n, max_p, task=None, do_print=False):
    return run_tests(['create', 'read', 'update', 'delete'], args, tests, n, max_p, task, do_print)


def run_single_test(tc, args, tests, task=None):
    n = args.n or 1
    n_p = args.b or 1
    req = tests[tc]
    req['host'] = args.host
    elapsed, count, total, count_wrong, count_exc, results = do_test(
        args, n, n_p, req, task)
    if count:
        average = total/count
    else:
        average = -1

    if not args.q:
        print()
        print("Total time:         ", elapsed)
        print("Count OK:           ", count)
        print("Per second:         ", count/elapsed)
        print("Average per request:", average)
        print("Wrong status:       ", count_wrong)
        print("Exceptions:         ", count_exc)

    return (args.cmd, n, n_p, (elapsed, count, total, average, count_wrong, count_exc, results))


def run_test(args, tests, n=500, max_p=50, task=None, do_print=True):
    if args.cmd == 'clean':
        run_single_test('clean', args, tests)
    else:
        tc = []
        for c in args.cmd:
            if c == 'crud':
                tc += ['create', 'read', 'update', 'delete']
            elif c == 'cud':
                tc += ['create', 'update', 'delete']
            else:
                tc.append(c)

        if args.o:
            run_single_test(tc[0], args, tests, task=task)
        else:
            run_tests(tc, args, tests, n, max_p, task, do_print)
