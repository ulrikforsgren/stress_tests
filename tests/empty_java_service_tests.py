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
    'data': RandomValue(0, 4000000000),
    'delay': 0
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Empty Java based service with a configurable delay (<<delay>>ms)'
        },
    'clean':
        {
            'op': 'delete',
            'resource': '/empty-java-service:empty-java-service'
        },
    'create':
        {
            'op': 'create',
            'resource': '/empty-java-service:empty-java-service',
            'data': {
                        "service":{
                            "name":"<<prefix>><<sid>>",
                            "delay":"<<delay>>",
                            "str-value":"String data <<sid>>"
                        }
                    },
        },
    'read':
        {
            'op': 'read',
            'resource': '/empty-java-service:empty-java-service/service=<<prefix>><<sid>>',
        },
    'update':
        {
            'op': 'update',
            'resource': '/empty-java-service:empty-java-service/service=<<prefix>><<sid>>',
            'data': {
                        "service":{
                            "delay":"<<delay>>",
                            "str-value":"Changed string data <<data>>"
                        }
                    },
        },
    'delete':
        {
            'op': 'delete',
            'resource': '/empty-java-service:empty-java-service/service=<<prefix>><<sid>>',
        }
}

if __name__ == '__main__':
    run_test(parseArgs(), CRUD_TESTS, parameters, 500, 40)