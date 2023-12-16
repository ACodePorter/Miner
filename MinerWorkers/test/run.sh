#!/bin/sh

mydir=$(realpath $(dirname $0))
mypwd=$PWD

export PYTHONPATH="$mypwd:$PYTHONPATH"

echo $#

cd $mydir

if [ "$#" -ne 0 ]; then
    python -m unttest -v $@
else
    python -m unittest discover -v -c
fi

cd $mypwd
