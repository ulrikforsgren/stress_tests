#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import (
    parseArgs,
    Parameters,
    SequenceRequest,
    RandomValue,
    run_test
)


# Paramaters are used to dynamically update the intent (op, resource, data, ...) 
# for each request. There are multiple types of parameters to create e.g 
# sequences, random values, etc. that are updated at various levels:
#
#  - each usage/string-replacement (Sequence, RandomValue, ...)
#  - per request (SequenceRequest, SequenceRequestRandom, ...)
#  - each batch of requests (SequenceBatch)
#

parameters = Parameters({
    'prefix': 'S',
    'sid': SequenceRequest(0),
    'data': RandomValue(0, 4000000000)
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Empty template based service'
        },
    'clean':
        {
            'op': 'delete',
            'resource': '/empty-template-service:empty-template-service'
        },
    'create':
        {
            'op': 'create',
            'resource': '/empty-template-service:empty-template-service',
            'data': '''{
                        "service":{
                            "name":"<<prefix>><<sid>>",
                            "str-value":"String data <<sid>>"
                        }
                    }''',
        },
    'read':
        {
            'op': 'read',
            'resource': '/empty-template-service:empty-template-service/service=<<prefix>><<sid>>',
        },
    'update':
        {
            'op': 'update',
            'resource': '/empty-template-service:empty-template-service/service=<<prefix>><<sid>>',
            'data': '''{
                        "service":{
                            "str-value":"Changed string data <<data>>"
                        }
                    }''',
        },
    'delete':
        {
            'op': 'delete',
            'resource': '/empty-template-service:empty-template-service/service=<<prefix>><<sid>>',
        }
}

if __name__ == '__main__':
    run_test(parseArgs(), CRUD_TESTS, parameters, 500, 40)
