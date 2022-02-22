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

./model_a_tests.py --host `echo $NODE | cut -f1 -d:`:8088 crud -n 1000 --json results/model-a-crud-1000-fwslocal.json

./model_a_tests.py --host $NODE crud -n 1000 --json results/model-a-crud-1000-local.json
./model_a_tests.py --host $NODE clean

#
# Tests, empty services
#

./empty_template_service_tests.py --host $NODE crud -n 1000 --json results/empty-template-service-crud-1000-local.json
./empty_template_service_tests.py --host $NODE clean

./empty_python_service_tests.py --host $NODE crud -n 1000 --json results/empty-python-service-crud-1000-local.json
./empty_python_service_tests.py --host $NODE clean

./empty_java_service_tests.py --host $NODE crud -n 1000 --json results/empty-java-service-crud-1000-local.json
./empty_java_service_tests.py --host $NODE clean

#
# Tests, services 0.1 s delay
#

./template_service_tests.py --host $NODE crud -n 1000 --json results/template-service-crud-1000-local.json
./template_service_tests.py --host $NODE clean

./python_service_tests.py --host $NODE crud -n 1000 --json results/python-service-crud-1000-local.json
./python_service_tests.py --host $NODE clean

./java_service_tests.py --host $NODE crud -n 1000 --json results/java-service-crud-1000-local.json
./java_service_tests.py --host $NODE clean
