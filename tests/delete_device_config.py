#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import sys

from stress_testing.stress_testing import parseArgs, Parameters,\
     Sequence, RandomValue, run_test

from devices import devices

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

# Inject paramaters that can be update on multiple levels when iterating:
#  - each usage (Sequence)
#  - url and data (SequenceLine)
#  - each batch of requests (SequenceBatch)
#
parameters = Parameters({
    "name": PopRequest(devices),
})


CRUD_TESTS = {
    '__info':
        {
            'name': 'Run parallel devices device delete-config from a predefined list',
            'parameters': parameters
        },
    'del-config':
        {
            'op': 'action',
            'url': '/tailf-ncs:devices/device={name}/delete-config',
            'parameters': parameters
        },
}

if __name__ == '__main__':
    run_test(parseArgs(sys.argv[1:], extra_actions=['del-config']), CRUD_TESTS, 500, 40)
