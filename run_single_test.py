#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import os
import sys
import importlib.util

from stress_testing.stress_testing import (
    parseArgs,
    run_single_test
)


def load_test(args):
    # TODO: Load tests from a specified file when test has '.py' extension
    if args.test.endswith('.py'):
        module_name = args.test[:-3]
        spec = importlib.util.spec_from_file_location(f'{module_name}', f'{os.getcwd()}/{args.test}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'tests'):
            parameters = module.parameters if hasattr(module, 'parameters') else {}
            return module.tests, parameters
    else:
        jobs_directory_path = f'{os.path.dirname(os.path.abspath(__file__))}/{args.path}'
        files = os.listdir(jobs_directory_path)
        filename = f'{args.test}.py'
        if filename in files:
                module_name = args.test
                spec = importlib.util.spec_from_file_location(f'jobs.{module_name}', f'{jobs_directory_path}/{filename}')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'tests'):
                    parameters = module.parameters if hasattr(module, 'parameters') else {}
                    # TODO: Chech for available operations. create, read, update, delete required for CRUD.
                    return module.tests, parameters
                else:
                    print(f"ERROR: Failed to load test. '{module_name}' does not contain 'tests'")
                    sys.exit(1)

        print(f"ERROR: Failed to load test. '{filename}' not found in path {jobs_directory_path}")
        sys.exit(1)


def main(args):
    tests, parameters = load_test(args)
    testcases = []

    parameters['stop'] = args.n
    parameters['concurrency'] = 1

    if args.operation not in tests:
        print(f"ERROR: Failed to load test. '{args.operation}' not found in tests")
        sys.exit(1)

    run_single_test(args, args.operation, tests, parameters)


if __name__ == '__main__':
    main(parseArgs(options='single', path='tests'))
