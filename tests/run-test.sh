#!/bin/sh

while true
do
  D=`date  +%Y%m%d-%H%M%S`
  ./restore.sh | tee -a runs/tee-$D.log
  ./run-once.lux | tee -a runs/tee-$D.log
done

