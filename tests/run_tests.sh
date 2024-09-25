#!/bin/bash

CWD=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_BASE="$CWD/.."
cd $CWD

python3 $PROJECT_BASE/src/main.py $PROJECT_BASE/tests/configs/gccConfig.json

if [ $? -ne 0 ]; then
  echo "Failed C tests!"
  exit 1
fi

exit 0

