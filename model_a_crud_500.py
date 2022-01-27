#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

from multiprocessing import Pool

from model_a_tests import do_test

import pprint as pp
pprint = pp.PrettyPrinter(indent=4).pprint

def run_test_in_subprocess(func, op, n, n_p, do_print=False):
    with Pool(processes=1) as pool:
        res = pool.apply(func, (op, n, n_p))
        elapsed, count, total, count_wrong, count_exc = res
        if count:
            average=total/count
        else:
            average = -1
        result = count, n_p, elapsed, total, average
        if do_print:
            print(f'{op.upper():<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}')
        pool.close()
        #TODO: Return wrong and exc as well...
        return (count, n_p, elapsed, total, average)

def run_tests(n, n_ps, do_print=False):
    results = []
    for n_p in n_ps:
        for op in ['create', 'read', 'update', 'delete']:
            results.append(run_test_in_subprocess(do_test, op, n, n_p, do_print))
    return results

if __name__ == '__main__':
    results = run_tests(500, [1, 2, 5, 10, 20, 40, 100], do_print=True)
