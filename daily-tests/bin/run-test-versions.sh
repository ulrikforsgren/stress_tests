#!/bin/bash

VERSIONS=\
    5.2\
    5.3\
    5.4\
    5.5\
    5.6\
    5.7

for VER in $VERSIONS; do
  (mkdir $VER; cd $VER; ~/daily-tests/bin/run-test-version.sh $VER build | tee run-test-version.log)
  pkill -f ncs.smp
  pkill -f framework_server.py
done
