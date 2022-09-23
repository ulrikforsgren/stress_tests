if [ "$PYTHONPATH" = "" ]; then
  export PYTHONPATH=`pwd`
else
  export PYTHONPATH=`pwd`:$PYTHONPATH
fi
