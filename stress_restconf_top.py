#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
from base64 import b64encode
import pprint as pp
import sys
import time

import aiohttp

#
# TODO:
#  - ArgParse
#  - Create service(s) from file
#  - Control commit flags
#

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
    'Content-type': 'application/yang-data+json',
    'Authorization': 'Basic %s' % b64encode(b"admin:admin").decode("ascii")
}

REQ_DISPATCH = {
    'create': ('POST', 201),
    'delete': ('DELETE', 200),
    'read': ('GET', 200)
}

request_id = 0
async def restconf_request(client, host, op, resource, data=None, options=None):
    global request_id
    try:
        request_id += 1
        rid = request_id
        method, response_code = REQ_DISPATCH[op]
        options = "?commit-queue=async&commit-queue-error-option=stop-on-error"
        url = f'http://{host}/restconf/data{resource}' + options
        print(f'{rid}:', url, data)
        st = time.time()
        async with client.request(method, url, headers=HEADERS_JSON, data=data.encode('utf-8')) as response:
            data = await response.json()
            #print(f'{rid}:', response.status)
            print(f'{rid}:', response.status, time.time()-st)
            if response.status != response_code:
                print(f"ERROR: response code not matching {response.status} != {response_code}")
                print(data)
            return data
    except Exception as e:
        return repr(e)

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
    "vid": Sequence(1000),
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
                                  'localhost:8080',
                                  op,
                                  url,
                                  data)

cmd = sys.argv[1]
if cmd == 'delete':
    args = {
        'op': 'delete',
        'url': '/top:top=V{id}',
        'data': ''
    }
elif cmd == 'create':
    args = {
        'op': 'create',
        'url': '',
        'data': '{{"/top:top":{{"name":"V{id}","vid":"{vid}","stacked-devices":["ex0","ex3"]}}}}'
    }
elif cmd == 'c-rm':
    args = {
        'op': 'create',
        'url': '',
        'data': '{{"/top:top":{{"name":"V{id}","use-resources-vid": [null],"stacked-devices":["ex0","ex1"]}}}}'
    }
elif cmd == 'read':
    args = {
        'op': 'read',
        'url': '/top:top=V{id}',
        'data': ''
    }

n = int(sys.argv[2])
n_p = int(sys.argv[3])
results = asyncio.run(stress_requests(n, n_p, setup, teardown, request, args, parameters))

pprint(results)
