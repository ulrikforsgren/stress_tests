#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import io
import queue
import random
import socket
import sys
import time
from threading import Thread

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

from stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue, single_request

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

    await teardown(args)



async def request_task(q):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=100),
        "data": RandomValue(0, 4000000000),
    })
    args = {
            'op': 'update', 'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '''{{
                        "list":{{
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
    }
    args['host'] = sys.argv[1]

    # Just run for a very long time...
    await stress_requests_stream(1000000, 10, setup, teardown,
                                 default_task, args)

def request_thread(q):
    asyncio.run(request_task(q))

x = []
y = []

yaxis = 100
if len(sys.argv)>2:
    yaxis = int(sys.argv[2])
figure, ax = plt.subplots(figsize=(4,3))
line, = ax.plot(x, y)
plt.axis([0, 300, 0, yaxis])

n = 0
t_prev = time.monotonic()

def func_animate(i):
    global x,y,n,q,t_prev
    l = len(q.get())
    t_now = time.monotonic()
    elapsed = t_now-t_prev
    y += [l/elapsed]
    n += 1

    if len(y)<=300:
        x += [n]
    else:
        y.pop(0)

    line.set_data(x, y)

    t_prev = t_now
    return line,

q = DataQueue(maxsize=8192)
ani = animation.FuncAnimation(figure,
                    func_animate,
                    frames=1,
                    interval=1000)


thread = Thread(target=request_thread, args=(q,))
thread.start()

plt.show()
stop_requests = True
sys.exit(1)
