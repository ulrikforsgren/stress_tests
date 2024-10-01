#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import argparse
import copy
import csv
from datetime import datetime
import sys
import time

import ncs
import psutil

from stress_testing.stress_testing import \
    Parameters, Sequence, SequenceRequest, \
    RandomString, RandomValue, SequenceRequestRandomized, \
    do_test
from create_devices import create_device, find_capabilities

# Scale parameters
numvlan = 20
devices_batch_size = 100000
create_batch_size = 10000
update_batch_size = 100
cpu_check_delay = 5

# TODO: Add "name" to distinguish between different sets of parameters
# TODO: Randomize device id to spread the load
parameters = Parameters({
    "sid": RandomString(15, seed=0, keep_state=True),
    "did": Sequence(0, keep_state=True),
    "data": RandomString(15),
    "numvlan": numvlan
})


create_parameters = copy.deepcopy(parameters)
load_parameters = copy.deepcopy(parameters)
update_parameters = copy.deepcopy(parameters)
delete_parameters = copy.deepcopy(parameters)


CREATE = {
            'op': 'create',
            'url': '/python-service:python-service',
            'data': '''{
                        "service":{
                            "name":"<<sid>>",
                            "device":"r<<did>>",
                            "template":["vlans"],
                            "str-value":"<<data>>",
                            "num-vlan":<<numvlan>>
                        }
                    }'''
}

LOAD = {
            'op': 'update',
            'url': '/python-service:python-service/'+
                   'python-service:service=<<sid>>',
            'data': '''{
                        "service":{
                        "template":["one-leaf", "vlans"]
                        }
                    }'''
}

UPDATE = {
             'op': 'update',
             'url': '/python-service:python-service/'+
                    'python-service:service=<<sid>>',
             'data': '''{
                        "service":{
                            "str-value":"<<data>>",
                            "num-vlan":<<numvlan>>
                        }
                    }'''
}

DELETE = {
            'op': 'delete',
            'url': '/python-service:python-service/'+
                   'python-service:service=<<sid>>'
}            

#
# Command line arguments
#


def parseArgs(args=None, extra_actions=[]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str,
                        help='host[:port]',
                        default='localhost:8080')
    parser.add_argument('cmd', nargs='+', choices=['clean', 'run', 'clean'])
    parser.add_argument("--dry-run", required=False, action='store_true', default=False,
                        help="Run sequence but do not send request over network.")
    parser.add_argument("--echo", required=False, action='store_true', default=False,
                        help="Echo request to console.")
    parser.add_argument("--keep-state", required=False, action='store_true', default=False,
                        help="Loads state if state files exist and saves after run.")
    parser.add_argument("-n", required=False, type=int,
                        help='Number of total requests.')
    parser.add_argument("-w", required=False, type=int, default=40,
                        help='Max window size. Starting 1, 2, 5, .., max')
    parser.add_argument("-s", required=False, type=str,
                        help='Window size(s) comma sepated.')
    parser.add_argument("-p", required=False, type=str, action='append',
                        help='Alter parameters.')
    parser.add_argument("-v", required=False, action='store_true',
                        default=False, help='Verbose mode. Show result of each request.')
    parser.add_argument("-o", required=False, type=str,
                        help='Output result in json format to file.')
    parser.add_argument("--highlight", required=False, action='store_true',
                        default=False, help='Highlight output to make it more readable.')
    return parser.parse_args(args)


#
# Process metrics and statistics
#


def get_info(p):
    with p.oneshot():
        mem = p.memory_info()[0] # RSS
        cpu_perc = p.cpu_percent()
        cpu_times = p.cpu_times()
    return (mem, cpu_perc, cpu_times)


def get_pids(name):
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] == name:
            yield p.pid
    return [ get_pids(name) ]


def get_ncs_process():
    pids = list(get_pids('ncs.smp')) + list(get_pids('beam.smp'))
    if len(pids) == 0:
        print("No ncs.smp processes are running.")
        sys.exit(1)
    elif len(pids) > 1:
        print("There are multiple ncs.smp processes running:")
        print_pids(pids)
        print("Use -p/--pid to monitor one.")
        sys.exit(1)
    return psutil.Process(pid=pids[0])


#
# Logging
#

