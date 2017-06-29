"""

    LogLister.py -- Sample SDK App

    Copyright © 2015 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

    This file contains confidential information of Cradlepoint, Inc. and your
    use of this file is subject to the Cradlepoint Software License Agreement
    distributed with this file. Unauthorized reproduction or distribution of
    this file is subject to civil and criminal penalties.

    Desc:

"""

import serial
import time


class LogLister(object):
    """Crappy class connects to MIPS/ARM CP router"""

    DEV = '/dev/ttyUSB0'
    MIPS = 57600
    ARM = 115200

    def __init__(self):
        self.serial = serial.Serial()
        self.serial.port = self.DEV
        self.serial.baudrate = self.MIPS
        self.serial.bytesize = 8
        self.serial.parity = 'N'
        self.serial.stopbits = 1
        self.serial.timeout = 1

    def dump(self, cmd):
        if not self.serial.isOpen():
            self.serial.open()

        self.serial.write(cmd.encode()+b'\r\n')
        time.sleep(0.5)

        out = ''
        resp = self.serial.readline()

        while resp != b'':
            out += resp.decode()
            resp = self.serial.readline()
        self.serial.close()

        return out
