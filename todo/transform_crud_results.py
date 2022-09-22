#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import re
import sys


if __name__ == '__main__':
    f = open(sys.argv[1], 'r')
    lines = [ l.strip().replace('.', ',').split() for l in f ]
    steps = []

    rm = {'CREATE': [], 'READ': [], 'UPDATE': [], 'DELETE': []}
    for l in lines:
        o, _, np, _, r, *rest = l
        rm[o].append(r)
        if np not in steps: steps.append(np)

    print('CRUD', 'CREATE', 'READ', 'UPDATE', 'DELETE')
    for n, s in enumerate(steps):
        print(s, end='')
        for o in ['CREATE', 'READ', 'UPDATE', 'DELETE']:
            print('', rm[o][n], end='')
        print()