def nso_metrics():
    N64 = True
    with ncs.maapi.single_read_trans('admin', 'system') as t:
        r = ncs.maagic.get_root(t)
        no_devices = len(r.devices.device)
        no_services = len(r.python_service__python_service.service)
        running = r.ncs_state.internal.cdb.datastore['running']
        disk_size = running.disk_size
        ram_size = running.ram_size
        cdb = r.metric.sysadmin.counter.cdb
        # Only for NSO 6.4-
        load_retries = cdb.load_retries if N64 else 0
        total_service_offloads = cdb.total_service_offloads if N64 else 0
        total_device_offloads = cdb.total_device_offloads if N64 else 0
        total_offload_memory = cdb.total_offload_memory if N64 else 0
    return (no_devices, no_services, disk_size, ram_size,
            load_retries, total_service_offloads,
            total_device_offloads, total_offload_memory)


def get_log(p):
    def log(name, info):
        print(datetime.now().isoformat(), name, info, nso_metrics(), get_info(p), flush=True)
    return log


def wait_for_cpu_to_idle(p, delay, threshold=5):
    start = time.monotonic()
    time.sleep(delay)
    while True:
        mem, cpu_perc, cpu_times = get_info(p)
        if cpu_perc < threshold:
            break
        time.sleep(1)
    print('CPU idle after', time.monotonic()-start, 'seconds')


#
# Test functions
#

def run_test(args, intent, n, n_p, parameters, task=None):
    # TODO: Move host to context?
    intent['host'] = args.host
    #parameters.load_state()
    
    elapsed, ok, total, nok, exc, results = do_test(
        args, n, n_p, intent, parameters)
    if nok>0:
        print(results)
    #parameters.save_state()

    return (elapsed, ok, nok, exc)


def create_devices(name, start, n_devices):
    n = 0
    batch_size = 100
    start_time =  time.monotonic()

    do_create_devices = True
    while do_create_devices:
        with ncs.maapi.single_write_trans('admin', 'system') as t:
            r = ncs.maagic.get_root(t)
            n_s = n
            n_c = 0
            for _ in range(0, batch_size):
                create_device(r.devices, f'{name}{start+n}', 'localhost',
                              10000, 'cli', 'cisco-ios-cli-3.0', 'default',
                              False)
                n += 1
                n_c += 1
                if n_c>=batch_size or n>n_devices: break
            t.apply()
            for i in range(0, n_c):
                find_capabilities(r.devices, f'{name}{start+n_s+i}')
            if n>=n_devices:
                do_create_devices = False
                break

    return time.monotonic()-start_time



# Executor
#

def run(args):
    args.no_networking = True
    args.commit_queue = True

    #columns = ['timestamp', 'create-devices', 'create', 'load', 'wait_cpu_idle_time', 'update', 'number_of_devices', 'number_of_services']
    #result_file = open(f'result-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv', 'w')
    #result_writer = csv.DictWriter(result_file, columns, extrasaction='ignore')
    #result_writer.writeheader()

    ncs_process = get_ncs_process()
    log = get_log(ncs_process)

    log('start', None)

    # create initial devices 
    log('create-devices', create_devices('r', 0, devices_batch_size))

    # Create a base set of services
    for _ in range(10):
        log('create', run_test(args, CREATE, create_batch_size, 15, create_parameters))
        log('load', run_test(args, LOAD, create_batch_size, 15, load_parameters))
        wait_for_cpu_to_idle(ncs_process, cpu_check_delay)
    # Update the services
    n = 0
    dn = 0
    while True:
        if n%10 == 0:
            dn+=1
            log('create-devices', create_devices('r', dn*devices_batch_size, devices_batch_size))
            #break
        log('create', run_test(args, CREATE, create_batch_size, 15, create_parameters))
        log('load', run_test(args, LOAD, create_batch_size, 15, load_parameters))
        wait_for_cpu_to_idle(ncs_process, cpu_check_delay)
        log('update', run_test(args, UPDATE, update_batch_size, 15, update_parameters))
        n += 1


def clean(args):
    args.no_networking = True
    args.commit_queue = True
    run_test(args, DELETE, 200, 15, delete_parameters)


def main(args):
    if args.cmd[0] == 'run':
        run(args)
    elif args.cmd[0] == 'clean':
        clean(args)
    else:
        print('Unknown command:', args.cmd[0])
if __name__ == '__main__':
    main(parseArgs())
