#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import sys
import time

import ncs


NEDIDs = {
    'router':    [ 'netconf', 'router-nc-1.0' ],
    'ios-cli':   [ 'cli',     'cisco-ios-cli-3.0' ],
    'nx-cli':    [ 'cli',     'cisco-nx-cli-5.22' ],
    'iosxr-cli': [ 'cli',     'cisco-iosxr-cli-7.38' ],
}


def parseArgs(cmd_args):
    parser = argparse.ArgumentParser(cmd_args)
    parser.add_argument('-n', '--name', required=True, default='ce',
                        help="Device name")
    parser.add_argument('-c', '--count', type=int, default=1,
                        help="Number of devices to create")
    parser.add_argument('-p', '--port', type=int, default=10000,
                        help="Starting port number")
    parser.add_argument('-a', '--address', type=str, default='localhost',
                        help="Device address")
    parser.add_argument('-t', '--type',
                        choices=['ios-cli', 'nx-cli', 'ios-xr', 'router'],
                        default='ios-cli',
                        help="Type of device")
    parser.add_argument('--accept-out-of-sync',
                        action='store_true', default=False,
                        help="Device address")
    return parser.parse_args()


def create_device(devices, name, address, port, t, nedid, authgrp,
                  accept_out_of_sync=False):
    device = devices.device
    dev = device.create(name)
    dev.address = address
    dev.port = port
    if t=='cli':
        dev.device_type.cli.ned_id = nedid
    elif t=='netconf':
        dev.device_type.netconf.ned_id = nedid
    dev.authgroup = authgrp
    dev.state.admin_state = "unlocked"
    if accept_out_of_sync:
        dev.out_of_sync_commit_behaviour = 'accept'
    else:
        dev.out_of_sync_commit_behaviour = 'reject'

def main(args):
    n = 0
    n_devices = args.count
    p_devices = 100

    do_create_devices = True
    while do_create_devices:
        with ncs.maapi.single_write_trans('admin', 'system') as t:
            x = n
            start = time.monotonic()
            for _ in range(0, p_devices):
                r = ncs.maagic.get_root(t)
                dt, nedid = NEDIDs[args.type]
                create_device(r.devices, f'{args.name}{n}', args.address,
                              args.port+n, dt, nedid, 'default',
                              args.accept_out_of_sync)
                n += 1
                if n>=n_devices: break
            t.apply()
            elap = time.monotonic()-start
            print(f"Devices {args.name}{x}-{args.name}{n-1} created in ", elap, "seconds.")
            if n>=n_devices:
                do_create_devices = False
                break

if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))
