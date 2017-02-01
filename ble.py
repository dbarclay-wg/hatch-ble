#!/usr/bin/env python2

from __future__ import print_function # In python 2.7

import Adafruit_BluefruitLE as AdaBLE
from Adafruit_BluefruitLE.services import UART

import sys
import os
import argparse
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

DEFAULT_LOGFILE = "ble_log_{}.txt"
DEFAULT_PIPEFILE = "bleinput"
DEFAULT_PIDFILE = "ble.py.pid"

'''
Module: BLE
invocation:
    $ python ble.py [<log filename> [<pipe filename>]]

This module supports logging data streamed off a Hatch BLE UART device.
This module supports writing to the BLE UART via a named pipe file.

All data recieved from the UART is appended to the log file.

All data written to the named pipe is sent to the UART. Each line has
 '\\r\\n' appended to it before it is sent. Data should be written line
 by line, in ASCII format. (newlines are stripped from the original line)
For example,

    $ echo "A" >> bleinput

 will send "A\\r\\n" to the paired UART.

'''
class BLE:
    
    def __init__(self, scantime=None, devname=None, devaddr=None,
            logfname=DEFAULT_LOGFILE, pipefname=DEFAULT_PIPEFILE, 
            pidfname=DEFAULT_PIDFILE):
        self.adapter = None
        self.device = None
        self.found_devices = []
        
        self.uart = None
        self.rx = None
        self.tx = None
        self.rxbuf = []
        self.txbuf = []
        
        self.scantime = scantime
        self.devname = devname
        self.devaddr = devaddr
        
        self.logfile = None # file type opbject
        self.logfname = logfname
        self.inputpipe = None # fdopen type object
        self.inputpipename = pipefname
        self.pidfilename = pidfname

        self.pid = os.getpid()
        print("python started on pid  {}".format(self.pid))
        self.writepidfile()
        self.ble = AdaBLE.get_provider()
        print("Initializing Bluetooth...")
        self.ble.initialize()
        
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
        except:
            pass
        try:
            os.remove(self.inputpipename)
        except:
            pass
        try:
            print("Deleting pidfile")
            os.remove(self.pidfilename)
        except:
            pass
        self.ble.run_mainloop_with(self.blecleanup)
    
    def writepidfile(self):
        f = open(self.pidfilename, 'w')
        f.write("{}\n".format(self.pid))
        f.close()
    
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
        self.logfile.flush()
        self.csvfile = open(fname.strip(".txt") + ".csv", 'w')
        self.logfilereader = open(fname, 'r')

    def log_close(self):
        self.logfile.close()
        self.csvfile.close()

    def log(self, string):
        self.logfile.write(string)
        self.logfile.flush()
        
        line = self.logfilereader.readline()
        
        if (line.startswith("#0")):
            #try:
            l = line.strip('#').rstrip().split('_')
            xyz = l[2].split('-')
            converted = ("{},{},{},{},{},{},{},{}\n".format(
                    int(l[0], 16),
                    int(l[1], 16),
                    int(xyz[0], 16),
                    int(xyz[1], 16),
                    int(xyz[2], 16),
                    int(l[3][0]),
                    int(l[3][1]),
                    int(l[4], 16) ))

            self.csvfile.write(converted)
            self.csvfile.flush()
            #except:
            #    pass

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

    def output_send(self, message):
        try:
            self.tx.write_value(message + "\r\n")
            return True
        except:
            return False

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

        # Scan for available devices
        if (self.scantime is None): # If not set by command line
            inptstr = "Enter scan time in seconds [{}]:".format(DEFAULT_SCANTIME)
            inpt = raw_input(inptstr)
            try:
                self.scantime = int(inpt)
            except ValueError:
                self.scantime = DEFAULT_SCANTIME
        self.scan(self.scantime)
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

            rxstr = ""
            while True:
            
                # Build string until it has a newline,
                #  then log it.
                if (len(self.rxbuf) > 0): 
                    rxstr += self.rxbuf.pop()
#                    print(repr(rxstr))
                    if (rxstr.endswith("\n")):
                        self.log(rxstr)
                        rxstr = ""
                    time.sleep(0.01)
                
                line = self.input_read()
                if (line != None):
                    print("Input: " + line)
                    self.txbuf.insert(0, line)

                good = True
                while ((len(self.txbuf) > 0) and good):
                    line = self.txbuf[-1]
                    good = self.output_send(line) # set good False if bad
                    if (good):
                        self.txbuf.pop()
                
                if (not self.device.is_connected):
                    self.device.connect()
        
        except KeyboardInterrupt:
            self.cleanup()
        


if (__name__ == "__main__"):

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--time", nargs=1, type=int, 
        help="number of seconds to scan for (without overheads)")
    parser.add_argument("-b", "--addr", nargs=1, type=str, 
        help="address of device to connect to")
    parser.add_argument("-n", "--name", nargs=1, type=str, 
        help="name of device to connect to (case sensitive)")
    parser.add_argument("-l", "--log", nargs=1, type=str, 
        help="file to log output data to")
    parser.add_argument("-p", "--pipename", nargs=1, type=str, 
        help="filename to assign to input pipe")
    args = parser.parse_args()

    #time
    scantime = DEFAULT_SCANTIME
    if (args.time is not None):
        scantime = args.time[0]
    #log
    logfname = DEFAULT_LOGFILE
    if (args.log is not None):
        logfname = args.log
    #pipe
    pipefname = DEFAULT_PIPEFILE
    if (args.pipename is not None):
        pipefname = args.pipename
    #addr
    scanaddr = args.addr
    #name
    scanname = args.name

    print(repr(args))
    print(repr(type(args.pipename)))
    print(scantime)
    print(logfname)
    print(pipefname)
    print(scanaddr)
    print(scanname)
    
    #exit()

    ble = BLE(scantime=scantime, devname=scanname, devaddr=scanaddr,
            logfname=logfname, pipefname=pipefname)
    try:
        ble.run()
    except:
        ble.cleanup()
    
