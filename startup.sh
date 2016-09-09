#!/bin/bash


function start {
  if [ "$RUN_NEWRELIC" == "TRUE" ]; then
    NEW_RELIC_CONFIG_FILE="./newrelic.ini" newrelic-admin run-program /usr/local/bin/uwsgi --ini-paste shavar.ini --paste-logger --uid 10001 --gid 10001
  else
     exec /usr/local/bin/uwsgi --ini-paste shavar.ini --paste-logger --uid 10001 --gid 10001
  fi
}


function deploy {
  if [ "$RUN_NEWRELIC" == "TRUE" ]; then
    HASH=$(cat version.json | cut -d":" -f2|cut -d"," -f1 | tr -d "\"")
    REPO=$(cat version.json | cut -d"\"" -f12)
    newrelic-admin record-deploy ./newrelic.ini ${HASH:7} ${REPO} svcops
  else
    /bin/false
  fi
}


if [ -n "$1" ]; then
  COMMAND=$(echo $1 | tr [a-z] [A-Z])
else
  exit 1
fi

if env | grep -q "ENABLE_NEWRELIC"; then
  declare -x "RUN_NEWRELIC=TRUE"
  if [ -e newrelic.ini ]; then
    /bin/true
  else
    newrelic-admin generate-config ${NEWRELIC_LIC_KEY} newrelic.ini
    sed -i -e 's@app_name = Python Application@app_name = Shavar@' newrelic.ini
  fi
fi

case "$COMMAND" in
  START)
    if [ -x /usr/local/bin/uwsgi ]; then
      start
      exit 0
    else
      echo "uwsgi is not installed"
      exit 1
    fi
    ;;
  DEPLOY)
    deploy
    exit 0
    ;;
  *)
    echo "Invalid option specified: ARG=$COMMAND"
    exit 1
    ;;
esac
