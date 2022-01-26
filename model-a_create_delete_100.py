#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

from multiprocessing import Pool

import stress_model_a

import pprint as pp
pprint = pp.PrettyPrinter(indent=4).pprint

def do_test(n, n_ps, do_print=False):
    results = []
    for n_p in n_ps:
        with Pool(processes=1) as pool:
            res = pool.apply(stress_model_a.do_test,('create', n, n_p))
            elapsed, count, total, count_wrong, count_exc = res
            if count:
                average=total/count
            else:
                average = -1
            result = count, n_p, elapsed, total, average
            if do_print:
                print(f'CREATE {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}')
            #TODO: Return wrong and exc as well...
            results.append((count, n_p, elapsed, total, average))
            pool.close()
        with Pool(processes=1) as pool:
            res = pool.apply(stress_model_a.do_test,('delete', n, n_p))
            elapsed, count, total, count_wrong, count_exc= res
            if count:
                average=total/count
            else:
                average = -1
            result = count, n_p, elapsed, total, average
            if do_print:
                print(f'DELETE {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}')
            results.append((count, n_p, elapsed, total, average))
            pool.close()
    return results

if __name__ == '__main__':
    results = do_test(100, [1, 2, 5, 10, 20, 40, 100], do_print=True)
