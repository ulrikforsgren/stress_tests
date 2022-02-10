#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import json
from multiprocessing import Pool
import pprint as pp
import random
import time

from restconf_api import REQ_DISPATCH, setup, teardown, restconf_request

HOST='localhost'
PORT=8080

pprint = pp.PrettyPrinter(indent=4).pprint


def parseArgs(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str,
                        help='host[:port]',
                        default='localhost:8080')
    parser.add_argument('cmd', choices=['clean', 'create', 'read',
                                        'update', 'delete', 'crud'])
    parser.add_argument("-n", required=False, type=int)
    parser.add_argument("-p", required=False, type=int)
    parser.add_argument("-s", required=False, type=str)
    parser.add_argument("-v", required=False, action='store_true', default=False)
    parser.add_argument("--json", required=False, type=str)
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

# class Parameters makes it possible provide parameters in the form of {x} in
# url and data strings.
"""
 The use of format_map is neat, but makes it harder to provide data as
 a dict and convert to json, as it is a teadious work escape curly braces.
 The escaping also makes it harder to see if the json is correctly formatted.
"""
class Parameters(dict):
    def __missing__(self, key):
        return "{" + key + "}"
    def update_request(self):
        for v in self.values():
            if isinstance(v, Sequence):
                v.update_request()
    def update_batch(self):
        for v in self.values():
            if isinstance(v, Sequence):
                v.update_batch()


#
# n_p connections are setup and reused for the whole test.
#
async def stress_requests(n, n_p, setup, teardown, task, args):
    results = []
    await setup(args)
    while n>0: # Execute requests in batches of n_p in parellel.
        if n<n_p: n_p = n
        tasks = [ asyncio.create_task(task(**args))
                  for p in range(0,n_p)]
        results += await asyncio.gather(*tasks)
        if 'parameters' in args:
            args['parameters'].update_batch()
        n -= n_p
    await teardown(args)
    return results

#
# n_p connections are setup for each batch then closed
#
async def stress_requests_batch(n, n_p, setup, teardown, task, args):
    results = []
    while n>0: # Execute requests in batches of n_p in parellel.
        if n<n_p: n_p = n
        await setup(args)
        tasks = [ asyncio.create_task(task(**args))
                  for p in range(0,n_p)]
        results += await asyncio.gather(*tasks)
        await teardown(args)
        if 'parameters' in args:
            args['parameters'].update_batch()
        n -= n_p
    return results

#
# n_p connections are setup and new requests and sent as a connection
# becomes available.
#
async def stress_requests_stream(n, n_p, setup, teardown, task, args):
    results = []
    tasks = set()

    await setup(args)

    for _ in range(0, min(n, n_p)):
        tasks.add(asyncio.create_task(task(**args)))
    n -= min(n, n_p) # Started initial tasks

    while len(tasks)>0:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            result = await d
            results.append(result)
        a = n_p-len(pending)  # Calculate number of free task slots
        tasks_to_start = min(a, n)
        for _ in range(0, tasks_to_start): # Start tasks in available slots
            pending.add(asyncio.create_task(task(**args)))
        n -= tasks_to_start
        tasks = pending

    await teardown(args)
    return results

async def single_request(args, setup=setup, teardown=teardown):
    # Setup connection pool
    await setup(args)
    result = await default_task(**args)
    # Cleanup connection pool
    await teardown(args)
    return result

async def default_task(client=None, parameters=Parameters(), host='', op='',
                       url='', data='', resource_type='data'):
    url = url.format_map(parameters)
    data = data.format_map(parameters)
    parameters.update_request()
    st = time.monotonic()
    resp = await restconf_request(client,
                                  host,
                                  op,
                                  url,
                                  data,
                                  resource_type)
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
            st,data,el = rest
            print(f"ERROR: wrong status returned {rid}: {st} != {expected_status}")
            print(data)
            assertion = False
        elif res == 'exception':
            exc, = rest
            print(f"ERROR: exception {rid}: {exc}")
            assertion = False
        else:
            raise Exception(f"Invalid return result {rid}: {res}")
    assert(assertion)


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
            st,_,el = rest
            total_ok += el
            count_ok += 1
        elif res == 'nok':
            count_wrong += 1
        elif res == 'exception':
            count_exc += 1

    return count_ok, total_ok, count_wrong, count_exc


def do_test(args, n, n_p, req, task=None):
    task = task or default_task
    st = time.monotonic()
    results = asyncio.run(stress_requests(n, n_p, setup, teardown, task, req))
    elapsed = time.monotonic()-st

    if args.v:
        pprint(results)

    count, total, count_wrong, count_exc = calc_average(results)

    return elapsed, count, total, count_wrong, count_exc, results

#
# Run test in subprocess to ensure proper cleanup between test iterations.
#
def run_test_in_subprocess(args, func, n, n_p, req, task=None, do_print=False):
    with Pool(processes=1) as pool:
        res = pool.apply(func, (args, n, n_p, req, task))
        elapsed, count, total, count_wrong, count_exc, results = res
        if count:
            average=total/count
        else:
            average = -1
        if do_print:
            op = req['op'].upper()
            print(f'{op:<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}')
        pool.close()
        return elapsed, count, total, average, count_wrong, count_exc, results

def np_gen(max_p):
    n = 1
    m = 1
    while n<=max_p:
        for s in [1,2,5]:
            np = s*m
            if np<max_p:
                yield np
            else:
                yield max_p
                return
        m *= 10

def run_crud_tests(args, tests, n, max_p, task=None, do_print=False):
    n = args.n or n

    max_p = min(max_p, n)
    if args.p:
        max_p = min(args.p, n)

    if not args.s:
        n_ps = [ n for n in np_gen(max_p) ]
    else:
        n_ps = [ int(s) for s in args.s.split(',')]

    results = []
    for n_p in n_ps:
        for op in ['create', 'read', 'update', 'delete']:
            req = tests[op]
            req['host'] = args.host
            results.append((op, n, n_p, run_test_in_subprocess(args, do_test, n, n_p, req, task, do_print)))
    if args.json:
        open(args.json, "w").write(json.dumps(results))
    return results


def run_single_test(args, tests, task=None):
    n = args.n or 1
    n_p = args.p or 1
    req = tests[args.cmd]
    req['host'] = args.host
    elapsed, count, total, count_wrong, count_exc, results = do_test(args, n, n_p, req, task)
    if count:
        average=total/count
    else:
        average = -1

    print("Total time:         ", elapsed)
    print("Count OK:           ", count)
    print("Per second:         ", count/elapsed)
    print("Average per request:", average)
    print("Wrong status:       ", count_wrong)
    print("Exceptions:         ", count_exc)

    return (args.cmd, n, n_p, (elapsed, count, total, average, count_wrong, count_exc, results))

