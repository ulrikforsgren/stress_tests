#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import pprint as pp
import sys

from stress_testing.restconf_api import run_single_request

pprint = pp.PrettyPrinter(indent=4).pprint


def main():
    data = {
        'tailf-ncs:devices': {
            'tailf-ncs:global-settings': {
                'tailf-ncs:commit-queue': {
                     'tailf-ncs:enabled-by-default': sys.argv[1] == 'true'
                }
            }
        }
    }
    result = run_single_request('localhost:8080', 'update', '', data)
    pprint(result)

if __name__ == '__main__':
    main()
