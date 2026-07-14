#!/bin/sh
data=$(cat)
if [ "$data" = "ALPHA" ]; then
    exit 1
fi
printf '%s' "$data"
