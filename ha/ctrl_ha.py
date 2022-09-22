#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import asyncio
import io
import queue
import random
import socket
import sys
import time

from stress_testing import setup, teardown, default_task, Parameters,\
                           SequenceRequest, RandomValue, single_request


async def get_ha_status(host):
    args = {
            'op': 'read',
            'url': '/tailf-ncs-monitoring:ncs-state/ha'
    }
    args['host'] = host
    status = await single_request(args)
    return status


async def set_ha_state(host, mode='none'):
    args = {
            'op': 'action',
            'url': f'/ha:ha-config/be-{mode}',
            'resource_type': 'operations'
    }
    args['host'] = host
    status = await single_request(args)
    return status

async def main():

    # Turn off HA
    print(await set_ha_state('localhost:8090'))
    print(await set_ha_state('localhost:8080'))

    # single_request(turn_off_ha)
    print(await get_ha_status('localhost:8080'))
    print(await get_ha_status('localhost:8090'))

    print(await set_ha_state('localhost:8080', 'master'))
    await asyncio.sleep(1)

    print(await set_ha_state('localhost:8090', 'slave'))
    await asyncio.sleep(1)

    print(await get_ha_status('localhost:8080'))
    print(await get_ha_status('localhost:8090'))

if __name__=='__main__':
    asyncio.run(main())
