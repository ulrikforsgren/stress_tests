#!/usr/bin/env python3

import subprocess

p = subprocess.Popen(['./msg.sh'],
                     shell=True,
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)

while True:
    s = p.stdout.read()
    if len(s) == 0:
        break
    print(s)
