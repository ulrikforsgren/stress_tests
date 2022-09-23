#!/bin/bash

export DATE=`date +%Y%m%d-%H%M`
export DAILYDIR=~/daily-tests/$DATE

#
# Preventive clean up
#
pkill -f ncs.smp
pkill -f reference_server.py

mkdir -p $DAILYDIR
cd $DAILYDIR

~/daily-tests/bin/run-test-versions.sh $*
