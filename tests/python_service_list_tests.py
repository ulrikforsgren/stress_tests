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
    "delay": 0,
    "numvlan": 100
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Python based service, list test, with a configurable delay ({delay}ms) and vlans ({numvlan} vlans)',
            'parameters': parameters
        },
    'clean':
        {
            'op': 'delete',
            'url': '/python-service:python-service'
        },
    're-deploy':
        {
            'op': 'action',
            'url': '/python-service:python-service/python-service:service=K{id}/re-deploy',
            'data': '''{{
                    "input" : {{
                        "dry-run":  {{}}
                    }}
                }}''',
            'parameters': parameters
        },
    'create':
        {
            'op': 'create',
            'url': '/python-service:python-service',
            'data': '''{{
                        "service":{{
                            "name":"K{id}",
                            "delay":{delay},
                            "device":"r{id}",
                            "template":"vlans",
                            "str-value":"String data {id}",
                            "num-vlan":{numvlan}
                        }}
                    }}''',
            'parameters': parameters
        },
    'read':
        {
            'op': 'read',
            'url': '/python-service:python-service/python-service:service=K{id}',
            'parameters': parameters
        },
    'update':
        {
            'op': 'update',
            'url': '/python-service:python-service/python-service:service=K{id}',
            'data': '''{{
                        "service":{{
                            "delay":{delay},
                            "device":"r{id}",
                            "template":"vlans",
                            "str-value":"Changed string data {data}",
                            "num-vlan":{numvlan}
                        }}
                    }}''',
            'parameters': parameters
        },
    'delete':
        {
            'op': 'delete',
            'url': '/python-service:python-service/python-service:service=K{id}',
            'parameters': parameters
        }
}

if __name__ == '__main__':
    run_test(parseArgs(sys.argv[1:], ['re-deploy', 'action','login']), CRUD_TESTS, 500, 40)
