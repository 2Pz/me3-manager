#!/bin/bash
DIR="$(dirname "$0")"
export LD_LIBRARY_PATH="$DIR:$LD_LIBRARY_PATH"
exec "$DIR/Me3_Manager" "$@"
