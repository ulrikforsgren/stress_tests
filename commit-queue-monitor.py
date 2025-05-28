#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
from datetime import datetime
import json
import sys

from stress_testing import restconf_api
from stress_tests.terminal import ansi


def parseArgs(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', type=str, default='localhost:8080',
                        help='node:[port]')
    parser.add_argument('-s', type=int, default=100,
                        help='Max bar size.')
    parser.add_argument('-t', action='store_true', default=False,
                        help='Show data as a table.')
    return parser.parse_args(args)


async def get_notifications(streams, restconf):
    await asyncio.gather(*[restconf.get_stream(s) for s in streams])


def get_logger(q):
    async def log(host, api, msg_type, **kwargs):
        msg = {
            'timestamp': datetime.isoformat(datetime.now()),
            'host': host,
            'api': api,
            'type': msg_type
        }
        msg.update(kwargs)
        await q.put(msg)
    return log


async def get_and_decode_cq_event(q, state):
    cqitems = state['cqitems']
    msg = await q.get()
    q.task_done()
    if msg['type'] == 'stream':
        if 'data' in msg:
            data = json.loads(msg['data'])
            n = data['ietf-restconf:notification']
            if 'tailf-ncs:ncs-commit-queue-progress-event' in n:
                e = n['tailf-ncs:ncs-commit-queue-progress-event']
                # print(f"{n['eventTime']} {e['id']} {e['state']}")
                i = e['id']
                s = e['state']
                stored_state = cqitems.get(i)
                if s == 'locked':
                    if stored_state == 'waiting':
                        state['waiting'] -= 1
                    state['locked'] += 1
                    cqitems[i] = s
                elif s == 'waiting':
                    if stored_state == 'locked':
                        state['locked'] -= 1
                    state['waiting'] += 1
                    cqitems[i] = s
                elif s == 'executing':
                    if stored_state == 'waiting':
                        state['waiting'] -= 1
                    if stored_state != 'executing':
                        state['executing'] += 1
                    cqitems[i] = s
                elif s == 'completed':
                    if stored_state == 'executing':
                        state['executing'] -= 1
                    state['completed'] += 1
                    if stored_state is not None:
                        del cqitems[i]
                elif s == 'failed':
                    if stored_state == 'executing':
                        state['executing'] -= 1
                    state['failed'] += 1
                    if stored_state is not None:
                        del cqitems[i]
                else:
                    print(f'UNKOWN STATE: {e} {stored_state}{ansi.RST}')


async def logger(args, q):
    try:
        # Variables to store the current commit-queue states
        state = {
            'cqitems': {},
            'locked': 0,
            'waiting': 0,
            'executing': 0,
            'completed': 0,
            'failed': 0
        }
        if args.t:
            from rich.live import Live
            from rich.bar import Bar
            from rich.console import Group
            from rich.table import Table
            from rich.text import Text
            from rich.color import Color
            # The table and contained objects
            table = Table(title="NSO Commit Queue Monitor")
            table.add_column("Metrics", min_width=12)
            table.add_column("Value", min_width=3)
            table.add_column("", min_width=3)
            t_locked = Text('0')
            b_locked = Bar(begin=0, end=0, size=args.s)
            table.add_row('Locked', t_locked, b_locked)
            t_waiting = Text('0')
            b_waiting = Bar(begin=0, end=0, size=args.s)
            table.add_row('Waiting', t_waiting, b_waiting)
            t_executing = Text('0', style='yellow')
            b_executing = Bar(begin=0, end=0, size=args.s, color='yellow')
            table.add_row('Executing', t_executing, b_executing)
            t_completed = Text('0', style='green')
            table.add_row('Completed', t_completed)
            t_failed = Text('0', style='red')
            table.add_row('Failed', t_failed)

            # The loop updating the table
            with Live(table) as live:
                while True:
                    await get_and_decode_cq_event(q, state)
                    t_locked.plain = str(state['locked'])
                    b_locked.end = state['locked']
                    t_waiting.plain = str(state['waiting'])
                    b_waiting.end = state['waiting']
                    t_executing.plain = str(state['executing'])
                    b_executing.end = state['executing']
                    t_completed.plain = str(state['completed'])
                    t_failed.plain = str(state['failed'])
        else:
            while True:
                await get_and_decode_cq_event(q, state)
                print(f"Locked {ansi.BOLD}{state['locked']:<8}{ansi.RST}"
                      f"Waiting {ansi.BOLD}{state['waiting']:<8}{ansi.RST}"
                      f"Executing {ansi.BOLD}{ansi.YELLOW}{state['executing']:<8}{ansi.RST}"
                      f"Completed {ansi.BOLD}{ansi.GREEN}{state['completed']:<8}{ansi.RST}"
                      f"Failed {ansi.BOLD}{ansi.RED}{state['failed']:<8}{ansi.RST}")
    except Exception as e:
        print(f'EXCEPTION: {e}')


async def subscribe_for_notifications(args, client, q,
                                      user='admin', password='admin',
                                      node='localhost:8081'):

    log = get_logger(q)
    connections = []
    restconf = restconf_api.RESTCONF(args.n, user, password,
                                     client=client, log=log)

    tasks = []
    tasks.append(asyncio.create_task(get_notifications(['ncs-events'], restconf),
                                     name='notif_task'))
    tasks.append(asyncio.create_task(logger(args, q),
                                     name='logger_task'))

    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in tasks:
        t.cancel()
    return await asyncio.gather(*tasks, return_exceptions=True)


async def main(args):
    try:
        client = restconf_api.get_client()
        q = asyncio.Queue()
        print(await subscribe_for_notifications(args, client, q, node=args.n))
    except Exception as e:
        print(f'EXCEPTION: {e}')
    finally:
        await client.close()

if __name__ == '__main__':
    try:
        asyncio.run(main(parseArgs()))
    except Exception as e:
        print(f'EXCEPTION: {e}')
    except KeyboardInterrupt:
        pass
