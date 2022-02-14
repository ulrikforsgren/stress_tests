#!/usr/bin/env python3

import sys
import time

import psutil


def get_info(p):
    mem = p.memory_info()[0]/1048576 # RSS MB
    cpu = p.cpu_percent()
    conn = len(p.connections())
    return (mem, cpu, conn)


def show_tree(p, indent=0):
    print('{:<40}{}'.format('    '*indent+p.name()+' ({})'.format(p.pid), p.exe()))
    for c in p.children():
        show_tree(c, indent+1)

def main():
    pid = int(sys.argv[1])

    proc = psutil.Process(pid=pid)
    show_tree(proc)

if __name__ == '__main__':
    main()
