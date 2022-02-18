#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

#
# Base to start scripting with NSO
#

"""
TODO:
 - Use argParse
"""


import sys
import time

import ncs

m = ncs.maapi.Maapi()
s = ncs.maapi.Session(m, "admin", "system")

#t = ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE)
#r = ncs.maagic.get_root(t)a

n = int(sys.argv[1])
n_devices = int(sys.argv[2])
p_devices = 100

do_create_devices = True
while do_create_devices:
    with ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE) as t:
        x = n
        start = time.monotonic()
        for _ in range(0, p_devices):
            r = ncs.maagic.get_root(t)
            device = r.devices.device
            ce = device.create(f'ce{n}')
            ce.address = 'localhost'
            ce.port = 30000#+n
            ce.device_type.netconf.ned_id = "router-nc-1.0"
            ce.authgroup = "default"
            ce.state.admin_state = "unlocked"
            n += 1
            if n>=n_devices: break
        t.apply()
        elap = time.monotonic()-start
        print(f"Devices {x}-{n-1} created in ", elap, "seconds.")
        if n>=n_devices:
            do_create_devices = False
            break
