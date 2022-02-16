#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

#
# Base to start scripting with NSO
#

import ncs

m = ncs.maapi.Maapi()
s = ncs.maapi.Session(m, "admin", "system")

#t = ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE)
#r = ncs.maagic.get_root(t)a

n = 0
n_devices = 10000
p_devices = 10

do_create_devices = True
while do_create_devices:
    with ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE) as t:
        x = n
        for _ in range(0, p_devices):
            r = ncs.maagic.get_root(t)
            device = r.devices.device
            ce = device.create(f'ce{n}')
            ce.address = 'localhost'
            ce.port = 30000+n
            ce.device_type.netconf.ned_id = "router-nc-1.0"
            ce.authgroup = "default"
            ce.state.admin_state = "unlocked"
            n += 1
            if n>=n_devices: break
        t.apply()
        print(f"Devices {x}-{n-1} created.")
        if n>=n_devices:
            do_create_devices = False
            break
