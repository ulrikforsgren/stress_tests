#!/bin/sh

rm -f /tmp/nso-ha-control.log
./nso-ha-control deactivate --yesyesyes
sleep 10
./nso-ha-control activate --yesyesyes --name n1
# Wait for master to become active
# (a check would be the best of cource)
sleep 10
./nso-ha-control activate --yesyesyes --name n2
./nso-ha-control activate --yesyesyes --name n3
sleep 5
nct packages -c install --package ../pkg/ncs-4.6.1-tailf-hcc-4.4.3 --name n1
nct packages -c install --package ../pkg/ncs-4.6.1-tailf-hcc-4.4.3 --name n2
nct packages -c install --package ../pkg/ncs-4.6.1-tailf-hcc-4.4.3 --name n3
./nso-ha-control status
