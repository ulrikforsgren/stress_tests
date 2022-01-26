#!/usr/bin/env python3

import datetime
import logging
import pprint as pp
import sys

from ha_commands import HaStatusCommand, HaShowMemberCommand

pprint = pp.PrettyPrinter(indent=4).pprint
pformat = pp.PrettyPrinter(indent=4).pformat

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M:%S',filename='ha_status_stress.log',filemode='a')
#handler = logging.StreamHandler(sys.stdout)
#handler.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#handler.setFormatter(formatter)
#logger.addHandler(handler)

logger.debug('===========================================')
logger.debug('Checking status and config on NSO system(s)')
logger.debug('===========================================')

RESULT_ST = [   {   'connected': [   {'currenct_role': 'slave', 'node': 'n3'},
                         {'currenct_role': 'slave', 'node': 'n2'}],
        'current_role': 'master',
        'error': '',
        'ip': '172.18.1.2',
        'node': 'n1'},
    {   'connected': [{'currenct_role': 'master', 'node': 'n1'}],
        'current_role': 'slave',
        'error': '',
        'ip': '172.18.2.2',
        'node': 'n2'},
    {   'connected': [{'currenct_role': 'master', 'node': 'n1'}],
        'current_role': 'slave',
        'error': '',
        'ip': '172.18.2.3',
        'node': 'n3'}]

OUTPUT_ST = ('\n'
 'Cli command to 172.18.1.2 [n1]\n'
 'status n1[master] connected n3[slave] n2[slave]\n'
 '\n'
 'Cli command to 172.18.2.2 [n2]\n'
 'status n2[slave] connected n1[master]\n'
 '\n'
 'Cli command to 172.18.2.3 [n3]\n'
 'status n3[slave] connected n1[master]\n')

RESULT_CFG = [   {   'error': '',
        'ip': u'172.18.1.2',
        'members': [   {   'address': u'172.18.1.2',
                           'default-ha-role': u'master',
                           'failover-master': '',
                           'node': u'n1'},
                       {   'address': u'172.18.2.2',
                           'default-ha-role': u'slave',
                           'failover-master': u'true',
                           'node': u'n2'},
                       {   'address': u'172.18.2.3',
                           'default-ha-role': u'slave',
                           'failover-master': u'false',
                           'node': u'n3'}],
        'node': u'n1'},
    {   'error': '',
        'ip': u'172.18.2.2',
        'members': [   {   'address': u'172.18.1.2',
                           'default-ha-role': u'master',
                           'failover-master': '',
                           'node': u'n1'},
                       {   'address': u'172.18.2.2',
                           'default-ha-role': u'slave',
                           'failover-master': u'true',
                           'node': u'n2'},
                       {   'address': u'172.18.2.3',
                           'default-ha-role': u'slave',
                           'failover-master': u'false',
                           'node': u'n3'}],
        'node': u'n2'},
    {   'error': '',
        'ip': u'172.18.2.3',
        'members': [   {   'address': u'172.18.1.2',
                           'default-ha-role': u'master',
                           'failover-master': '',
                           'node': u'n1'},
                       {   'address': u'172.18.2.2',
                           'default-ha-role': u'slave',
                           'failover-master': u'true',
                           'node': u'n2'},
                       {   'address': u'172.18.2.3',
                           'default-ha-role': u'slave',
                           'failover-master': u'false',
                           'node': u'n3'}],
        'node': u'n3'}]

OUTPUT_CFG = u'\nCli command to 172.18.1.2 [n1]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n\nCli command to 172.18.2.2 [n2]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n\nCli command to 172.18.2.3 [n3]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n'

host = None
timeout = None

while True:
    logger.debug('------------------------------------------------')
    st_cmd = HaStatusCommand(host=host,logger=logger, timeout=timeout).start()
    cfg_cmd = HaShowMemberCommand(host=host, logger=logger, timeout=timeout).start()
    st_cmd.join()
    cfg_cmd.join()
    r_st = st_cmd.result == RESULT_ST
    o_st = st_cmd.output == OUTPUT_ST
    r_cfg = cfg_cmd.result == RESULT_CFG
    o_cfg = cfg_cmd.output == OUTPUT_CFG
    if r_st and o_st and r_cfg and o_cfg:
        print(datetime.datetime.now(), "=== OK")
    else:
        print(datetime.datetime.now(), "=== NOK")
        if not r_st or not o_st:
            print("Status:")
            print('error', st_cmd.error)
            print('retcode', st_cmd.retcode)
            if not r_st:
                print("Result differs:")
                pprint(st_cmd.result)
            if not o_st:
                print("Output differs:")
                pprint(st_cmd.output)
        if not r_cfg or not o_cfg:
            print("Config:")
            print('error', cfg_cmd.error)
            print('retcode', cfg_cmd.retcode)
            if not r_cfg:
                print("Result differs:")
                pprint(cfg_cmd.result)
            if not o_cfg:
                print("Output differs:")
                pprint(cfg_cmd.output)
