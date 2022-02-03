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
from matplotlib.animation import FuncAnimation
import numpy as np

from stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue

class DataQueue(queue.Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
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

async def stress_requests_stream(n, n_p, setup, teardown, task, args):
    tasks = set()

    await setup(args)

    for _ in range(0, min(n, n_p)):
        tasks.add(asyncio.create_task(task(**args)))
    n -= min(n, n_p) # Started initial tasks

    while len(tasks)>0:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            result = await d
            q.put(result)
        a = n_p-len(pending)  # Calculate number of free task slots
        tasks_to_start = min(a, n)
        for _ in range(0, tasks_to_start): # Start tasks in available slots
            pending.add(asyncio.create_task(task(**args)))
        n -= tasks_to_start
        tasks = pending

    await teardown(args)



async def async_generator(q):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=100),
        "data": RandomValue(0, 4000000000),
    })
    args = {
            'op': 'update',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '''{{
                        "list":{{
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
    }
    args['host'] = 'localhost:8080'
    await stress_requests_stream(30000, 10, setup, teardown, default_task, args)

def generator_thread(q):
    asyncio.run(async_generator(q))

x = []
y = []

figure, ax = plt.subplots(figsize=(4,3))
line, = ax.plot(x, y)
plt.axis([0, 300, 0, 100])

n = 0
t_prev = time.monotonic()

def func_animate(i):
    global x,y,n,q,t_prev
    x += [n]
    l = len(q.get())
    t_now = time.monotonic()
    elapsed = t_now-t_prev
    y += [l/elapsed]
    n += 1

    line.set_data(x, y)

    t_prev = t_now
    return line,

q = DataQueue(maxsize=8192)
ani = FuncAnimation(figure,
                    func_animate,
                    frames=10,
                    interval=1000)

#ani.save(r'animation.gif', fps=10)


thread = Thread(target=generator_thread, args=(q,))
thread.start()

plt.show()
sys.exit(1)
