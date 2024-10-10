from stress_testing.stress_testing import (
    parseArgs,
    Parameters,
    Parameter
)


from devices import devices


#
# New Parameter types can be created by extending the Sequence class
#
class PopRequest(Parameter):
    def __init__(self, l):
        self.l = l
    
    def update_request(self):
        try:
            self.current = self.l.pop(0)
        except IndexError:
            self.current = '<no more values>'

# Paramaters are used to dynamically update the intent (op, resource, data, ...) 
# for each request. There are multiple types of parameters to create e.g 
# sequences, random values, etc. that are updated at various levels:
#
#  - each usage/string-replacement (Sequence, RandomValue, ...)
#  - per request (SequenceRequest, SequenceRequestRandom, ...)
#  - each batch of requests (SequenceBatch)
#

parameters = Parameters({
    "dname": PopRequest(devices),
})


tests = {
    '__info':
        {
            'name': 'Run parallel devices device delete-config from a predefined list'
        },
    'del-config':
        {
            'op': 'action',
            'resource': '/tailf-ncs:devices/device=<<dname>>/delete-config',
        },
}