#!/usr/bin/env python3
"""Run one job from the benchmarking-nso job directory."""

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path


BENCHMARKING_MODULE_PATH = Path(__file__).with_name('benchmarking-nso.py')
SPEC = importlib.util.spec_from_file_location('benchmarking_nso', BENCHMARKING_MODULE_PATH)
benchmarking_nso = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmarking_nso)


def parse_parameter(value):
    if '=' not in value:
        raise argparse.ArgumentTypeError("parameters must use KEY=VALUE format")
    key, raw_value = value.split('=', 1)
    if not key:
        raise argparse.ArgumentTypeError("parameter name cannot be empty")
    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed_value = raw_value
    return key, parsed_value


async def drain_results(queue):
    while True:
        await queue.get()


async def run_job(args, name, job_data, overrides):
    params = dict(benchmarking_nso.global_parameters)
    params.update({'host': args.host, 'add_to_metrics': False})
    parameters = benchmarking_nso.Parameters(params)
    queue = asyncio.Queue()
    drain_task = asyncio.create_task(drain_results(queue))
    try:
        if callable(job_data):
            await job_data(args, parameters, cmd_params=overrides, result_queue=queue)
        else:
            await benchmarking_nso.job(args, parameters, job_data,
                                       cmd_params=overrides, result_queue=queue)
    finally:
        drain_task.cancel()
        await asyncio.gather(drain_task, return_exceptions=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', help='Job name (filename without .py)')
    parser.add_argument('--path', default='jobs', help='Directory containing job modules')
    parser.add_argument('--host', default='localhost:8080', help='NSO host[:port]')
    parser.add_argument('-p', '--param', action='append', type=parse_parameter, default=[],
                        metavar='KEY=VALUE', help='Override a job parameter (repeatable; values accept JSON)')
    args = parser.parse_args(argv)
    jobs = benchmarking_nso.get_jobs(args.path)
    if args.job not in jobs:
        parser.error(f"unknown job '{args.job}'. Available jobs: {', '.join(sorted(jobs))}")
    overrides = dict(args.param)
    try:
        asyncio.run(run_job(args, args.job, jobs[args.job], overrides))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
