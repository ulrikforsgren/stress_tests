from stress_testing.parameters import (
    Parameters,
    SequenceRequest,
    RandomValue
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


tests = {
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
            'data': {
                        "service":{
                            "name":"<<prefix>><<sid>>",
                            "str-value":"String data <<sid>>"
                        }
                    },
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
            'data': {
                        "service":{
                            "str-value":"Changed string data <<data>>"
                        }
                    },
        },
    'delete':
        {
            'op': 'delete',
            'resource': '/empty-template-service:empty-template-service/service=<<prefix>><<sid>>',
        }
}
