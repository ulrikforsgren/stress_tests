#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import pprint as pp
import sys
import time

from restconf_api import setup, teardown
from stress_testing import request, stress_requests,\
                           calc_average, Parameters, SequenceRequest

pprint = pp.PrettyPrinter(indent=4).pprint

# TODO:
# - Use argparse
# - Argument for host:port
# - Argument for user:password


# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "id": SequenceRequest(0),
})




def do_test(cmd, n, n_p):
    if cmd == 'clean':
        args = {
            'op': 'delete',
            'url': '/model-a:model-a'
        }
    elif cmd == 'create':
        args = {
            'op': 'create',
            'url': '/model-a:model-a',
            'data': '{{ "list":{{"name":"K{id}","str-value":"String data {id}"}}}}',
            'parameters': parameters
        }
    elif cmd == 'read':
        args = {
            'op': 'read',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'parameters': parameters
        }
    elif cmd == 'update':
        args = {
            'op': 'update',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '{{ "list":{{"str-value":"Changed string data {id}"}}}}',
            'parameters': parameters
        }
    elif cmd == 'delete':
        args = {
            'op': 'delete',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'parameters': parameters
        }
    st = time.monotonic()
    results = asyncio.run(stress_requests(n, n_p, setup, teardown, request, args))
    elapsed = time.monotonic()-st

    count, total, count_wrong, count_exc = calc_average(results)

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
