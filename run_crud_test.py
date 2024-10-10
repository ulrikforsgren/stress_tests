#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import os
import sys
import importlib.util


from stress_testing.runners import (
    run_tests,
    run_single_test
)
from stress_testing.argparser import parseArgs


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
    if args.cmd == ['clean']:
        parameters['stop'] = 1
        parameters['concurrency'] = 1
        run_single_test(args, 'clean', tests, parameters)
    else:
        testcases = []
        for c in args.cmd:
            if c == 'crud':
                testcases += ['create', 'read', 'update', 'delete']
            elif c == 'cud':
                testcases += ['create', 'update', 'delete']
            else:
                testcases.append(c)

        run_tests(args, testcases, tests, parameters, 500, 40, do_print=True)


if __name__ == '__main__':
    main(parseArgs(options='crud', path='tests'))
