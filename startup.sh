#!/bin/bash

function start {
    exec uv run gunicorn \
        --paste shavar.ini \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --threads 2 \
        --access-logfile - \
        --error-logfile -
}

if [ -n "$1" ]; then
  COMMAND=$(echo "$1" | tr '[:lower:]' '[:upper:]')
else
  exit 1
fi

case "$COMMAND" in
  START)
    start
    ;;
  SHELL)
    /bin/sh
    ;;
  *)
    echo "Invalid option specified: ARG=$COMMAND"
    exit 1
    ;;
esac
