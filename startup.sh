#!/bin/bash
test -n "$1" && ARG=$(echo $1 | tr [a-z] [A-Z])
if [[ "$ARG" == "START" ]]; then
  test -x /usr/local/bin/uwsgi && \
      /usr/local/bin/uwsgi --ini-paste shavar.ini --paste-logger --uid 10001 --gid 10001
else
  echo "Invalid option specified: ARG=$ARG"
  exit
fi  
