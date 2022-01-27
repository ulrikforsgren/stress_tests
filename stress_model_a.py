#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
from base64 import b64encode
import functools
import pprint as pp
import sys
import time

import aiohttp

HOST='localhost'
PORT=8080

COMMIT_PARAMS = '' # '?commit-queue=async&commit-queue-error-option=stop-on-error'
#
# TODO:
#  - ArgParse
#  - Create service(s) from file
#  - Control commit flags
#  - Provide host and port
#  - Modularize code and make tests as function for easier automation.

pprint = pp.PrettyPrinter(indent=4).pprint

#
# Classes to inject dynamic values for stressing requests.
#
class Sequence:
    def __init__(self, n, ffunc=None):
        self.n = n
        self.ffunc = ffunc or (lambda s: str(s))
    def __str__(self):
        s = self.ffunc(self.n)
        self.update_str()
        return s
    def update_str(self):
        self.n += 1
    def update_request(self):
        pass
    def update_batch(self):
        pass

class SequenceRequest(Sequence):
    def __init__(self, n, ffunc=None):
        super(SequenceRequest, self).__init__(n, ffunc)
    def update_str(self):
        pass
    def update_request(self):
        self.n += 1

class SequenceBatch(Sequence):
    def __init__(self, n, ffunc=None):
        super(SequenceBatch, self).__init__(n, ffunc)
    def update_str(self):
        pass
    def update_batch(self):
        self.n += 1

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
# The use of format_map is neat, but makes it harder to provide data as
# a dict and convert to json, as it is not easily known which curly braces
# to escape...
#

async def stress_requests(n, n_p, setup, teardown, task, args, parameters):
    results = []
    args.update(await setup())
    async def do_request():
        return await task(parameters, **args)
    while n>0:
        if n<n_p: n_p = n
        tasks = [ asyncio.create_task(do_request())
                  for p in range(0,n_p)]
        results += await asyncio.gather(*tasks)
        parameters.update_batch()
        n -= n_p
    await teardown(args)
    return results

HEADERS_JSON={
    'Accept':'application/yang-data+json',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping the data
    'Content-type': 'application/yang-data+json',
    'Authorization': 'Basic %s' % b64encode(b"admin:admin").decode("ascii")
}

REQ_DISPATCH = {
    'create': ('POST', 201),
    'delete': ('DELETE', 204),
    'read': ('GET', 200)
}

request_id = 0
async def restconf_request(client, host, op, resource, data=None, options=None):
    global request_id
    request_id += 1
    rid = request_id
    method, response_code = REQ_DISPATCH[op]
    options = COMMIT_PARAMS
    url = f'http://{host}/restconf/data{resource}' + options
    st = time.monotonic()
    try:
        async with client.request(method, url, headers=HEADERS_JSON, data=data.encode('utf-8')) as response:
            if response.status in [ 201, 204 ]:
                data = None # No content is expected.
            else:
                if response.headers['Content-Type'] == 'application/yang-data+json':
                #    data = await response.json()
                #else:
                    data = await response.text()
            elapsed = time.monotonic()-st
            return (rid, 'ok', response.status, data, elapsed)
    except Exception as e:
        return (rid, 'exception', repr(e))

#
# Main
#

#
# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "id": SequenceRequest(0),
})


async def setup():
    conn = aiohttp.TCPConnector(limit=0) # No limit of parallel connections
    client = aiohttp.ClientSession(connector=conn)
    return { 'client': client }

async def teardown(args):
    await args['client'].close()

async def request(parameters, client=None, op='', url='', data=''):
    url = url.format_map(parameters)
    data = data.format_map(parameters)
    parameters.update_request()
    return await restconf_request(client,
                                  f'{HOST}:{PORT}',
                                  op,
                                  url,
                                  data)



def assert_statuses(cmd, results):
    expected_status = REQ_DISPATCH[cmd][1]
    for r in results:
        rid, res, *rest = r
        if res == 'ok':
            st,data,el = rest
            if st != expected_status:
                pass
                #print(f"ERROR: wrong status returned {rid}: {st} != {expected_status}")
                #print(data)
        elif res == 'exception':
            exc, = rest
            #print(f"ERROR: exception {rid}: {exc}")
        else:
            raise Exception(f"Invalid return result {rid}: {res}")

def calc_average(results, expected_status):
    total_ok = 0.0
    count_ok = 0
    total_wrong = 0.0
    count_wrong = 0
    total_exc = 0.0
    count_exc = 0
    for r in results:
        rid, res, *rest = r
        if res == 'ok':
            st,_,el = rest
            if st == expected_status:
                total_ok += el
                count_ok += 1
            else:
                total_wrong += el
                count_wrong += 1
        elif res == 'exception':
            count_exc += 1

    return count_ok, total_ok, count_wrong, count_exc


def do_test(cmd, n, n_p):
    if cmd == 'clean':
        args = {
            'op': 'delete',
            'url': '/model-a:model-a',
            'data': ''
        }
        cmd = 'delete'
    elif cmd == 'delete':
        args = {
            'op': 'delete',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': ''
        }
    elif cmd == 'create':
        args = {
            'op': 'create',
            'url': '/model-a:model-a',
            'data': '{{ "list":{{"name":"K{id}","str-value":"String data {id}"}}}}'
        }
    elif cmd == 'read':
        args = {
            'op': 'read',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': ''
        }
    st = time.monotonic()
    results = asyncio.run(stress_requests(n, n_p, setup, teardown, request, args, parameters))
    elapsed = time.monotonic()-st

    assert_statuses(cmd, results)

    count, total, count_wrong, count_exc = calc_average(results, REQ_DISPATCH[cmd][1])

    return elapsed, count, total, count_wrong, count_exc


if __name__ == '__main__':
    cmd = sys.argv[1]
    n = int(sys.argv[2])
    n_p = int(sys.argv[3])

    elapsed, count, total, count_wrong, count_exc = do_test(cmd, n, n_p)
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
