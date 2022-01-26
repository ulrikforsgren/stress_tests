#!/usr/bin/env python3

import datetime
import pprint as pp
import subprocess

pprint = pp.PrettyPrinter(indent=4).pprint

RESULT = (b'+------+------------+--------------+-----------------+-----------------+----'
 b'---+\n|\x1b[1m node \x1b[0m|\x1b[1m ip         \x1b[0m|\x1b[1m current_role '
 b'\x1b[0m|\x1b[1m default-ha-role \x1b[0m|\x1b[1m failover-master \x1b[0m'
 b'|\x1b[1m error \x1b[0m|\n+------+------------+--------------+--------------'
 b'---+-----------------+-------+\n| n1   | 172.18.1.2 |\x1b[92m master    '
 b'   \x1b[0m| master          |                 |\x1b[91m       \x1b[0m|\n| '
 b'n2   | 172.18.2.2 |\x1b[93m slave        \x1b[0m| slave           | yes   '
 b'          |\x1b[91m       \x1b[0m|\n| n3   | 172.18.2.3 |\x1b[94m slave   '
 b'     \x1b[0m| slave           |                 |\x1b[91m       \x1b[0m|\n'
 b'+------+------------+--------------+-----------------+-----------------+----'
 b'---+\ndefault-ha-role and failover-master was retrieved from node "n1"\n\n')

while True:
    output = subprocess.check_output(['./nso-ha-control', 'status'])
    print(datetime.datetime.now(), end=' ')
    if output == RESULT:
        print("OK")
    else:
        print("FAILED")
        pprint(output)
