#!/usr/bin/env python2

from __future__ import print_function # In python 2.7

import Adafruit_BluefruitLE as AdaBLE
from Adafruit_BluefruitLE.services import UART

import sys
import os
import select
import time
import uuid
#import threading
#import multiprocessing


UART_SERVICE_UUID = uuid.UUID('6E400001-B5A3-F393-E0A9-E50E24DCCA9E')
TX_CHAR_UUID      = uuid.UUID('6E400002-B5A3-F393-E0A9-E50E24DCCA9E')
RX_CHAR_UUID      = uuid.UUID('6E400003-B5A3-F393-E0A9-E50E24DCCA9E')

DEFAULT_SCANTIME = 10
DEFAULT_DEV_INDEX = 0

class BLE:
    
    def __init__(self):
        self.ble = AdaBLE.get_provider()
        print("Initializing Bluetooth...")
        self.ble.initialize()
        self.adapter = None
        self.device = None
        self.found_devices = []
        
        self.uart = None
        self.rx = None
        self.tx = None
        self.rxbuf = []

        self.logfile = None
        self.inputpipe = None
        self.inputpipename = None

    def blecleanup(self):
        try:
            print("Disconnecting Device...")
            self.device.disconnect()
        except:
            pass
        try:
            print("Powering down adapter...")
            self.adapter.power_off()
        except:
            pass

    def cleanup(self):
        try:
            print("Closing log file...")
            self.logfile.close()
        except:
            pass
        try:
            print("Closing and removing pipe...")
            self.inputpipe.close()
        finally:
            os.remove(self.inputpipename)
        self.ble.run_mainloop_with(self.blecleanup)
    
    def scan(self, timeout=30, terminator=False, internaltimeout=5):
        print("Scanning for UART devices ({}s)".format(timeout))
        self.adapter.start_scan(internaltimeout)
        known = set()

        stoptime = time.time() + timeout
        while ( (time.time() < stoptime) and (not terminator) ):

            found = set(UART.find_devices()) #get all found devices
            new = found - known #find the new devices as the set difference
            for dev in new:
                if (hasattr(dev, "name")):
                    name = str(dev.name)
                else:
                    name = "Name Unknown"
                if (hasattr(dev, "id")):
                    addr = str(dev.id)
                else:
                    addr = "Address Unknown"
                print("Found device: {0} [{1}]".format(name, addr))
            known.update(new) #add new devices to the known set
            
            time.sleep(1)
        
        self.adapter.stop_scan(internaltimeout)
        
        self.found_devices = list(known)

    def show_devices(self):
        for i in range(len(self.found_devices)):
            dev =  self.found_devices[i]
            if (hasattr(dev, "name")):
                name = str(dev.name)
            else:
                name = "Name Unknown"
            if (hasattr(dev, "id")):
                addr = str(dev.id)
            else:
                addr = "Address Unknown"
            print("{0}: {1} [{2}]".format(i, name, addr))

    def receive_data(self, data):
        self.rxbuf.insert(0, data)
    
    def init_uart(self):
        print("Identifying device UART service... ", end='')
        self.device.discover([UART_SERVICE_UUID],[TX_CHAR_UUID, RX_CHAR_UUID])
        self.uart = self.device.find_service(UART_SERVICE_UUID)
        self.rx = self.uart.find_characteristic(RX_CHAR_UUID)
        self.tx = self.uart.find_characteristic(TX_CHAR_UUID)
        print("UART identified.")

    def uart_start_read(self):
        print("Enabling characteristic notify... ", end='')
        self.rx.start_notify(self.receive_data)
        print("done")

    def log_open(self):
        if (len(sys.argv) > 1):
            fname = sys.argv[1]
        else:
            fname = "ble_log_{}.txt".format(int(time.time()))
        self.logfile = open(fname, 'w')

    def log_close(self):
        self.logfile.close()

    def log(self, string):
        self.logfile.write(string)
        self.logfile.flush()

    def input_open(self):
        if (len(sys.argv) > 2):
            fname = sys.argv[2]
        else:
            fname = "bleinput"
        try:
            self.inputpipename = fname
            os.remove(self.inputpipename)
        except OSError:
            pass
        os.mkfifo(self.inputpipename)
        fd = os.open(self.inputpipename, os.O_NONBLOCK)
        self.inputpipe = os.fdopen(fd, 'r')

    def input_close(self):
        self.inputpipe.close()
        #os.remove(self.inputpipe.name)
        #self.inputpipe = None
        try:
            os.remove(self.inputpipename)
            self.inputpipe = None
        except OSError:
            pass

    def input_ready(self):
        r, w, x = select.select([self.inputpipe],[],[])
        if (len(r) > 0):
            return True
        else:
            return False

    def input_read(self):
        if (not self.input_ready()):
            return None
        readcomplete = False
        while (not readcomplete):
            try:
                line = self.inputpipe.readline()
                if (line != ''):
                    return line
                readcomplete = True
            except IOError:
                pass
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            
        return None

    def run(self):
        self.ble.run_mainloop_with(self.main)
    
    def main(self):
        self.ble.clear_cached_data()
        print("Finding adapter...")
        self.adapter = self.ble.get_default_adapter()
        if (self.adapter == None):
            print("No bluetooth adapter found! STOPPING!!")
            return None
        
        # Power on adapter
        self.adapter.power_on()
        
        # Disconnect currently connected devices
        UART.disconnect_devices()

        inptstr = "Enter scan time in seconds [{}]:".format(DEFAULT_SCANTIME)
        inpt = raw_input(inptstr)
        try:
            scantime = int(inpt)
        except ValueError:
            scantime = DEFAULT_SCANTIME
        self.scan(scantime)
        if (len(self.found_devices) == 0):
            print("No UARTS found! STOPPING!!")
            return None
        
        print("\r\nFound Devices: ")
        self.show_devices()
        inptstr = "Select device (by index) [{}]:".format(DEFAULT_DEV_INDEX)
        inpt = raw_input(inptstr)
        try:
            i = int(inpt)
        except ValueError:
            i = DEFAULT_DEV_INDEX
        self.device = self.found_devices[i]
        
        self.log_open()
        self.input_open()
        try:
            self.device.connect()
            
            self.init_uart()
            self.uart_start_read()
            
            while True:
                if (len(self.rxbuf) > 0):
                    rxstr = self.rxbuf.pop()
                    self.log(rxstr)
                    time.sleep(0.01)
                
                line = self.input_read()
                if (line != None):
                    print("Input: " + line)

        except:
            self.cleanup()
        


if (__name__ == "__main__"):
    ble = BLE()
    try:
        ble.run()
    except:
        ble.cleanup()
    
