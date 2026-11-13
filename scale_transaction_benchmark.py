#!/usr/bin/env python3
"""Measure NSO write transaction timings while device counts increase.

Service callbacks use the ``module:function`` convention from
concurrent_maapi_transactions.py and receive
``(worker_name, transaction, maagic_root, intent)``. Each callback is run in
its own transaction and must populate it without calling ``apply()``.
"""

import argparse
from importlib import import_module
import os
import re
import shutil
import sys
import time
from typing import NamedTuple

import ncs
import yaml

import device_manager


#DEFAULT_DEVICE_STEPS = [10, 1000, 2000, 5000, 10000, 20000]
DEFAULT_DEVICE_STEPS = [10, 20, 50]

_COLOR_MODE = 'auto'
_ANSI_ESCAPE = re.compile(r'\033\[[0-9;]*m')
_RESET = '\033[0m'
_BOLD = '\033[1m'
_DIM = '\033[2m'
_RED = '\033[31m'
_GREEN = '\033[32m'
_YELLOW = '\033[33m'
_BLUE = '\033[34m'
_CYAN = '\033[36m'


class Intent(NamedTuple):
    name: str
    i: int


def colorize(text, *codes):
    """Add ANSI styling when color output is enabled."""
    stream = getattr(sys.stdout, 'console', sys.stdout)
    enabled = (
        _COLOR_MODE == 'always'
        or (_COLOR_MODE == 'auto'
            and os.environ.get('NO_COLOR') is None
            and getattr(stream, 'isatty', lambda: False)())
    )
    if not enabled:
        return text
    return ''.join(codes) + text + _RESET


def strip_color(text):
    return _ANSI_ESCAPE.sub('', text)


def parse_device_steps(value):
    if isinstance(value, str):
        parts = value.split(',')
    elif isinstance(value, (list, tuple)):
        parts = value
    else:
        raise argparse.ArgumentTypeError(
            'device steps must be a comma-separated string or a list')
    try:
        steps = [int(part) for part in parts]
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            'device steps must contain integers') from exc
    if not steps or any(step < 1 for step in steps):
        raise argparse.ArgumentTypeError(
            'device steps must contain positive integers')
    if steps != sorted(set(steps)):
        raise argparse.ArgumentTypeError(
            'device steps must be strictly increasing')
    return steps


def list_ned_ids(args):
    """Return NED IDs from devices.ned-ids."""
    with ncs.maapi.Maapi() as maapi:
        with ncs.maapi.Session(maapi, args.user, args.context):
            with maapi.start_read_trans(db=ncs.OPERATIONAL) as transaction:
                root = ncs.maagic.get_root(transaction)
                return [entry.id for entry in root.devices.ned_ids.ned_id]


def print_ned_ids(ned_ids):
    for ned_id in ned_ids:
        print(ned_id, flush=True)


def check_ned_id(args):
    """Exit if the requested NED ID is not in devices.ned-ids."""
    ned_ids = list_ned_ids(args)
    if any(ned_id.split(':', 1)[-1] == args.nid for ned_id in ned_ids):
        return
    print(colorize(
        f'NED ID {args.nid!r} was not found. Available NED IDs:',
        _BOLD, _RED), flush=True)
    print_ned_ids(ned_ids)
    sys.exit(1)


