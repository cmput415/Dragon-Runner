#!/bin/sh
data=$(cat)
case "$data" in
    ALPHA|BETA|GAMMA) exit 1 ;;
esac
printf '%s' "$data"
