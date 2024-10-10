from stress_testing.stress_testing import (
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
    'data': RandomValue(0, 4000000000),
    'delay': 100
})


tests = {
    '__info':
        {
            'name': 'Java based service with a configurable delay (<<delay>> ms)',
            'parameters': parameters
        },
    'clean':
        {
            'op': 'delete',
            'resource': '/java-service:java-service'
        },
    'create':
        {
            'op': 'create',
            'resource': '/java-service:java-service',
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
            'resource': '/java-service:java-service/service=<<prefix>><<sid>>',
        },
    'update':
        {
            'op': 'update',
            'resource': '/java-service:java-service/service=<<prefix>><<sid>>',
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
            'resource': '/java-service:java-service/service=<<prefix>><<sid>>',
        }
}
