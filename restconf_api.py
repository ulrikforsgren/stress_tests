# -*- mode: python; python-indent: 4 -*-

from base64 import b64encode
import aiohttp


HEADERS_JSON={
    'Accept':'application/yang-data+json',
    'Accept-Encoding': 'identity', # Prevent NSO from gzipping the data
    'Content-type': 'application/yang-data+json',
    'Authorization': 'Basic %s' % b64encode(b"admin:admin").decode("ascii")
}


# Expected response status for successful requests.
REQ_DISPATCH = {
    'create': ('POST', 201),
    'read':   ('GET', 200),
    'update': ('PATCH', 204),
    'delete': ('DELETE', 204),
    'action': ('POST', 204)
}


async def setup(args):
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
    try:
        if data is not None:
              data=data.encode('utf-8')
        async with client.request(method, url, headers=HEADERS_JSON,
                                  data=data,
                                  params=params) as response:
            if response.status in [ 201, 204 ]:
                data = None # No content is expected.
            else:
                if response.headers['Content-Type'] == 'application/yang-data+json':
                    data = await response.json()
                else:
                    data = await response.text()
            res = 'ok' if response.status == expected_status else 'nok'
            return (rid, res, response.status, data)
    except Exception as e:
        return (rid, 'exception', repr(e))
