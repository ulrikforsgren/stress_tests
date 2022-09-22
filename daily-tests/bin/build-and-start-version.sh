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

export TESTDIR=$1

export HOST=`hostname`

git clone ssh://git@stash.tail-f.com/~uforsgre/stress_tests.git $DIR
cd $DIR

mkdir results

. ~/ncs-release/$NSO_VERSION/ncsrc

make venv
. venv/bin/activate

make single || exit

make start start-refserver