def load_callback(spec):
    module_name, separator, function_name = spec.partition(':')
    if not separator or not module_name or not function_name:
        raise ValueError('function must use the form module:callable')
    callback = getattr(import_module(module_name), function_name)
    if not callable(callback):
        raise ValueError(f'{spec!r} does not refer to a callable')
    return callback


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='YAML file containing benchmark options.')
    parser.add_argument('--save-config', metavar='FILE',
                        help='Save the effective options to a YAML file.')
    parser.add_argument('--device-steps', default=DEFAULT_DEVICE_STEPS,
                        help='Cumulative device targets, e.g. 10,1000,2000.')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Maximum devices created per transaction.')
    parser.add_argument('--device-start', type=int, default=0,
                        help='Starting numeric suffix for device names.')
    parser.add_argument('--name', default='r',
                        help='Device name prefix (as in device_manager.py).')
    parser.add_argument('--address', default='localhost',
                        help='First device address.')
    parser.add_argument('--address-count', type=int, default=1,
                        help='Number of consecutive device addresses.')
    parser.add_argument('--port', type=int, default=10000,
                        help='Starting device port.')
    parser.add_argument('--port-count', type=int, default=1000,
                        help='Number of ports available per address.')
    parser.add_argument('--type', choices=['cli', 'netconf'], default='cli',
                        help='NSO device type.')
    parser.add_argument('--nid', default='cisco-ios-cli-6.109',
                        help='NED ID for devices.')
    parser.add_argument('--list-nedids', action='store_true',
                        help='List available NED IDs and exit.')
    parser.add_argument('--authgroup', default='default',
                        help='Authentication group assigned to devices.')
    parser.add_argument('--admin-state', default='southbound-locked',
                        help='Device admin state (default: southbound-locked).')
    parser.add_argument('--accept-out-of-sync', dest='accept_out_of_sync',
                        action='store_true', default=False,
                        help='Allow commits for out-of-sync devices.')
    parser.add_argument('--no-accept-out-of-sync', dest='accept_out_of_sync',
                        action='store_false', help=argparse.SUPPRESS)
    parser.add_argument('--no-fetch-host-keys', dest='fetch_host_keys',
                        action='store_false', default=True,
                        help='Skip ssh fetch-host-keys after device creation.')
    parser.add_argument('--device-batch-delay', type=float, default=0.0,
                        help='Pause between device creation batches.')
    parser.add_argument('--device-service-delay', type=float, default=1.0,
                        help='Pause after device creation before services.')
    parser.add_argument('--step-delay', type=float, default=1.0,
                        help='Pause between device-count steps.')
    parser.add_argument('-f', '--function', metavar='MODULE:CALLABLE',
                        help='Service-population callback, like in concurrent_maapi_transactions.py.')
    parser.add_argument('--service-count', type=int, default=10,
                        help='Services to create at each device-count step.')
    parser.add_argument('--service-delay', type=float, default=0.1,
                        help='Pause between service transactions.')
    parser.add_argument('--user', default='admin', help='NSO user.')
    parser.add_argument('--context', default='system', help='NSO context.')
    parser.add_argument('--output',
                        help='Also write the console output to this file '
                             '(default: a timestamped log file).')
    parser.add_argument('--color', choices=['auto', 'always', 'never'],
                        default='auto',
                        help='Colorize console output (default: auto).')
    return parser


def parse_args(argv=None):
    argv = list(argv) if argv is not None else None
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument('--config')
    bootstrap_args, _ = bootstrap.parse_known_args(argv)

    config_values = {}
    if bootstrap_args.config:
        with open(bootstrap_args.config, encoding='utf-8') as config_file:
            config_values = yaml.safe_load(config_file) or {}
        if not isinstance(config_values, dict):
            raise ValueError('config file must contain a YAML mapping')
        allowed = {action.dest for action in build_parser()._actions}
        unknown = set(config_values) - allowed
        if unknown:
            raise ValueError('unknown config option(s): ' + ', '.join(sorted(unknown)))

    parser = build_parser()
    if config_values:
        parser.set_defaults(**config_values)
    args = parser.parse_args(argv)
    try:
        args.device_steps = parse_device_steps(args.device_steps)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    for name in ('batch_size', 'address_count', 'port_count'):
        if getattr(args, name) < 1:
            parser.error(f'--{name.replace("_", "-")} must be at least 1')
    if args.device_start < 0:
        parser.error('--device-start must be non-negative')
    if args.service_count < 0:
        parser.error('--service-count must be non-negative')
    for name in ('device_batch_delay', 'device_service_delay',
                 'step_delay', 'service_delay'):
        if getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be non-negative')
    if args.admin_state == 'southbound-locked':
        args.fetch_host_keys = False

    return args


def save_config(args):
    values = {
        key: value for key, value in vars(args).items()
        if key not in ('config', 'save_config')
    }
    with open(args.save_config, 'w', encoding='utf-8') as config_file:
        yaml.safe_dump(values, config_file, sort_keys=False)
    print(f'Saved effective configuration to {args.save_config}', flush=True)


