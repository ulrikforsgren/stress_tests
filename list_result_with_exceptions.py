#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

import json
import sys

if __name__ == '__main__':
    name = sys.argv[1]
    results = json.load(open(name))

    for res_p in results:
        op,n,n_p,res_rtp = res_p
        elapsed,count,_,average,count_wrong,count_exc,res_r = res_rtp
        print(f'{op.upper():<6} {count:>5} {n_p:>3} {elapsed:>5.1f} {count/elapsed:>6.1f} {average:>6.3f} {count_wrong:>5} {count_exc:>5}')
        for r in res_r:
            if r[1] == 'exception':
                print(r)

