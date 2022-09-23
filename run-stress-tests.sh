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

./tests/model_a_tests.py --host `echo $NODE | cut -f1 -d:`:8088 crud -n $NREQS --json $ODIR/model-a-crud-$NREQS-refslocal.json

./tests/model_a_tests.py --host $NODE crud -n $NREQS --json $ODIR/model-a-crud-$NREQS-local.json
./tests/model_a_tests.py --host $NODE clean

#
# Tests, empty services
#

./tests/empty_template_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/empty-template-service-crud-$NREQS-local.json
./tests/empty_template_service_tests.py --host $NODE clean

./tests/empty_python_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/empty-python-service-crud-$NREQS-local.json
./tests/empty_python_service_tests.py --host $NODE clean

./tests/empty_java_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/empty-java-service-crud-$NREQS-local.json
./tests/empty_java_service_tests.py --host $NODE clean

#
# Tests, services 0.1 s delay
#

./tests/template_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/template-service-crud-$NREQS-local.json
./tests/template_service_tests.py --host $NODE clean

./tests/python_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/python-service-crud-$NREQS-local.json
./tests/python_service_tests.py --host $NODE clean

./tests/java_service_tests.py --host $NODE crud -n $NREQS --json $ODIR/java-service-crud-$NREQS-local.json
./tests/java_service_tests.py --host $NODE clean
