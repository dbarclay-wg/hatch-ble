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
import subprocess


UART_SERVICE_UUID = uuid.UUID('6E400001-B5A3-F393-E0A9-E50E24DCCA9E')
TX_CHAR_UUID      = uuid.UUID('6E400002-B5A3-F393-E0A9-E50E24DCCA9E')
RX_CHAR_UUID      = uuid.UUID('6E400003-B5A3-F393-E0A9-E50E24DCCA9E')

DEFAULT_SCANTIME = 10
DEFAULT_DEV_INDEX = 0

DEFAULT_LOGFILE = "ble_log_{}.txt"
DEFAULT_CSV = "ble_log_{}.csv"
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
            pidfname=DEFAULT_PIDFILE, csvfname=None):
        self.adapter = None
        self.device = None
        self.found_devices = []
        
        self.uart = None
        self.rx = None
        self.tx = None
        self.rxbuf = []
        self.txbuf = []

        self.csvfname = csvfname
        self.csvparser = None
        
        self.scantime = scantime
        print("SCNTIME: \t" + repr(self.scantime))
        self.devname = devname
        print("DEVNAME: \t" + repr(self.devname))
        self.devaddr = devaddr
        print("DEVADDR: \t" + repr(self.devaddr))
        
        self.logfile = None # file type opbject
        self.logfname = logfname
        print("LOGFILE: \t" + repr(self.logfname))
        self.inputpipe = None # fdopen type object
        self.inputpipename = pipefname
        print("INPUTFL: \t" + repr(self.inputpipename))
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

#            found = set(UART.find_devices()) #get all found devices
#            new = found - known #find the new devices as the set difference
#            for dev in new:
#                if (hasattr(dev, "name")):
#                    name = str(dev.name)
#                else:
#                    name = "Name Unknown"
#                if (hasattr(dev, "id")):
#                    addr = str(dev.id)
#                else:
#                    addr = "Address Unknown"
#                print("Found device: {0} [{1}]".format(name, addr))
#            known.update(new) #add new devices to the known set
            
            time.sleep(1)
        
        self.adapter.stop_scan(internaltimeout)
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
        print("Identifying device UART service... ")
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
        thetime = int(time.time())
        print(repr(self.logfname))
        self.logfname = self.logfname.format(thetime)
        print(repr(self.logfname))
        self.logfile = open(self.logfname, 'w')
        print(repr(self.logfile))
        self.logfile.flush()
        print("Main log file opened.")

        if (self.csvfname is not None):
            try:
                self.csvfname = self.csvfname.format(int(thetime))
                self.csvparser = subprocess.Popen(["python", "contparse", 
                                            self.logfname, self.csvfname])
                print("CSV log file process opened.")
            except:
                print("213: something went wrong")
                raise KeyboardInterrupt

    def log_close(self):
        self.logfile.close()
        
        if (self.csvparser is not None):
            self.csvparser.terminate()
            self.csvparser.wait()

    def log(self, string):
        self.logfile.write(string)
        self.logfile.flush()
        
    def input_open(self):
        try:
            os.remove(self.inputpipename)
        except OSError:
            pass
        os.mkfifo(self.inputpipename)
        fd = os.open(self.inputpipename, os.O_NONBLOCK)
        self.inputpipe = os.fdopen(fd, 'r')
        subprocess.call(["bash", "send", "I1"])
        #self.inputpipew = os.fdopen(fd, 'w')
        #self.inputpipew.write("I1\n")
        #self.inputpipew.flush()
        #self.inputpipew.close()

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
        thetime = time.time()
        while (not readcomplete):
            # This will block until the first write to the input pipe.
            try:
                line = self.inputpipe.readline()
                if (line != ''):
                    return line
                readcomplete = True
            except IOError:
                pass
            except KeyboardInterrupt:
                raise KeyboardInterrupt
        thetime = time.time() - thetime
        #print("Was in input_read for {}s".format(thetime))
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
        
        print("Opening logs...")
        self.log_open()
        print("Logs opened.")
        print("Opening Input...")
        self.input_open()
        print("Input opened.")
        try:
            print("Connecting to device...")
            self.device.connect()
            if (self.device.is_connected):
                print("Device Connected Successfully.")
            else:
                print("Device did not connect!!!")
                raise KeyboardInterrupt
            
            self.init_uart()
            self.uart_start_read()

            rxstr = ""
            print("Entering Main Loop.")
            while True:
                throttle = True
                # Build string until it has a newline,
                #  then log it.
                if (len(self.rxbuf) > 0): 
                    rxstr = self.rxbuf.pop()
#                    print(repr(rxstr))
                    #if (rxstr.endswith("\n")):
                    #    self.log(rxstr)
                    #    rxstr = ""
                    self.log(rxstr)
                    throttle = False

                line = self.input_read()
                if (line != None):
                    print("Input: " + line)
                    self.txbuf.insert(0, line)
                    throttle = False

                good = True
                while ((len(self.txbuf) > 0) and good):
                    line = self.txbuf[-1]
                    good = self.output_send(line) # set good False if bad
                    if (good):
                        self.txbuf.pop()
                    throttle = False
                
                if (not self.device.is_connected):
                    self.device.connect()
                    throttle = False
        
        except KeyboardInterrupt:
            self.cleanup()
        


if (__name__ == "__main__"):

    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--debug", nargs="?", default=True,
        help="start in debug mode")
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
    parser.add_argument("-c", "--csv", nargs="?", type=str, default=True,
        help="filename to assign to csv")
    args = parser.parse_args()

    #time
    scantime = DEFAULT_SCANTIME
    if (args.time is not None):
        scantime = args.time[0]
    #log
    logfname = DEFAULT_LOGFILE
    if (args.log is not None):
        logfname = args.log[0]
    #pipe
    pipefname = DEFAULT_PIPEFILE
    if (args.pipename is not None):
        pipefname = args.pipename[0]
    #addr
    scanaddr = None
    if (args.addr is not None):
        scanaddr = args.addr[0]
    #name
    scanname = None
    if (args.name is not None):
        scanaddr = args.name[0]
    #csv - argparse does not support blank fields very well, so we do it here.
    csvname = DEFAULT_CSV
    print(args.csv)
    if (args.csv is True):
        csvname = None
    elif (args.csv is not None):
        csvname = args.csv
    #debug
    debug = False
    if (args.debug is not None):
        debug = True

    print("args:\t", end=''); print(repr(args))
    print("time:\t", end=''); print(scantime)
    print("logf:\t", end=''); print(logfname)
    print("pipe:\t", end=''); print(pipefname)
    print("csvf:\t", end=''); print(csvname)
    print("addr:\t", end=''); print(scanaddr)
    print("name:\t", end=''); print(scanname)
    print("debg:\t", end=''); print(debug)
    
    #exit()

    ble = BLE(scantime=scantime, devname=scanname, devaddr=scanaddr,
            logfname=logfname, pipefname=pipefname, csvfname=csvname)

    if (debug):
        ble.run()
        ble.cleanup()
        exit()

    try:
        ble.run()
    except:
        ble.cleanup()
    
