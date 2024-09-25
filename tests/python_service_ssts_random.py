#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import parseArgs, Parameters,\
     Sequence, SequenceRequest, RandomString, RandomValue, \
     SequenceRequestRandomized, run_test


# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "sid": RandomString(15, seed=0, keep_state=True),
    "did": Sequence(0, 10000, keep_state=True),
    "data": RandomString(15),
    "delay": 0,
    "numvlan": 800
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Python based service with a configurable delay ({delay}ms) and vlans ({numvlan} vlans)',
        },
    'clean':
        {
            'op': 'delete',
            'url': '/python-service:python-service'
        },
    're-deploy':
        {
            'op': 'action',
            'url':
            '/python-service:python-service/python-service:service=S<<sid>>/re-deploy',
            'data': '''{
                    "input" : {
                        "dry-run":  {}
                    }
                }''',
        },
    'create':
        {
            'op': 'create',
            'url': '/python-service:python-service',
            'data': '''{
                        "service":{
                            "name":"S<<sid>>",
                            "delay":<<delay>>,
                            "device":"r<<did>>",
                            "template":["one-leaf", "vlans"],
                            "str-value":"<<data>>",
                            "num-vlan":<<numvlan>>
                        }
                    }''',
        },
    'read':
        {
            'op': 'read',
            'url':
            '/python-service:python-service/python-service:service=S<<sid>>',
        },
    'update':
        {
            'op': 'update',
            'url':
            '/python-service:python-service/python-service:service=S<<sid>>',
            'data': '''{
                        "service":{
                            "delay":<<delay>>,
                            "device":"r<<did>>",
                            "template":["one-leaf", "vlans"],
                            "str-value":"<<data>>",
                            "num-vlan":<<numvlan>>
                        }
                    }''',
        },
    'delete':
        {
            'op': 'delete',
            'url':
            '/python-service:python-service/python-service:service=S<<sid>>',
        }
}

if __name__ == '__main__':
    run_test(parseArgs(sys.argv[1:], ['re-deploy', 'action','login']), CRUD_TESTS, parameters, 500, 40)
