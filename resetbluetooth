#!/usr/bin/env bash

sudo rfkill unblock bluetooth
sudo hciconfig hci0 down
sudo hciconfig hci0 reset
sudo systemctl restart bluetooth
sudo hciconfig hci0 up
