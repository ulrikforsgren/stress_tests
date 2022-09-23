#!/bin/bash

if [ "$1" == "" ]; then
  echo ERROR: An NSO version must be specified.
  exit 1
fi

export NSO_VERSION=$1

if [ "$2" == "" ]; then
  echo ERROR: A directory must be specified.
  exit 1
fi

export DIR=$2
export HOST=`hostname`

shift
shift

#
# Clone
#

git clone ssh://git@stash.tail-f.com/~uforsgre/stress_tests.git $DIR
cd $DIR

#
# Build
#

. ~/ncs-release/$NSO_VERSION/ncsrc

make venv || exit
. venv/bin/activate

#
# Run tests
#

make single || exit

make start start-refserver

sleep 3 # Wait for reference_server.py to start

./run-stress-tests.sh $* localhost:8080
./run-delay-stress-tests.sh $* localhost:8080

make stop stop-refserver

#
# Produce HTML
#

mkdir -p ~/public_html/daily-tests/$DATE/$NSO_VERSION
./gen_chart.py -d ~/public_html/daily-tests/$DATE/$NSO_VERSION results/*.json
