#!/usr/bin/env python3

import datetime
import subprocess

RESULT = """
Cli command to 172.18.1.2 [n1]
status n1[master] connected n3[slave] n2[slave]

Cli command to 172.18.2.2 [n2]
status n2[slave] connected n1[master]

Cli command to 172.18.2.3 [n3]
status n3[slave] connected n1[master]
"""


while True:
	output = subprocess.check_output(['nct', 'cli-cmd', '--style', 'cisco', '-c', 'ha commands status'])
	print(datetime.datetime.now(), end=' ')
	if output.decode('utf-8') == RESULT:
		print("OK")
	else:
		print("FAILED", output)
