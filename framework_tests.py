#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import sys
import time

from stress_testing import parseArgs, Parameters, SequenceRequest,\
                           run_crud_tests, run_single_test


# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "id": SequenceRequest(0),
})


CRUD_TESTS = {
    'clean':
        {
            'op': 'delete',
            'parameters': parameters
        },
    'create':
        {
            'op': 'create',
            'parameters': parameters
        },
    'read':
        {
            'op': 'read',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'parameters': parameters
        },
    'delete':
        {
            'op': 'delete',
            'parameters': parameters
        }
}


async def timeout_task(client=None, parameters=Parameters(), op='', url='', data=''):
    url = url.format_map(parameters)
    data = data.format_map(parameters)
    parameters.update_request()
    st = time.monotonic()
    await asyncio.sleep(1)
    elapsed = time.monotonic()-st
    return (parameters['id'], 'ok', 200, "String result", elapsed)


if __name__ == '__main__':
    args = parseArgs(sys.argv[1:])
    if args.cmd == 'crud':
        run_crud_tests(args, 10, [1, 5, 10], CRUD_TESTS, task=timeout_task, do_print=True)
    else:
        run_single_test(args, CRUD_TESTS, task=timeout_task)
