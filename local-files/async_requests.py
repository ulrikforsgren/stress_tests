#!/usr/bin/env python
# -*- coding: utf-8; mode: python; python-indent: 4 -*-

import asyncio
import requests
import time


async def func():
    r = requests.get('http://localhost:8088/restconf/data/model/name')
    return r.status_code


async def main():
    results = []
    for i in range(100):
        results.append(await func())
    return results


if __name__ == '__main__':
    start = time.time()
    print(asyncio.run(main()))
    end = time.time()
    print(end - start)
