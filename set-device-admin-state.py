#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import pprint as pp
import sys

from stress_testing.restconf_api import run_single_request

pprint = pp.PrettyPrinter(indent=4).pprint

state = sys.argv[1]


def make_device_adminstate_data(start, n, state):
    devs = []
    for i in range(start, start+n):
        devs.append({
                'name': f'r{i}',
                'state': {
                    'admin-state': state
                }
            })
    data = {
        'tailf-ncs:devices': {
            'device': devs
        }
    }
    return data


def main():
    ndevs = 1000
    np = 100
    for i in range(0, ndevs//np):
        data = make_device_adminstate_data(i*np, np, state)
        result = run_single_request('localhost:8080', 'update', '', data)


if __name__ == '__main__':
    main()
