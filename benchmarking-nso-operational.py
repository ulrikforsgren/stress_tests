#!/usr/bin/env python3
"""Collect NSO operational counters and serve them to the benchmarking UI."""

import argparse
import asyncio
import logging
import time
from types import SimpleNamespace

import grpc
import ncs

from benchmarking_metrics import (
    MetricsStore,
    UIServicer,
    notifications,
    ui_pb2,
    ui_pb2_grpc,
)


DEFAULT_METRIC_PATH = (
    '/metric/sysadmin/counter/transaction/datastore{running}')
METRIC_VALUE_COUNT = 9
OK_INDEX = 1
NOK_INDEX = 7


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=int, default=3600,
                        help='How many seconds of metrics to retain.')
    parser.add_argument('--metrics-db', default='benchmarking-metrics.db',
                        help='SQLite database used to persist metrics.')
    parser.add_argument('--interval', type=float, default=1.0,
                        help='Seconds between metric samples.')
    parser.add_argument('--metric-path', action='append', dest='metric_paths',
                        help=('MAAPI object path containing nine values. '
                              'Can be repeated; values at indexes 1 and 7 '
                              'are summed as OK and NOK.'))
    parser.add_argument('--user', default='admin',
                        help='NSO user for the MAAPI session.')
    parser.add_argument('--context', default='system',
                        help='NSO CLI context for the MAAPI session.')
    parser.add_argument('--grpc-address', default='[::]:50052',
                        help='Address for the benchmarking UI gRPC API.')
    args = parser.parse_args()
    if args.history < 1:
        parser.error('--history must be at least 1 second')
    if args.interval <= 0:
        parser.error('--interval must be greater than zero')
    args.metric_paths = args.metric_paths or [DEFAULT_METRIC_PATH]
    return args


def read_metric_values(transaction, metric_paths):
    """Read each metric object in one MAAPI call and sum its OK/NOK fields."""
    ok = 0
    nok = 0
    for path in metric_paths:
        values = transaction.get_object(METRIC_VALUE_COUNT, path)
        if values is None or len(values) != METRIC_VALUE_COUNT:
            raise ValueError(
                f'{path} returned {0 if values is None else len(values)} '
                f'values; expected {METRIC_VALUE_COUNT}')
        ok += int(values[OK_INDEX].as_pyval())
        nok += int(values[NOK_INDEX].as_pyval())
    return ok, nok


async def collect_metrics(transaction, store, args):
    next_prune = time.monotonic() + 60
    previous_reading = None
    while True:
        current_reading = read_metric_values(transaction, args.metric_paths)
        if previous_reading is None:
            # The first value is only a baseline; it has no preceding sample
            # from which to calculate a delta.
            previous_reading = current_reading
        else:
            previous_ok, previous_nok = previous_reading
            current_ok, current_nok = current_reading
            # If a counter was reset, count from zero after the reset.
            ok = (current_ok - previous_ok
                  if current_ok >= previous_ok else current_ok)
            nok = (current_nok - previous_nok
                   if current_nok >= previous_nok else current_nok)
            previous_reading = current_reading
            timestamp, ok, nok = store.record(time.time(), ok, nok)
            await notifications.emit(ui_pb2.Metric(
                timestamp=timestamp,
                ok=ok,
                nok=nok,
            ))

        if time.monotonic() >= next_prune:
            store.prune(args.history)
            next_prune = time.monotonic() + 60
        await asyncio.sleep(args.interval)


async def main(args):
    store = MetricsStore(args.metrics_db)
    store.prune(args.history)
    server = grpc.aio.server()
    ui_pb2_grpc.add_UIServicer_to_server(
        UIServicer(SimpleNamespace(history=args.history), store), server)
    server.add_insecure_port(args.grpc_address)

    try:
        await server.start()
        logging.info('Benchmarking UI API listening on %s', args.grpc_address)
        while True:
            try:
                with ncs.maapi.Maapi() as maapi:
                    with ncs.maapi.Session(maapi, args.user, args.context):
                        # Keep one operational read transaction open until it
                        # fails; reconnect below if NSO drops the session.
                        with maapi.start_read_trans(
                                db=ncs.OPERATIONAL) as transaction:
                            logging.info('Reading NSO operational metrics from %s',
                                         ', '.join(args.metric_paths))
                            await collect_metrics(transaction, store, args)
            except Exception:
                logging.exception(
                    'NSO connection or read failed; retrying in 1 second')
                await asyncio.sleep(1)
    finally:
        await server.stop(None)
        store.close()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        logging.info('Stopped')
