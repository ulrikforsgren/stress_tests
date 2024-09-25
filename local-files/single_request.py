#!/usr/bin/env python
# -*- coding: utf-8; mode: python; python-indent: 4 -*-
def printt(string):
    width=20
    string = str(string).strip()
    if len(string) > width:
        string = string[:width-3].strip() + '...'
    print(string)




import requests
import time


def func():
    r = requests.get('http://localhost:8088'
                     '/restconf/data/model/name')
    return r.status_code


def main():
    return func()


if __name__ == '__main__':
    start = time.time()
    print(main())
    end = time.time()
    print(end - start)
