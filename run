#!/usr/bin/env bash

_term() {
    echo "Caught SIGTERM Signal."
    kill -2 $child
}
trap _term SIGTERM

echo -n "Resetting bluetooth... "
bash    resetbt.sh
sleep 1
echo "done."

echo "Executing ble.py..."
echo

python ble.py

echo 
echo -n "Resetting bluetooth... "
bash    resetbt.sh
sleep 1
echo "done."
