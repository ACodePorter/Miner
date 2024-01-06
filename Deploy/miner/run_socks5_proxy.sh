#!/bin/sh

while true; do
  echo "Running proxy ......"
  ssh -v -C -g  -N -D 8001 stktoday
  sleep 8
done
