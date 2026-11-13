#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import ipaddress
import sys
import time

import ncs


def default_ned_id(version):
    major, minor = (int(part) for part in version.split('.', 2)[:2])
    if major > 6 or (major == 6 and minor >= 4):
        return 'cisco-ios-netsim-cli-1.0'
    return 'cisco-ios-cli-3.0'


def parseArgs(cmd_args):
    parser = argparse.ArgumentParser(cmd_args)
    parser.add_argument('-n', '--name', required=False, default='r',
                        help="Device name")
    parser.add_argument('-g', '--group', default='g',
                        help="Group name")
    parser.add_argument('-c', '--count', type=int, default=1,
                        help="Number of devices to create")
    parser.add_argument('-i', type=int, default=0,
                        help="Starting device number")
    parser.add_argument('-p', '--port', type=int, default=10000,
                        help="Starting port number")
    parser.add_argument('-m', '--port-count', type=int, default=1000,
                        help="Number of ports available per address")
    parser.add_argument('-a', '--address', type=str, default='localhost',
                        help="First device address")
    parser.add_argument('--address-count', type=int, default=1,
                        help="Number of consecutive device addresses")
    parser.add_argument('-t', '--type',
                        choices=['cli', 'netconf'],
                        default='cli',
                        help="Type of device")
    parser.add_argument('--nid', type=str,
                        default=None,
                        help="Type of device")
    parser.add_argument('--accept-out-of-sync',
                        action='store_true', default=False,
                        help="Device address")
    parser.add_argument('--admin-state', type=str,
                        default='southbound-locked',
                        help="Administrative state for created devices")
    parser.add_argument('--find', action='store_true',
                        help="Find capabilities for newly created devices")
    parser.add_argument('cmd',
                        choices=['create', 'create-config', 'delete', 'find', 'fetch', 'sync-from',
                                 'create-group', 'list-ned-ids'],
                        help="Command")
    return parser.parse_args()


parameters = {
    'create': {
            'needs_transaction': True,
            'p_devices': 100
        },
    'create-config': {
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
    'create-config': 'created',
    'delete': 'deleted',
    'find': 'capabilities found',
    'fetch': 'fetch ssh host keys'
}


def create_device(r, name, address, port, t, nedid, authgrp,
                  accept_out_of_sync=False, admin_state='southbound-locked'):
    device = r.devices.device
    dev = device.create(name)
    dev.address = address
    dev.port = port
    if t=='cli':
        dev.device_type.cli.ned_id = nedid
    elif t=='netconf':
        dev.device_type.netconf.ned_id = nedid
    dev.authgroup = authgrp
    dev.state.admin_state = admin_state
    if accept_out_of_sync:
        dev.out_of_sync_commit_behaviour = 'accept'
    else:
        dev.out_of_sync_commit_behaviour = 'reject'


def create_device_config(r, name):
    device = r.python_service.device
    dev = device.create(name)
    dev.config.interface.FastEthernet.create('0/1')

def device_endpoint(device_number, start_address, address_count,
                    start_port, port_count):
    if address_count < 1:
        raise ValueError("--address-count must be at least 1")
    if port_count < 1:
        raise ValueError("--port-count must be at least 1")

    if address_count == 1:
        address = start_address
    else:
        try:
            address = str(ipaddress.ip_address(start_address) +
                          device_number % address_count)
        except ValueError as exc:
            raise ValueError(
                "--address must be an IP address when --address-count is greater than 1"
            ) from exc

    port = start_port + (device_number // address_count) % port_count
    return address, port


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
    m = ncs.maapi.Maapi()
    s = ncs.maapi.Session(m, "admin", "system")
    if args.cmd == 'list-ned-ids':
        t = ncs.maapi.Transaction(m, db=ncs.OPERATIONAL,rw=ncs.READ)
        r = ncs.maagic.get_root(t)
        ned_ids = set()
        for e in r.devices.ned_ids.ned_id:
            print(e.id)
        return

    if args.nid is None:
        t = ncs.maapi.Transaction(m, db=ncs.OPERATIONAL, rw=ncs.READ)
        r = ncs.maagic.get_root(t)
        args.nid = default_ned_id(str(r.ncs_state.version))

    n = args.i
    n_devices = args.count
    p_devices = parameters[args.cmd]['p_devices']

    do_stuff = True
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
            dt = args.type
            nedid = args.nid
            if args.cmd == 'create':
                address, port = device_endpoint(
                    n, args.address, args.address_count,
                    args.port, args.port_count)
                create_device(r, f'{args.name}{n}', address,
                              port, dt, nedid, 'default',
                              args.accept_out_of_sync, args.admin_state)
            elif args.cmd == 'create-config':
                create_device_config(r, f'{args.name}{n}')
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
        if args.cmd == 'create' and args.find:
            r = ncs.maagic.get_root(m)
            for device_number in range(x, n):
                find_capabilities(r.devices, f'{args.name}{device_number}')
        if parameters[args.cmd]['needs_transaction']:
            t = ncs.maapi.Transaction(m, db=ncs.RUNNING,rw=ncs.READ_WRITE)
        elap = time.monotonic()-start
        dnames = f"{args.name}{x}-{args.name}{n-1}" if n-x>1 else f"{args.name}{x}"
        print(f"Devices {dnames} {cmd_text[args.cmd]} in ", elap, "seconds.")
        if n>=n_devices:
            do_stuff = False
            break

if __name__ == '__main__':
    main(parseArgs(sys.argv[1:]))
