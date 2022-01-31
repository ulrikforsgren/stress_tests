#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import sys

from aiohttp import web


routes = web.RouteTableDef()

@routes.get('/restconf/data/{model}/{name}')
async def get_handler(request):
    return web.Response(status=200)

@routes.post('/restconf/data/{model}')
async def post_handler(request):
    await asyncio.sleep(0.01)
    return web.Response(status=201)

@routes.patch('/restconf/data/{model}/{name}')
async def patch_handler(request):
    await asyncio.sleep(0.02)
    return web.Response(status=204)

@routes.delete('/restconf/data/{model}/{name}')
async def delete_handler(request):
    await asyncio.sleep(0.03)
    return web.Response(status=204)

def main(argv):
    app = web.Application()
    app.add_routes(routes)
    return app

if __name__ == '__main__':
    main(sys.argv)
