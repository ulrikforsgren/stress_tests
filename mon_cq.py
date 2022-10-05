#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import asyncio
import json
from multiprocessing import Pool
import pprint as pp
import random
import time

import aiohttp

from stress_testing.restconf_api import REQ_DISPATCH, setup, teardown, restconf_request

HOST='localhost'
PORT=8080

pprint = pp.PrettyPrinter(indent=4).pprint

async def get_metrics(client, host):
    url = '/tailf-ncs:metric/sysadmin/gauge/commit-queue'
    op = 'read'
    resp = await restconf_request(client,
                                  host,
                                  op,
                                  url)
    return resp



async def monitor(host):
    conn = aiohttp.TCPConnector(limit=0)
    client = aiohttp.ClientSession(connector=conn)
    while True:
        result = await get_metrics(client, host)
        print(result)
        await asyncio.sleep(2)
    await client.close()


def main():
    asyncio.run(monitor('localhost:8080'))


if __name__ == '__main__':
    main()
