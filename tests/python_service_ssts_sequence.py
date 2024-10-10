from stress_testing.stress_testing import (
    Parameters,
    Sequence,
    SequenceRequest,
    RandomString
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
    "sid": SequenceRequest(0, keep_state=True),
    "did": Sequence(0, 10000, keep_state=True),
    "data": RandomString(15),
    "delay": 0,
    "numvlan": 800
})


tests = {
    '__info':
        {
            'name': 'Python based service with a configurable delay (<<delay>> ms) and vlans (<<numvlan>> vlans)',
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
            '/python-service:python-service/python-service:service=S<<sid>>/re-deploy',
            'data': {
                    "input" : {
                        "dry-run":  {}
                    }
                },
        },
    'create':
        {
            'op': 'create',
            'resource': '/python-service:python-service',
            'data': {
                        "service":{
                            "name":"S<<sid>>",
                            "delay":"<<delay>>",
                            "device":"r<<did>>",
                            "template":["one-leaf", "vlans"],
                            "str-value":"<<data>>",
                            "num-vlan":"<<numvlan>>"
                        }
                    },
        },
    'read':
        {
            'op': 'read',
            'resource':
            '/python-service:python-service/python-service:service=S<<sid>>',
        },
    'update':
        {
            'op': 'update',
            'resource':
            '/python-service:python-service/python-service:service=S<<sid>>',
            'data': {
                        "service":{
                            "delay":"<<delay>>",
                            "device":"r<<did>>",
                            "template":["one-leaf", "vlans"],
                            "str-value":"<<data>>",
                            "num-vlan":"<<numvlan>>"
                        }
                    },
        },
    'delete':
        {
            'op': 'delete',
            'resource':
            '/python-service:python-service/python-service:service=S<<sid>>',
        }
}
