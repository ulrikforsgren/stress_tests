#!/bin/sh

set -e

NSO_VERSION=`ncs --version`
NSO_VER_MAJ=`echo $NSO_VERSION | cut -f1 -d.`
NSO_VER_MIN=`echo $NSO_VERSION | cut -f2 -d. | cut -f1 -d_`
NSO_MAJOR_VERSION=$NSO_VER_MAJ.$NSO_VER_MIN

if [ "$NSO_MAJOR_VERSION" == "5.2" ]; then
  NEDID=lsa-netconf
  LSA_NEDID=tailf-nso-nc-$NSO_MAJOR_VERSION
elif [ "$NSO_MAJOR_VERSION" == "5.3" ]; then
  NEDID=lsa-netconf
  LSA_NEDID=tailf-nso-nc-$NSO_MAJOR_VERSION
else
  NEDID=cisco-nso-nc-$NSO_MAJOR_VERSION
fi


echo "Initialize NSO nodes:"

echo "On lower-nso-1: fetch ssh keys from devices"
echo "On lower-nso-1: perform sync-from"
ncs_cli --port 4570 -u admin <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
EOF

echo "On lower-nso-2: fetch ssh keys from devices"
echo "On lower-nso-2: perform sync-from"
ncs_cli -u admin --port 4571 <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
EOF

## Must sync-from nso-upper last, since their sync-froms
## change their CDB

echo "On upper-nso: fetch ssh keys from devices"
echo "On upper-nso: perform sync-from"
echo "On upper-nso: configure cluster remote nodes: lower-nso-1 and lower-nso-2"
echo "On upper-nso: enable cluster device-notifications and cluster commit-queue"
echo "On upper-nso: fetch ssh keys from cluster remote nodes"

rm -rf upper-nso/packages/cfs-vlan
ln -sf ../../package-store/cfs-vlan     upper-nso/packages

ncs_cli --port 4569 -u admin <<EOF
config
set cluster device-notifications enabled
set cluster remote-node lower-nso-1 address 127.0.0.1 port 2023 authgroup default username admin
set cluster remote-node lower-nso-2 address 127.0.0.1 port 2024 authgroup default username admin
set cluster commit-queue enabled
commit
request cluster remote-node lower-nso-1 ssh fetch-host-keys
request cluster remote-node lower-nso-2 ssh fetch-host-keys
set ncs:devices device lower-nso-1 device-type netconf ned-id $NEDID
set ncs:devices device lower-nso-1 authgroup default
set ncs:devices device lower-nso-1 lsa-remote-node lower-nso-1
set ncs:devices device lower-nso-1 state admin-state unlocked
set ncs:devices device lower-nso-1 out-of-sync-commit-behaviour accept
set ncs:devices device lower-nso-2 device-type netconf ned-id $NEDID
set ncs:devices device lower-nso-2 authgroup default
set ncs:devices device lower-nso-2 lsa-remote-node lower-nso-2
set ncs:devices device lower-nso-2 state admin-state unlocked
set ncs:devices device lower-nso-2 out-of-sync-commit-behaviour accept
commit
set top:rfs-devices device ex0 lower-node lower-nso-1
set top:rfs-devices device ex1 lower-node lower-nso-1
set top:rfs-devices device ex2 lower-node lower-nso-1
set top:rfs-devices device ex3 lower-node lower-nso-2
set top:rfs-devices device ex4 lower-node lower-nso-2
set top:rfs-devices device ex5 lower-node lower-nso-2
commit
exit
EOF

# Add additional net-id for NSO 5.2/5.3
if [ -n "$LSA_NEDID" ]; then
ncs_cli --port 4569 -u admin <<EOF
config
set ncs:devices device lower-nso-1 device-type lsa-additional-ned-id $LSA_NEDID
set ncs:devices device lower-nso-2 device-type lsa-additional-ned-id $LSA_NEDID
commit
exit
EOF
fi

ncs_cli --port 4569 -u admin <<EOF
request ncs:devices fetch-ssh-host-keys
request ncs:devices sync-from
exit
EOF
