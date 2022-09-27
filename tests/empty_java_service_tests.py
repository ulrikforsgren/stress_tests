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
    "delay": 0
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Empty Java based service with a configurable delay ({delay}ms)',
            'parameters': parameters
        },
    'clean':
        {
            'op': 'delete',
            'url': '/empty-java-service:empty-java-service'
        },
    'create':
        {
            'op': 'create',
            'url': '/empty-java-service:empty-java-service',
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
            'url': '/empty-java-service:empty-java-service/empty-java-service:service=K{id}',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'url': '/empty-java-service:empty-java-service/empty-java-service:service=K{id}',
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
            'url': '/empty-java-service:empty-java-service/empty-java-service:service=K{id}',
            'parameters': parameters
        }
}

if __name__ == '__main__':
    run_test(parseArgs(sys.argv[1:]), CRUD_TESTS, 500, 40)
