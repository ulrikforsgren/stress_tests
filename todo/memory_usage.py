#!/usr/bin/env python3

import sys
import time

import psutil


def get_info(p):
    mem = p.memory_info()[0]/1048576 # RSS MB
    cpu = p.cpu_percent()
    conn = len(p.connections())
    return (mem, cpu, conn)


def main():
    pid = int(sys.argv[1])

    proc = psutil.Process(pid=pid)

    start = time.monotonic()
    while True:
        t = int(time.monotonic()-start)
        mem, cpu, conn = get_info(proc)
        print(f'{t:>5}  {mem:>6.0f} MB  {cpu:>5.1f} %  {conn:>4} conn')
        time.sleep(1)

if __name__ == '__main__':
    main()
