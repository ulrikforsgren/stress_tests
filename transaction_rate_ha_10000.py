#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import io
import queue
import random
import socket
import sys
import time

"""
TODO:
 - Options for hosts, no. transations, ...
 - Test that HA is working.
 - Support for high-availability
"""


from stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue, single_request,\
                           stress_requests_window

from ctrl_ha import get_ha_status, set_ha_state


def p(*args, **kwargs):
    pass
    #print(*args, **kwargs)


async def test_transaction_rate_ha(leader, follower, n):
    parameters = Parameters({
        "id": SequenceRequest(0, wrap=100),
        "data": RandomValue(0, 4000000000),
    })
    args = {
            'op': 'update',
            'url': '/model-a:model-a/model-a:list=K{id}',
            'data': '''{{
                        "list":{{
                            "str-value":"Changed string data {data}"
                        }}
                    }}''',
            'parameters': parameters
    }
    args['host'] = leader

    # Turn off HA
    p(await set_ha_state(leader))
    p(await set_ha_state(follower))
    p(await get_ha_status(leader))
    p(await get_ha_status(follower))

    start = time.monotonic()
    p(len(await stress_requests_window(n, 10, setup, teardown,
                                       default_task, args)))
    elapsed_without_ha = time.monotonic()-start

    await asyncio.sleep(4)
    p(await set_ha_state(leader, 'master'))
    await asyncio.sleep(1)
    p(await set_ha_state(follower, 'slave'))
    await asyncio.sleep(5)
    p(await get_ha_status(leader))
    p(await get_ha_status(follower))

    start = time.monotonic()
    p(len(await stress_requests_window(n, 10, setup, teardown,
                                       default_task, args)))
    elapsed_with_ha = time.monotonic()-start

    print("Without HA:", elapsed_without_ha, n/elapsed_without_ha)
    print("With HA:   ", elapsed_with_ha, n/elapsed_with_ha)

    return (elapsed_without_ha, elapsed_with_ha)


async def test_main(n, i):
    leader, follower = sys.argv[1:3]
    n_total = 0
    wo_total = 0
    wi_total = 0
    for _ in range(0, i):
        wo, wi = await test_transaction_rate_ha(leader, follower, n)
        wo_total += wo
        wi_total += wi
        n_total += n

    print("Total without HA:", wo_total, n_total/wo_total)
    print("Total with HA:   ", wi_total, n_total/wi_total)

if __name__=='__main__':
    asyncio.run(test_main(1000, 20))

