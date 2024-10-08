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
    'delay': 100,
    'num-vlan': 1
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Python based service with a configurable delay ({delay}ms) and vlans ({numvlan} vlans)',
            'parameters': parameters
        },
    'clean':
        {
            'op': 'delete',
            'resource': '/python-service:python-service'
        },
    're-deploy':
        {
            'op': 'action',
            'resource':
            '/python-service:python-service/service=<<prefix>><<sid>>/re-deploy',
            'data': '''{
                    "input" : {
                        "dry-run":  {}
                    }
                }''',
        },
    'create':
        {
            'op': 'create',
            'resource': '/python-service:python-service',
            'data': '''{
                        "service":{
                            "name":"<<prefix>><<sid>>",
                            "delay":<<delay>>,
                            "device":"r<<id>>",
                            "template":"one-leaf",
                            "str-value":"String data <<id>>",
                            "num-vlan":<<numvlan>>
                        }
                    }''',
        },
    'read':
        {
            'op': 'read',
            'resource': '/python-service:python-service/service=<<prefix>><<sid>>',
        },
    'update':
        {
            'op': 'update',
            'resource': '/python-service:python-service/service=<<prefix>><<sid>>',
            'data': '''{
                        "service":{
                            "delay":<<delay>>,
                            "str-value":"Changed string data <<data>>"
                        }
                    }''',
        },
    'delete':
        {
            'op': 'delete',
            'resource': '/python-service:python-service/service=<<prefix>><<sid>>',
        }
}

if __name__ == '__main__':
    run_test(parseArgs(None, ['re-deploy']), CRUD_TESTS, parameters, 500, 40)
