#!/usr/bin/env python3

import datetime
import logging
import os
import pprint as pp
import sys

from display import color,tableize
from http_requests import HaStatus, HaMember, execute_requests

pprint = pp.PrettyPrinter(indent=4).pprint
pformat = pp.PrettyPrinter(indent=4).pformat

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M:%S',filename='ha_status_http_stress.log',filemode='a')
#handler = logging.StreamHandler(sys.stdout)
#handler.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#handler.setFormatter(formatter)
#logger.addHandler(handler)

logger.debug('===========================================')
logger.debug('Checking status and config on NSO system(s)')
logger.debug('===========================================')

RESULT = [   {   'connected': [   {'currenct_role': 'slave', 'node': 'n3'},
                         {'currenct_role': 'slave', 'node': 'n2'}],
        'current_role': 'master',
        'ip': '172.18.1.2',
        'node': 'n1'},
    {   'connected': [{'currenct_role': 'master', 'node': 'n1'}],
        'current_role': 'slave',
        'ip': '172.18.2.2',
        'node': 'n2'},
    {   'connected': [{'currenct_role': 'master', 'node': 'n1'}],
        'current_role': 'slave',
        'ip': '172.18.2.3',
        'node': 'n3'},
    {   'ip': '172.18.1.2',
        'members': [   {   'address': '172.18.1.2',
                           'default-ha-role': 'master',
                           'failover-master': '',
                           'node': 'n1'},
                       {   'address': '172.18.2.2',
                           'default-ha-role': 'slave',
                           'failover-master': True,
                           'node': 'n2'},
                       {   'address': '172.18.2.3',
                           'default-ha-role': 'slave',
                           'failover-master': False,
                           'node': 'n3'}],
        'node': 'n1'},
    {   'ip': '172.18.2.2',
        'members': [   {   'address': '172.18.1.2',
                           'default-ha-role': 'master',
                           'failover-master': '',
                           'node': 'n1'},
                       {   'address': '172.18.2.2',
                           'default-ha-role': 'slave',
                           'failover-master': True,
                           'node': 'n2'},
                       {   'address': '172.18.2.3',
                           'default-ha-role': 'slave',
                           'failover-master': False,
                           'node': 'n3'}],
        'node': 'n2'},
    {   'ip': '172.18.2.3',
        'members': [   {   'address': '172.18.1.2',
                           'default-ha-role': 'master',
                           'failover-master': '',
                           'node': 'n1'},
                       {   'address': '172.18.2.2',
                           'default-ha-role': 'slave',
                           'failover-master': True,
                           'node': 'n2'},
                       {   'address': '172.18.2.3',
                           'default-ha-role': 'slave',
                           'failover-master': False,
                           'node': 'n3'}],
        'node': 'n3'}]

nodes = [
    {
        'ip': u'172.18.1.2',
        'node': u'n1'
    },{
        'ip': u'172.18.2.2',
        'node': u'n2'
    },{
        'ip': u'172.18.2.3',
        'node': u'n3'
    }
]

def ALL(nodes, request):
    return [request(host=node, port=8080, ssl=False) for node in nodes]

while True:
    logger.debug('------------------------------------------------')
    st_cmds = ALL(nodes, HaStatus)
    cfg_cmds = ALL(nodes, HaMember)
    results = execute_requests(st_cmds+cfg_cmds)
    datas = [ result['data'] for result in results]
    if datas == RESULT:
        print(datetime.datetime.now(), "=== OK")
    else:
        print(datetime.datetime.now(), "=== NOK")
        pprint(datas)
