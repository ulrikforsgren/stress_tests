#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import sys

from aiohttp import web
from aiohttp.helpers import AppKey


routes = web.RouteTableDef()
n = pn = 0


requests_monitor_task = AppKey('requests_monitor', asyncio.Task)
async def requests_monitor():
    global n, pn
    while True:
        if n != pn:
            print(f"Total number of processed requests: {n}")
            pn = n
        await asyncio.sleep(5)

async def background_tasks(app):
    app[requests_monitor_task] = asyncio.create_task(requests_monitor())

    yield

    app[requests_monitor_task].cancel()
    await app[requests_monitor_task]


# READ
@routes.get('/restconf/data/{model}/{name}')
async def get_handler(request):
    global n
    n += 1
    await asyncio.sleep(0.02)
    #await asyncio.sleep(1)
    return web.json_response(data={'status': 'ok'}, status=200)

# CREATE
@routes.post('/restconf/data/{model}')
async def post_handler(request):
    global n
    n += 1
    await asyncio.sleep(0.01)
    return web.Response(status=201)

# UPDATE
@routes.patch('/restconf/data/{model}/{name}')
async def patch_handler(request):
    global n
    n += 1
    #await asyncio.sleep(0.02)
    return web.Response(status=204)

# DELETE
@routes.delete('/restconf/data/{model}/{name}')
async def delete_handler(request):
    global n
    n += 1
    await asyncio.sleep(0.03)
    return web.Response(status=204)

def main(argv):
    app = web.Application()
    app.cleanup_ctx.append(background_tasks)
    app.add_routes(routes)
    return app

if __name__ == '__main__':
    web.run_app(main(sys.argv), port = 8088)

