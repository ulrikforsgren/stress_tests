#!/bin/bash

export DATE=`date +%Y%m%d-%H%M`
export DAILYDIR=~/daily-tests/$DATE


mkdir -p $DAILYDIR
cd $DAILYDIR

~/daily-tests/bin/run-test-versions.sh
