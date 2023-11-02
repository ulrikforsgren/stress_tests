#!/usr/bin/env python
# -*- coding: utf-8; mode: python; python-indent: 4 -*-
def printt(string):
    width=20
    string = str(string).strip()
    if len(string) > width:
        string = string[:width-3].strip() + '...'
    print(string)

import asyncio
import aiohttp
import time


async def func(session):
    r = await session.get('http://localhost:8088'
                          '/restconf/data/model/name')
    return r.status


async def main():
    results = []
    session = aiohttp.ClientSession()
    tasks = []
    for i in range(100):
        tasks.append(asyncio.create_task(func(session)))
    results = await asyncio.gather(*tasks)
    await session.close()
    return results


if __name__ == '__main__':
    start = time.time()
    print(asyncio.run(main()))
    end = time.time()
    print(end - start)
