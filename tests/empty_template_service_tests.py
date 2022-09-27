#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import parseArgs, Parameters,\
     SequenceRequest, RandomValue, run_test


# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "id": SequenceRequest(0),
    "data": RandomValue(0, 4000000000),
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Empty template based service'
        },
    'clean':
        {
            'op': 'delete',
            'url': '/empty-template-service:empty-template-service'
        },
    'create':
        {
            'op': 'create',
            'url': '/empty-template-service:empty-template-service',
            'data': '''{{
                        "service":{{
                            "name":"K{id}",
                            "str-value":"String data {id}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'read':
        {
            'op': 'read',
            'url': '/empty-template-service:empty-template-service/empty-template-service:service=K{id}',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'url': '/empty-template-service:empty-template-service/empty-template-service:service=K{id}',
            'data': '''{{
                        "service":{{
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
        },
    'delete':
        {
            'op': 'delete',
            'url': '/empty-template-service:empty-template-service/empty-template-service:service=K{id}',
            'parameters': parameters
        }
}

if __name__ == '__main__':
    run_test(parseArgs(sys.argv[1:]), CRUD_TESTS, 500, 40)
