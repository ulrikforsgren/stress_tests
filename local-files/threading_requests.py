#!/usr/bin/env python
# -*- coding: utf-8; mode: python; python-indent: 4 -*-

import requests
import threading
import time


def func():
    r = requests.get('http://localhost:8088/restconf/data/model/name')
    return r.status_code


def main():
    threads = []
    for i in range(100):
        t = threading.Thread(target=func)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()


if __name__ == '__main__':
    start = time.time()
    print(main())
    end = time.time()
    print(end - start)
