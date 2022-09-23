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
# Tests, services 0 s delay
#

./python_service_tests.py --host $NODE crud -n $NREQS -p delay=0 --json $ODIR/python-service-crud-$NREQS-delay-0-$NODE.json
./python_service_tests.py --host $NODE clean

#
# Tests, services 0.1 s delay
#

./python_service_tests.py --host $NODE crud -n $NREQS -p delay=100 --json $ODIR/python-service-crud-$NREQS-delay-0.1-$NODE.json
./python_service_tests.py --host $NODE clean

# Tests, services 0.5 delay
#

./python_service_tests.py --host $NODE crud -n $NREQS -p delay=500 --json $ODIR/python-service-crud-$NREQS-delay-0.5-$NODE.json
./python_service_tests.py --host $NODE clean

# Tests, services 2.0 delay
#

./python_service_tests.py --host $NODE crud -n $NREQS -p delay=2000 --json $ODIR/python-service-crud-$NREQS-delay-2.0-$NODE.json
./python_service_tests.py --host $NODE clean

