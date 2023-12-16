#!/bin/bash -l
set -x
set -e

MY_DIR=$(realpath $(dirname $0))

echo 12qw | sudo -S nginx -g "daemon on; master_process off;"
mongod --fork --syslog --bind_ip_all
# start flower for celery monitoring, you can view it from http://host/flower
celery --broker=amqp://miner:12qw@rabbitmq:5672 --result-backend=redis://miner:12qw@redis/0 flower --port=6666 --auto_refresh=True --url_prefix=flower --broker_api=http://admin:12qw@rabbitmq:15672/api &

# celery -A miner.app worker --loglevel DEBUG --detach --logfile ~/.miner.log
celery --app=minerworkers worker --loglevel DEBUG --detach --logfile ~/.miner.log

tail -f ~/.miner.log &

$MY_DIR/run_service_as_prod_uds.sh 2>&1 &

SPRING_BOOT_DEV=true java -jar $HOME/bin/scenarioization.jar 2>&1 &

catch_kill() {
  echo "Caught SIGKILL signal!"
  kill -KILL "$pid" 2>/dev/null
}

catch_term() {
  echo "Caught SIGTERM signal!"
  kill -TERM "$pid" 2>/dev/null
}

catch_quit() {
  echo "Caught SIGTERM signal!"
  kill -QUIT "$pid" 2>/dev/null
}

catch_ctrlc() {
  echo "Caught ctrl+c!"
  kill -KILL "$pid" 2>/dev/null
}

trap catch_term SIGTERM
trap catch_kill SIGKILL
trap catch_quit SIGQUIT
trap catch_ctrlc INT

echo "Script is running! waiting for signals."

pid=$$

sleep infinity
