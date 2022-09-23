#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import parseArgs, Parameters,\
     SequenceRequest, RandomValue, run_crud_tests, run_single_test


# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "id": SequenceRequest(0),
    "data": RandomValue(0, 4000000000),
    "delay": 0
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Empty Python based service with a configurable delay'
        },
    'clean':
        {
            'op': 'delete',
            'url': '/empty-python-service:empty-python-service'
        },
    'create':
        {
            'op': 'create',
            'url': '/empty-python-service:empty-python-service',
            'data': '''{{
                        "service":{{
                            "name":"K{id}",
                            "delay":{delay},
                            "str-value":"String data {id}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'read':
        {
            'op': 'read',
            'url': '/empty-python-service:empty-python-service/empty-python-service:service=K{id}',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'url': '/empty-python-service:empty-python-service/empty-python-service:service=K{id}',
            'data': '''{{
                        "service":{{
                            "delay":{delay},
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'delete':
        {
            'op': 'delete',
            'url': '/empty-python-service:empty-python-service/empty-python-service:service=K{id}',
            'parameters': parameters
        }
}

if __name__ == '__main__':
    args = parseArgs(sys.argv[1:])
    if args.cmd == 'crud':
        run_crud_tests(args, CRUD_TESTS, 500, max_p=40, do_print=True)
    else:
        run_single_test(args, CRUD_TESTS)