def run_transaction(args, populate):
    full_start = time.perf_counter()
    setup_start = time.perf_counter()
    with ncs.maapi.single_write_trans(
            args.user, args.context, db=ncs.RUNNING) as transaction:
        transaction_setup = time.perf_counter() - setup_start

        populate_start = time.perf_counter()
        root = ncs.maagic.get_root(transaction)
        populate(root, transaction)
        populate_time = time.perf_counter() - populate_start

        apply_start = time.perf_counter()
        transaction.apply()
        apply_time = time.perf_counter() - apply_start

    return {
        'transaction_setup_s': transaction_setup,
        'populate_s': populate_time,
        'apply_s': apply_time,
        'total_s': time.perf_counter() - full_start,
    }


def print_timing(label, timing, overwrite=False):
    total = f'{timing["total_s"]:.6f}s'
    message = (
        f'{colorize(label + ":", _BOLD, _CYAN)} '
        f'{colorize("transaction-setup=", _DIM)}'
        f'{timing["transaction_setup_s"]:.6f}s '
        f'{colorize("populate=", _DIM)}{timing["populate_s"]:.6f}s '
        f'{colorize("apply=", _DIM)}{timing["apply_s"]:.6f}s '
        f'{colorize("total=", _BOLD)}'
        f'{colorize(total, _BOLD, _GREEN)}'
    )
    if overwrite:
        console = getattr(sys.stdout, 'console', sys.stdout)
        console.write('\r\033[K' + message)
        console.flush()
        log = getattr(sys.stdout, 'log', None)
        if log is not None:
            log.write(strip_color(message) + '\n')
            log.flush()
        return
    print(message, flush=True)


def prepare_devices(args, first_number, count):
    """Run the device actions required before the devices are used."""
    with ncs.maapi.Maapi() as maapi:
        with ncs.maapi.Session(maapi, args.user, args.context):
            root = ncs.maagic.get_root(maapi)
            find_start = time.perf_counter()
            for number in range(first_number, first_number + count):
                name = f'{args.name}{number}'
                device_manager.find_capabilities(root.devices, name)
            find_time = time.perf_counter() - find_start

            fetch_time = 0.0
            if args.fetch_host_keys:
                fetch_start = time.perf_counter()
                for number in range(first_number, first_number + count):
                    name = f'{args.name}{number}'
                    device_manager.fetch_host_keys(root.devices, name)
                fetch_time = time.perf_counter() - fetch_start

    total = f'{find_time + fetch_time:.6f}s'
    print(
        f'{colorize("Prepared:", _BOLD, _BLUE)}           '
        f'find-capabilities={find_time:.6f}s '
        f'ssh/fetch_host_keys={fetch_time:.6f}s '
        f'{colorize("total=", _BOLD)}'
        f'{colorize(total, _BOLD, _GREEN)}',
        flush=True,
    )


def create_devices(args, first_number, count):
    total_batches = (count + args.batch_size - 1) // args.batch_size
    created = 0
    for batch_number in range(1, total_batches + 1):
        batch_count = min(args.batch_size, count - created)
        batch_start = first_number + created

        def populate(root, _transaction):
            for offset in range(batch_count):
                number = batch_start + offset
                address, port = device_manager.device_endpoint(
                    number, args.address, args.address_count,
                    args.port, args.port_count)
                device_manager.create_device(
                    root, f'{args.name}{number}', address, port,
                    args.type, args.nid, args.authgroup,
                    args.accept_out_of_sync, args.admin_state)

        metrics = run_transaction(args, populate)
        device_range = f'{args.name}{batch_start}'
        if batch_count > 1:
            device_range += f'-{args.name}{batch_start + batch_count - 1}'
        print_timing(
            f'Device batch {batch_number}/{total_batches} '
            f'({batch_count} devices, {device_range})',
            metrics, overwrite=True)
        if batch_number == total_batches:
            print(flush=True)
        created += batch_count
        if args.device_batch_delay and batch_number < total_batches:
            time.sleep(args.device_batch_delay)
    return created


