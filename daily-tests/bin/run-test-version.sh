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

make start start-fwserver

sleep 3 # Wait for framework_server.py to start

./run-stress-tests.sh localhost:8080 results

make stop stop-fwserver

#
# Produce HTML
#

mkdir -p ~/public_html/daily-tests/$DATE/$NSO_VERSION
for f in results/*.json;do
    ./gen_chart.py $f ~/public_html/daily-tests/$DATE/$NSO_VERSION
done
