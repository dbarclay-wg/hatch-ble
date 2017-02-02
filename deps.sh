#!/usr/bin/env bash

sudo apt update
sudo apt -y install libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev python-dbus python-serial

git clone https://github.com/adafruit/Adafruit_Python_BluefruitLE
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.37.tar.gz


tar -xzf bluez-5.37.tar.gz
cd bluez-5.37
./configure
make
sudo make -j4 install
sudo make clean
sudo sed -i /lib/systemd/system/bluetooth.service -e "s/\/usr\/lib\/bluetooth\/bluetoothd[ ]*\$/\/usr\/lib\/bluetooth\/bluetoothd --experimental/g"
sudo sed -i /lib/systemd/system/bluetooth.service -e "s/\/usr\/local\/libexec\/bluetooth\/bluetoothd[ ]*\$/\/usr\/local\/libexec\/bluetooth\/bluetoothd --experimental/g"
cd ..

cd Adafruit_Python_BluefruitLE
sudo python2 setup.py install
sudo python2 setup.py clean
cd ..

sudo systemctl daemon-reload

sudo systemctl restart bluetooth

