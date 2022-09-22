#!/usr/bin/env python3

import sys
import time

import psutil


def get_info(p):
    mem = p.memory_info()[0]/1048576 # RSS MB
    cpu = p.cpu_percent()
    try:
        conn = len(p.connections())
    except OSError as e:
        if e.errno == 38:
            conn = len(p.connections())
        else:
            conn = -1
    return (mem, cpu, conn)


def main():
    pid = int(sys.argv[1])

    ncs = psutil.Process(pid=pid)
    erl_child_setup = ncs.children()[0] # Assuming only 1 child
    assert(erl_child_setup.name() == 'erl_child_setup')
    java = None
    #TODO: Python to be added
    for child in erl_child_setup.children():
        name = child.name()
        if name == 'java':
            java = child
    assert(java is not None)


    start = time.monotonic()
    while True:
        t = int(time.monotonic()-start)
        mem, cpu, conn = get_info(ncs)
        jmem, jcpu, jconn = get_info(java)
        print(f'{t:>5}', end='')
        print(f'  {mem:>6.0f} MB  {cpu:>5.1f} %  {conn:>4} conn', end='')
        print(f'  {jmem:>6.0f} MB  {jcpu:>5.1f} %  {jconn:>4} conn', end='')
        print()
        time.sleep(1)

if __name__ == '__main__':
    main()
