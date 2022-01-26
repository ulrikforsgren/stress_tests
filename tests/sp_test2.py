#!/usr/bin/env python3

import subprocess
import time

p = subprocess.Popen(['ls'],
                     shell=True,
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)

print(p.poll())
time.sleep(1)
print(p.poll())
n = 0
print(p.stdout.read())
print(p.stdout.read())
