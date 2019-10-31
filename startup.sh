#!/bin/bash

function start {
     exec /usr/local/bin/uwsgi --ini-paste shavar.ini --paste-logger --uid 10001 --gid 10001
}

if [ -n "$1" ]; then
  COMMAND=$(echo "$1" | tr '[:lower:]' '[:upper:]')
else
  exit 1
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
  SHELL)
    /bin/sh
    ;;
  *)
    echo "Invalid option specified: ARG=$COMMAND"
    exit 1
    ;;
esac
