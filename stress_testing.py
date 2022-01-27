#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import pprint as pp

from restconf_api import REQ_DISPATCH, restconf_request

HOST='localhost'
PORT=8080

pprint = pp.PrettyPrinter(indent=4).pprint


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



async def request(client=None, parameters=Parameters(), op='', url='', data=''):
    url = url.format_map(parameters)
    data = data.format_map(parameters)
    parameters.update_request()
    return await restconf_request(client,
                                  f'{HOST}:{PORT}',
                                  op,
                                  url,
                                  data)

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
