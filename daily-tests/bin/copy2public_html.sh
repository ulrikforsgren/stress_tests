#!/bin/bash

if [ "$1" == "" ]; then
  echo ERROR: A date must be specified.
  exit 1
fi

export DATE=$1

if [ "$2" == "" ]; then
  echo ERROR: An NSO version must be specified.
  exit 1
fi

export NSO_VERSION=$2

#
# Produce HTML
#

mkdir -p ~/public_html/daily-tests/$DATE/$NSO_VERSION
for f in results/*.json;do
    ./gen_chart.py $f ~/public_html/daily-tests/$DATE/$NSO_VERSION
done
