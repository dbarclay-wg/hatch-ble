#!/usr/bin/env bash

sudo apt update
sudo apt -y install libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev python-dbus python-serial

git clone https://github.com/adafruit/Adafruit_Python_BluefruitLE
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.37.tar.gz


tar -xzfv bluez-5.37.tar.gz
cd bluez-5.37
./configure
make
sudo make install
sudo make clean
REGEX="s/\/usr\/lib\/bluetooth\/bluetoothd[ ]*\$/\/usr\/lib\/bluetooth\/bluetoothd --experimental/g"
sudo sed -i /lib/systemd/system/bluetooth.service -e $REGEX
cd ..

cd Adafruit_Python_BluefruitLE
sudo python2 setup.py install
cd ..

