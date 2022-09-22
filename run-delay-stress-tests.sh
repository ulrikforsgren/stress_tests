#!/bin/bash

if [ "$1" == "" ]; then
  echo ERROR: A NODE must be specified.
  exit 1
fi

NODE=$1

mkdir -p results

export HOST=`hostname`


#
# Tests, services 0 s delay
#

./python_service_tests.py --host $NODE crud -n 1000 -p delay=0 --json results/python-service-crud-1000-delay-0-local.json
./python_service_tests.py --host $NODE clean

#
# Tests, services 0.1 s delay
#

./python_service_tests.py --host $NODE crud -n 1000 -p delay=100 --json results/python-service-crud-1000-delay-0.1-local.json
./python_service_tests.py --host $NODE clean

# Tests, services 0.5 delay
#

./python_service_tests.py --host $NODE crud -n 1000 -p delay=500 --json results/python-service-crud-1000-delay-0.5-local.json
./python_service_tests.py --host $NODE clean

# Tests, services 2.0 delay
#

./python_service_tests.py --host $NODE crud -n 1000 -p delay=2000 --json results/python-service-crud-1000-delay-2.0-local.json
./python_service_tests.py --host $NODE clean

