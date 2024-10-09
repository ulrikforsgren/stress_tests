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
    parser.add_argument('-g', '--group', default='g',
                        help="Group name")
    parser.add_argument('-c', '--count', type=int, default=1,
                        help="Number of devices to create")
    parser.add_argument('-i', type=int, default=0,
                        help="Starting device number")
    parser.add_argument('-p', '--port', type=int, default=10000,
                        help="Starting port number")
    parser.add_argument('-m', type=int, default=0,
                        help="Wrap port number using: 'c + i mod m.'")
    parser.add_argument('-a', '--address', type=str, default='localhost',
                        help="Device address")
    parser.add_argument('-t', '--type',
                        choices=['ios-cli', 'nx-cli', 'ios-xr', 'router'],
                        default='ios-cli',
                        help="Type of device")
    parser.add_argument('--accept-out-of-sync',
                        action='store_true', default=False,
                        help="Device address")
    parser.add_argument('cmd',
                        choices=['create', 'delete', 'find', 'fetch', 'sync-from',
                                 'create-group'],
                        help="Command")
    return parser.parse_args()


parameters = {
    'create': {
            'needs_transaction': True,
            'p_devices': 100
        },
    'delete': {
            'needs_transaction': True,
            'p_devices': 100
        },
    'find': {
            'needs_transaction': False,
            'p_devices': 1
        },
    'fetch': {
            'needs_transaction': False,
            'p_devices': 1
        }
}

cmd_text = {
    'create': 'created',
    'delete': 'deleted',
    'find': 'capabilities found',
    'fetch': 'fetch ssh host keys'
}


def create_device(r, name, address, port, t, nedid, authgrp,
                  accept_out_of_sync=False):
    device = r.devices.device
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


def find_capabilities(devices, name):
    device = devices.device
    dev = device[name]
    result = dev.find_capabilities()
    return result


def fetch_host_keys(devices, name):
    device = devices.device
    dev = device[name]
    result = dev.ssh.fetch_host_keys()
    return result


def main(args):
    n = args.i
    n_devices = args.count
    p_devices = parameters[args.cmd]['p_devices']

    do_stuff = True
    m = ncs.maapi.Maapi()
    s = ncs.maapi.Session(m, "admin", "system")
    while do_stuff:
        if parameters[args.cmd]['needs_transaction']:
            t = ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE)
        x = n
        start = time.monotonic()
        for _ in range(0, p_devices):
            if parameters[args.cmd]['needs_transaction']:
                r = ncs.maagic.get_root(t)
            else:
                r = ncs.maagic.get_root(m)
            dt, nedid = NEDIDs[args.type]
            if args.cmd == 'create':
                create_device(r, f'{args.name}{n}', args.address,
                              args.port+n%1000, dt, nedid, 'default',
                              args.accept_out_of_sync)
            elif args.cmd == 'delete':
                del r.devices.device[f'{args.name}{n}']
            elif args.cmd == 'find':
                result = find_capabilities(r.devices, f'{args.name}{n}')
#                print(result)
            elif args.cmd == 'fetch':
                result = fetch_host_keys(r.devices, f'{args.name}{n}')
#                print(result)
            elif args.cmd == 'create-group':
                result = fetch_host_keys(r.devices, f'{args.name}{n}')
#                print(result)
            n += 1
            if n>=n_devices: break
        if parameters[args.cmd]['needs_transaction']:
            t.apply()
            t = ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE)
        elap = time.monotonic()-start
        dnames = f"{args.name}{x}-{args.name}{n-1}" if n-x>1 else f"{args.name}{x}"
        print(f"Devices {dnames} {cmd_text[args.cmd]} in ", elap, "seconds.")
        if n>=n_devices:
            do_stuff = False
            break

if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))
