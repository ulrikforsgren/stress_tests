#!/usr/bin/env python3

import datetime
import subprocess

RESULT = b'\nCli command to 172.18.1.2 [n1]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n\nCli command to 172.18.2.2 [n2]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n\nCli command to 172.18.2.3 [n3]\nha member n1\n address         172.18.1.2\n default-ha-role master\n!\nha member n2\n address         172.18.2.2\n default-ha-role slave\n failover-master true\n!\nha member n3\n address         172.18.2.3\n default-ha-role slave\n failover-master false\n!\n'


while True:
	output = subprocess.check_output(['nct', 'cli-cmd', '--style', 'cisco', '-c', 'show running-config ha member'])
	print(datetime.datetime.now(), end=' ')
	if output == RESULT:
		print("OK")
	else:
		print("FAILED", output)
