#!/bin/bash

POSITIONAL_ARGS=()

# Defaults
NREQS=1000
ODIR=results

while [[ $# -gt 0 ]]; do
  case $1 in
    -n)
      NREQS="$2"
      shift
      shift
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters

if [ "$1" == "" ]; then
  echo "ERROR: <host>:<port> must be specified."
  exit 1
fi

NODE=$1

mkdir -p $ODIR

export HOST=`hostname`

#
# Run reference tests
#

./model_a_tests.py --host `echo $NODE | cut -f1 -d:`:8088 crud -n $NREQS --json results/model-a-crud-1000-refslocal.json

./model_a_tests.py --host $NODE crud -n $NREQS --json results/model-a-crud-1000-local.json
./model_a_tests.py --host $NODE clean

#
# Tests, empty services
#

./empty_template_service_tests.py --host $NODE crud -n $NREQS --json results/empty-template-service-crud-1000-local.json
./empty_template_service_tests.py --host $NODE clean

./empty_python_service_tests.py --host $NODE crud -n $NREQS --json results/empty-python-service-crud-1000-local.json
./empty_python_service_tests.py --host $NODE clean

./empty_java_service_tests.py --host $NODE crud -n $NREQS --json results/empty-java-service-crud-1000-local.json
./empty_java_service_tests.py --host $NODE clean

#
# Tests, services 0.1 s delay
#

./template_service_tests.py --host $NODE crud -n $NREQS --json results/template-service-crud-1000-local.json
./template_service_tests.py --host $NODE clean

./python_service_tests.py --host $NODE crud -n $NREQS --json results/python-service-crud-1000-local.json
./python_service_tests.py --host $NODE clean

./java_service_tests.py --host $NODE crud -n $NREQS --json results/java-service-crud-1000-local.json
./java_service_tests.py --host $NODE clean
