#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

# TODO:
# * Command console
#  - Multiple tasks
#  - History
#  - Job handler
#  - Unknown command
# * Use python dict for json data
# * Use new matplotlib event loop
# * Dict to pass parameters to running transaction task?!


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


gargs = {
    'n_p': 20,
}
stop_requests = False
stop_event = asyncio.Event()
async def stress_requests_stream(task, args):
    global stop_requests, gargs
    tasks = set()

    await setup(args)

    try:
        # Start initial n_p tasks
        for _ in range(0, gargs['n_p']):
            tasks.add(asyncio.create_task(task(**args)))

        while len(tasks)>0 and not stop_requests:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                result = await d
                q.put(result)
            # Start new tasks, but no more than n_p in total.
            tasks_to_start = gargs['n_p']-len(pending)  # Calculate number of free task slots
            if tasks_to_start>0:
                for _ in range(0, tasks_to_start): # Start tasks in available slots
                    pending.add(asyncio.create_task(task(**args)))
            tasks = pending
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(e)

    await teardown(args)



async def request_task(args, q):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=1000),
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
    await stress_requests_stream(default_task, data)


async def command_handler(args, q):
    global stop_requests, gargs
    req_task = None
    try:
        while not stop_requests:
            cmdline = await aioconsole.ainput('> ')
            try:
                cmd, *cmdargs = re.split(r'\s+', cmdline.strip())
                if cmd in ['exit', 'quit', 'q']:
                    stop_event.set()
                    #break
                elif cmd == 'start':
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
                elif cmd == 'show':
                    print(gargs)
                elif cmd == 'set':
                    gargs[cmdargs[0]] = int(cmdargs[1])
                elif cmd == 'zoom':
                    maxy = int(max(max(y), max(y2))*1.2)
                    if maxy == 0:
                        maxy = 100
                    plt.axis([0, 300, 0, maxy])
                else:
                    print("Unknown command.")
            except KeyboardInterrupt as e:
                raise e
            except Exception as e:
                print(f"Error parsing command: {e}")
    except asyncio.CancelledError:
        pass
    stop_requests = True
    stop_event.set()
    if req_task is not None:
        req_task.cancel()

event_loop = None
async def amain(args, q):
    global event_loop
    event_loop = asyncio.get_event_loop()
    cmd_task = asyncio.create_task(command_handler(args, q))
    await stop_event.wait()
    cmd_task.cancel()



def request_thread(args, q, plt):
    asyncio.run(amain(args, q))
    plt.close()

x = []
y = []
y2 = []
n = 0
t_prev = time.monotonic()
q = DataQueue(maxsize=8192)


close_flag = 0
# to handle close event.
def handle_close(evt):
    global close_flag # should be global variable to change the outside close_flag.
    close_flag = 1


async def set_event(e):
    e.set()


def main(args):
    global stop_requests

    plt.ion()
    figure = plt.figure('Transactional Throughput Stress Test', figsize=(4,3))
    figure.canvas.mpl_connect('close_event', handle_close) # listen to close event
    ax = figure.add_subplot()
    ax.set_title('Throughput')
    ax.set_ylabel('RESTCONF requests/second')
    ax.set_xlabel('Seconds')
    line, = ax.plot(x, y)
    line2, = ax.plot(x, y)
    plt.axis([0, 300, 0, args.yaxis])
    ax.legend((line, line2), ('ok', 'nok'), loc='lower right', shadow=True)

    def func_animate():
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


    thread = Thread(target=request_thread, args=(args, q, plt))
    thread.start()

    try:
        t = time.monotonic()+2
        while close_flag == 0:
            # Update every two seconds
            nt = time.monotonic()
            if nt>t:
                func_animate()
                t = nt+2

            #ax.relim() # recompute the axes limits.
            #ax.autoscale_view() # update the axes limits.

            figure.canvas.draw() # draw the figure
            figure.canvas.flush_events() # flush the GUI events for the figure.
            # plt.show(block=False)
            time.sleep(0.1) # wait a little bit of time

            if close_flag == 1:
                break
    except KeyboardInterrupt:
        pass
    if stop_requests == False:
        asyncio.run_coroutine_threadsafe(set_event(stop_event), event_loop)
    print('stopped')
    stop_requests = True
    sys.exit(0)

if __name__ == '__main__':
    main(parseArgs())
