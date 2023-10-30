#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

# TODO:
# - Command console
# - Use python dict for json data
# - Use new matplotlib event loop
# - Dict to pass parameters to running transaction task?!


import argparse
import asyncio
import io
import queue
import random
import re
import socket
import sys
import time
from threading import Thread

import aioconsole
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

from stress_testing.stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue, single_request


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost:8080',
                        help='Host:Port to connect to.')
    parser.add_argument('--yaxis', type=int, default=300,
                    help='Y axis max value.')
    return parser.parse_args()


class DataQueue(queue.Queue):
    """
    DataQueue provides a FIFO type queue where, where the get
    method return all currently queued items in one chunk.
    It uses a socketpair to provide the synchronization needed
    to get the number of currently queued items.
    """
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        # It might be possible to use a diggre
        self.r, self.w = socket.socketpair()
        self.r.setblocking(False)
    def get(self, block=True, timeout=None):
        try:
            results = []
            data = self.r.recv(self.maxsize)
            for _ in data:
                results.append(super().get())
            return results
        except io.BlockingIOError:
            return []
    def put(self, item):
        super().put(item)
        self.w.send(b'.')
    def fileno(self):
        return self.r.fileno()


stop_requests = False
async def stress_requests_stream(n, n_p, setup, teardown, task, args):
    global stop_requests
    tasks = set()

    await setup(args)

    try:
        # Start initial tasks, but no more than n_p
        for _ in range(0, min(n, n_p)):
            tasks.add(asyncio.create_task(task(**args)))
        n -= min(n, n_p)

        while len(tasks)>0 and not stop_requests:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                result = await d
                q.put(result)
            # Start new tasks, but no more than n_p in total.
            a = n_p-len(pending)  # Calculate number of free task slots
            tasks_to_start = min(a, n)
            for _ in range(0, tasks_to_start): # Start tasks in available slots
                pending.add(asyncio.create_task(task(**args)))
            n -= tasks_to_start
            tasks = pending
    except asyncio.CancelledError:
        pass 

    await teardown(args)



async def request_task(args, q):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=100),
        "data": RandomValue(0, 4000000000),
    })
    data = {
            'op': 'update', 'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '''{{
                        "list":{{
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
    }
    data['host'] = args.host

    # Just run for a very long time...
    await stress_requests_stream(1000000, 20, setup, teardown,
                                 default_task, data)

async def command_handler(args, q):
    global stop_requests
    req_task = None
    while True:
        cmdline = await aioconsole.ainput('> ')
        cmd, *cmdargs = re.split(r'\s+', cmdline.strip())
        if cmd in ['exit', 'quit', 'q']:
            break
        if cmd == 'start':
            if req_task is None:
                req_task = asyncio.create_task(request_task(args, q))
            else:
                print("Request task already running.")
        elif cmd == 'stop':
            if req_task is not None:
                req_task.cancel()
                req_task = None
            else:
                print("Request task not running.")
    stop_requests = True
    if req_task is not None:
        req_task.cancel()

async def amain(args, q):
    await command_handler(args, q)


def request_thread(args, q, plt):
    asyncio.run(amain(args, q))
    plt.close()

x = []
y = []
y2 = []
n = 0
t_prev = time.monotonic()
q = DataQueue(maxsize=8192)

def main(args):
    global stop_requests

#    figure, ax = plt.subplots(figsize=(4,3))
#    ax.set_title('Transactions per second')
#    line, = ax.plot(x, y)
#    plt.axis([0, 300, 0, args.yaxis])

    figure = plt.figure('Transactional Throughput Stress Test', figsize=(4,3))
    ax = figure.add_subplot()
    ax.set_title('Throughput')
    ax.set_ylabel('Transactions/second')
    ax.set_xlabel('Seconds')
    line, = ax.plot(x, y)
    line2, = ax.plot(x, y)
    plt.axis([0, 300, 0, args.yaxis])
    ax.legend((line, line2), ('ok', 'nok'), loc='lower right', shadow=True)

    def func_animate(i):
        global x,y,y2,n,q,t_prev
        results = q.get()
        l = len(results)
        ok = 0
        nok = 0
        for r in results:
            if r[1] == 'ok':
                ok +=1
            else:
                nok +=1
        t_now = time.monotonic()
        elapsed = t_now-t_prev
        y += [ok/elapsed]
        y2 += [nok/elapsed]
        n += 1

        if len(y)<=300:
            x += [n]
        else:
            y.pop(0)
            y2.pop(0)

        line.set_data(x, y)
        line2.set_data(x, y2)

        t_prev = t_now
        return line,

    ani = animation.FuncAnimation(figure,
                        func_animate,
                        frames=1,
                        interval=1000)


    thread = Thread(target=request_thread, args=(args, q, plt))
    thread.start()

    try:
        plt.show()
        print('stopped')
    except KeyboardInterrupt:
        pass
    stop_requests = True
    sys.exit(0)

if __name__ == '__main__':
    main(parseArgs())
