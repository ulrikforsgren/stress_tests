import asyncio
import copy
import json
import os
import os.path as path
import pprint as pp
import sys

from .executors import sliding_window_executor
from .functions import (
    set_flags,
    calc_average,
    np_gen,
    replace_chars
)
from .parameters import format_parameters
from .terminal import ansi
from .gen_chart import generate_html

pprint = pp.PrettyPrinter(indent=4).pprint


###############################################################################
#  RUNNER FUNCTIONS
###############################################################################
#

def do_test(args, task_args, parameters, want_results=True, task_func=None, request_cb=None):
    set_flags(args, task_args)
    elapsed, results = asyncio.run(
        sliding_window_executor(args, task_args, parameters, want_results=want_results, task_func=task_func, request_cb=request_cb))
    if want_results:
        if args.v:
            pprint(results)

        # TODO: Refactor analysis of the results and want_results. No stats is returned when want_results is False.
        count, total, count_wrong, count_exc = calc_average(results)

        return elapsed, count, total, count_wrong, count_exc, results
    return elapsed


#
# Run test in subprocess to ensure proper isolation/cleanup between test iterations.
#
def run_test_in_subprocess(args, test_func, task_args, parameters, task_func=None, do_print=False):
    task_args = copy.deepcopy(task_args)
    parameters = copy.deepcopy(parameters)
    result = test_func(args, task_args, parameters, task_func=task_func)
    elapsed, count, total, count_wrong, count_exc, results = result
    if count:
        average = total/count
    else:
        average = -1.0
    if do_print:
        op = task_args['op'].upper()
        n_p = parameters['concurrency']
        print(f'{op:<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}', flush=True)
    return elapsed, count, total, average, count_wrong, count_exc, results


def run_tests(args, testcases, tests, parameters, no_requests, max_concurrency, task_func=None, do_print=False):
    no_requests = args.n or no_requests

    max_concurrency = min(max_concurrency, no_requests)
    if args.w:
        max_concurrency = min(args.w, no_requests)

    if not args.s:
        n_ps = [n for n in np_gen(max_concurrency)]
    else:
        n_ps = list(map(int, args.s.split(',')))

    print()
    parameters.update_cmdline(args.p)
    parameters['stop'] = no_requests
    if '__info' in tests:
        info = tests['__info']
        if 'name' in info:
            name = format_parameters(parameters, info['name'], update=False)
            if args.highlight:
                print(ansi.BOLD, end='')
                print(ansi.REVERSE, end='')
            print(f'==== {name} ====')
            if args.highlight:
                print(ansi.RST, end='')
            print()

    results = []
    for r, n_p in enumerate(n_ps):
        if args.highlight and r % 2 == 1:
            print(ansi.DIM, end='')
        for op in testcases:
            task_args = tests[op]
            # TODO: Should host be in task_args? parameters is better?
            task_args['host'] = args.host
            parameters['concurrency'] = n_p
            results.append((op, no_requests, n_p, run_test_in_subprocess(
                args, do_test, task_args, parameters, task_func=task_func, do_print=do_print)))
        if args.highlight and r % 2 == 1:
            print(ansi.RST, end='')
    if args.o:
        open(args.o, "w").write(json.dumps(results))
    if args.html:
        dirs, fname = path.split(sys.argv[0])
        name, ext = path.splitext(fname)
        oname = f'{name}-{args.n}-{args.p}-{args.w}-{args.s}.html'
        oname = replace_chars(oname, '_', ',=')
        generate_html(oname, '', oname, results)
        print()
        print("Wrote html file:", oname)
        if args.open:
            import webbrowser
            webbrowser.open(f'file://{path.join(os.getcwd(), oname)}')
    return results


def run_single_test(args, tc, tests, parameters, task_func=None):
    n = args.n or 1
    n_p = args.w or 1
    task_args = tests[tc]
    task_args['host'] = args.host
    if args.keep_state:
        parameters.load_state()
    parameters.update_cmdline(args.p)
    if args.echo:
        print(str(parameters))
    elapsed, count, total, count_wrong, count_exc, results = do_test(
        args, task_args, parameters, task_func=task_func)
    if count:
        average = total/count
    else:
        average = -1
    if args.echo:
        print(str(parameters))
    if args.keep_state:
        parameters.save_state()
    if not args.q:
        print()
        print("Total time:         ", elapsed)
        print("Count OK:           ", count)
        print("Per second:         ", count/elapsed)
        print("Average per request:", average)
        print("Wrong status:       ", count_wrong)
        print("Exceptions:         ", count_exc)

    return elapsed, count, total, average, count_wrong, count_exc, results

#
# Used in legacy tests
#
def run_test(args, tests, parameters, n=500, max_p=40, task_func=None, do_print=True):
    if args.cmd == ['clean']:
        parameters['stop'] = 1
        parameters['concurrency'] = 1
        run_single_test(args, 'clean', tests, parameters)
    else:
        tc = []
        for c in args.cmd:
            if c == 'crud':
                tc += ['create', 'read', 'update', 'delete']
            elif c == 'cud':
                tc += ['create', 'update', 'delete']
            else:
                tc.append(c)

        if args.single:
            run_single_test(args, tc[0], tests, parameters, task_func=task_func)
        else:
            run_tests(args, tc, tests, parameters, n, max_p, task_func, do_print=do_print)
