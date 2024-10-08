#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import parseArgs, Parameters,\
     Sequence, RandomValue, run_test

from devices import devices


#
# New Parameter types can be created by extending the Sequence class
#
class PopRequest(Sequence):
    def __init__(self, l):
        self.l = l
    def update_str(self):
        pass
    def update_request(self):
        self.l.pop(0)
    def __str__(self):
        return  str(self.l[0])
    def update_batch(self):
        pass


# Paramaters are used to dynamically update the intent (op, resource, data, ...) 
# for each request. There are multiple types of parameters to create e.g 
# sequences, random values, etc. that are updated at various levels:
#
#  - each usage/string-replacement (Sequence, RandomValue, ...)
#  - per request (SequenceRequest, SequenceRequestRandom, ...)
#  - each batch of requests (SequenceBatch)
#

parameters = Parameters({
    "name": PopRequest(devices),
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Run parallel devices device delete-config from a predefined list'
        },
    'del-config':
        {
            'op': 'action',
            'resource': '/tailf-ncs:devices/device={name}/delete-config',
        },
}

if __name__ == '__main__':
    run_test(parseArgs(None, extra_actions=['del-config']), CRUD_TESTS, parameters, 500, 40)
