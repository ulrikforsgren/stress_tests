#!/usr/bin/env python
# -*- coding: utf-8; mode: python; python-indent: 4 -*-
def printt(string):
    width=20
    string = str(string).strip()
    if len(string) > width:
        string = string[:width-3].strip() + '...'
    print(string)

import asyncio
import requests
import time


async def func():
    r = requests.get('http://localhost:8088'
                     '/restconf/data/model/name')
    return r.status_code


async def main():
    tasks = []
    for i in range(100):
        tasks.append(asyncio.create_task(func()))
    results = await asyncio.gather(*tasks)
    return results


if __name__ == '__main__':
    start = time.time()
    print(asyncio.run(main()))
    end = time.time()
    print(end - start)
