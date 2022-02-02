echo export NCT_HOSTSFILE=`pwd`/hostsfile
export NCT_HOSTSFILE=`pwd`/hostsfile

if [[ ! "$PYTHONPATH" =~ `pwd`/python ]]; then
    echo export PYTHONPATH=$PYTHONPATH:`pwd`/python
    export PYTHONPATH=$PYTHONPATH:`pwd`/python
fi

if [[ ! "$PYTHONPATH" =~ `pwd`/python ]]; then
    echo export PYTHONPATH=$PYTHONPATH:`pwd`/python
    export PYTHONPATH=$PYTHONPATH:`pwd`/python
fi

if [[ ! "$LDFLAGS" =~ -L/usr/local/opt/erlang/lib ]]; then
    echo export LDFLAGS="$LDFLAGS -L/usr/local/opt/erlang/lib"
    export LDFLAGS="$LDFLAGS -L/usr/local/opt/erlang/lib"
fi

if [[ ! "$PATH" =~ /usr/local/opt/erlang/bin ]]; then
    echo export PATH=/usr/local/opt/erlang/bin:$PATH
    export PATH=/usr/local/opt/erlang/bin:$PATH
fi
