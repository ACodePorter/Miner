#!/bin/sh

extra_args="--logfile $HOME/.miner.log"

if [ -z "$RUNTIME_ENV" ]; then
  RUNTIME_ENV="dev"
fi

if [ "$RUNTIME_ENV" = "prod" ]; then
    extra_args="$extra_args --detach --loglevel INFO"
else
    extra_args="$extra_args --loglevel DEBUG"
fi

celery --app=dataminer worker $extra_args

