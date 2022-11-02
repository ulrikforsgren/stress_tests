# -*- mode: python; python-indent: 4 -*-

import asyncio
from base64 import b64encode
import json
import aiohttp
from yarl import URL

HEADERS_JSON={
    'Accept':'application/yang-data+json',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping the data
    'Content-type': 'application/yang-data+json',
    'Authorization': 'Basic %s' % b64encode(b"admin:admin").decode("ascii")
}


# Expected response status for successful requests.
REQ_DISPATCH = {
    'create': ('POST', [201]),
    'read':   ('GET', [200]),
    'update': ('PATCH', [200, 204]),
    'set': ('PUT', [204]),
    'delete': ('DELETE', [200, 204]),
    'action': ('POST', [200, 204])
}

# This method is an extension of TCPConnector to setup an number of connections
# prior to doing requests
async def setup_pool_connections(self, conn, host, n_p):
    req = aiohttp.ClientRequest('GET', URL(f'http://{host}'))
    timeout = aiohttp.ClientTimeout(total=5 * 60)
    key = req.connection_key
    assert self._get(key) is None, "No connections should be setup at this time."
    connections = []
    for _ in range(0, n_p):
        proto = await self._create_connection(req, [], timeout)
        connections.append((proto, self._loop.time()))
    conn._conns[key] = connections


async def setup(args):
    aiohttp.TCPConnector.setup_pool_connections = setup_pool_connections
    conn = aiohttp.TCPConnector(limit=0) # No limit of parallel connections
    client = aiohttp.ClientSession(connector=conn)
    args['client'] = client


async def teardown(args):
    await args['client'].close()


request_id = 0
async def restconf_request(client, host, op, resource, data=None,
                           resource_type='data', params=None):
    global request_id
    request_id += 1
    rid = request_id
    method, expected_status = REQ_DISPATCH[op]
    url = f'http://{host}/restconf/{resource_type}{resource}'
    if params is not None:
        # aiohttp request uses yarl.URL is used for params and can not handle
        # params without equal sign (=). Putting them directly in the url instead.
        url += '?' + params
    try:
        if data is not None:
              data=data.encode('utf-8')
        async with client.request(method, url, headers=HEADERS_JSON,
                                  data=data) as response:
            if response.status in [ 201, 204 ]:
                data = None # No content is expected.
            else:
                if response.headers['Content-Type'] == 'application/yang-data+json':
                    data = await response.json()
                else:
                    data = await response.text()
            res = 'ok' if response.status in expected_status else 'nok'
            return (rid, res, response.status, data)
    except Exception as e:
        return (rid, 'exception', repr(e))


async def single_request(host, op, url, data=None):
    conn = aiohttp.TCPConnector(limit=0)
    client = aiohttp.ClientSession(connector=conn)
    resp = await restconf_request(client,
                                  host,
                                  op,
                                  url,
                                  data=json.dumps(data))
    await client.close()
    return resp


def run_single_request(host, op, url, data=None):
    return asyncio.run(single_request(host, op, url, data=data))
