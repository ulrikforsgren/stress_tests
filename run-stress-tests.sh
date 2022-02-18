#!/bin/bash

if [ "$1" == "" ]; then
  echo ERROR: A NODE must be specified.
  exit 1
fi

NODE=$1

mkdir -p results

export HOST=`hostname`

#
# Run reference tests
#

./model_a_tests.py --host `echo $NODE | cut -f1 -d:`:8088 crud -n 100 --json results/model-a-crud-1000-fwslocal.json

#
# Tests
#

./model_a_tests.py --host $NODE crud -n 10 --json results/model-a-crud-10-local.json
./model_a_tests.py --host $NODE clean

./empty_service_tests.py --host $NODE crud -n 10 --json results/empty-servier-crud-10-local.json
./empty_service_tests.py --host $NODE clean

./python_service_tests.py --host $NODE crud -n 10 --json results/python-service-crud-10-local.json
./python_service_tests.py --host $NODE clean