def create_services(args, callback, target_devices, first_intent):
    for offset in range(args.service_count):
        intent_number = first_intent + offset
        intent = Intent(name=f'service-{intent_number:06d}', i=intent_number)

        def populate(root, transaction):
            stdout = sys.stdout
            if hasattr(stdout, 'log'):
                sys.stdout = stdout.log
            try:
                callback('scale-benchmark', transaction, root, intent)
            finally:
                sys.stdout = stdout

        timing = run_transaction(args, populate)
        print_timing(
            f'Create Service:     {offset + 1}/{args.service_count} '
            f'({intent.name})', timing,
            overwrite=True)
        if args.service_delay and offset + 1 < args.service_count:
            time.sleep(args.service_delay)
    print(flush=True)
    return args.service_count


def delete_services(args, target_devices, first_intent):
    """Delete the services created for this step, one transaction at a time."""
    for offset in range(args.service_count):
        intent_number = first_intent + offset
        service_name = f'S{intent_number}'

        def populate(root, _transaction, name=service_name):
            del root.python_service.service[name]

        timing = run_transaction(args, populate)
        print_timing(
            f'Delete service:     {offset + 1}/{args.service_count} '
            f'({service_name})', timing,
            overwrite=True)
        if args.service_delay and offset + 1 < args.service_count:
            time.sleep(args.service_delay)
    print(flush=True)


class _Tee:
    """Write each chunk to the console and the log file."""

    def __init__(self, console, log):
        self.console = console
        self.log = log
        self.streams = (console, log)

    def write(self, data):
        self.console.write(data)
        self.log.write(strip_color(data))
        self.flush()
        return len(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return self.streams[0].isatty()


def open_output_log(args):
    path = args.output or time.strftime(
        'scale_transaction_benchmark-%Y%m%d-%H%M%S.log')
    log_file = open(path, 'w', encoding='utf-8', buffering=1)
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)
    print(f'Writing output to {path}', flush=True)
    return log_file


def main(argv=None):
    global _COLOR_MODE

    args = parse_args(argv)
    _COLOR_MODE = args.color
    stdout, stderr = sys.stdout, sys.stderr
    log_file = open_output_log(args)
    try:
        return run(args)
    finally:
        sys.stdout, sys.stderr = stdout, stderr
        log_file.close()


def run(args):
    if args.save_config:
        save_config(args)
        sys.exit(0)
    if args.list_nedids:
        print_ned_ids(list_ned_ids(args))
        sys.exit(0)

    check_ned_id(args)
    callback = load_callback(args.function) if args.function else None
    if callback is None:
        print(colorize(
            'No -f callback supplied; service transactions will be skipped.',
            _YELLOW), flush=True)

    existing_total = 0
    intent_index = 0
    scale_start = time.perf_counter()
    for step_index, target_devices in enumerate(args.device_steps):
        if target_devices <= existing_total:
            continue
        add_count = target_devices - existing_total
        
        print(colorize(
            f'\nScaling to {target_devices} devices (adding {add_count})',
            _BOLD, _BLUE), flush=True)
        created = create_devices(
            args, args.device_start + existing_total, add_count)

        prepare_devices(args, args.device_start + existing_total, add_count)
        
        existing_total += created

        service_create_phase_time = 0.0
        service_delete_phase_time = 0.0
        if callback and args.service_count:
            if args.device_service_delay:
                time.sleep(args.device_service_delay)
            service_create_start = time.perf_counter()
            created_services = create_services(
                args, callback, target_devices, intent_index)
            service_create_phase_time = time.perf_counter() - service_create_start
            service_delete_start = time.perf_counter()
            delete_services(args, target_devices, intent_index)
            service_delete_phase_time = time.perf_counter() - service_delete_start
            intent_index += created_services

        print(colorize(
            f'Scale {target_devices} complete: '
            f'device_phase={created:.6f}s '
            f'service_create_phase={service_create_phase_time:.6f}s '
            f'service_delete_phase={service_delete_phase_time:.6f}s '
            f'elapsed={time.perf_counter() - scale_start:.6f}s',
            _BOLD, _GREEN), flush=True)
        if args.step_delay and step_index + 1 < len(args.device_steps):
            time.sleep(args.step_delay)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
