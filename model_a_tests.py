#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

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
            'url': '/model-a:model-a'
        },
    'create':
        {
            'op': 'create',
            'url': '/model-a:model-a',
            'data': '''{{
                        "list":{{
                            "name":"K{id}",
                            "str-value":"String data {id}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'read':
        {
            'op': 'read',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '''{{
                        "list":{{
                            "str-value":"Changed string data {id}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'delete':
        {
            'op': 'delete',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'parameters': parameters
        }
}

if __name__ == '__main__':
    args = parseArgs(sys.argv[1:])
    if args.cmd == 'crud':
        run_crud_tests(args, CRUD_TESTS, 500, max_p=40, do_print=True)
    else:
        run_single_test(args, CRUD_TESTS)
