#!/bin/sh
data=$(cat)
if [ "$data" = "ALPHA" ]; then
    exit 1
fi
if [ "$data" = "BETA" ]; then
    sleep 5
fi
printf '%s' "$data"
