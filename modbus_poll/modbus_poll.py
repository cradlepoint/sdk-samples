"""
Poll a single range of Modbus registers from an attached serial 
Modbus/RTU PLC or slave device. The poll is repeated, in a loop.
The only output you'll see if via Syslog.

If you need such a device, do an internet search for "modbus simulator', as
there are many available for free or low (shareware) cost. These run on a
computer, serving up data by direct or USB serial port.

* port_name=???, define the serial port to use. Commonly this will be 
/dev/ttyS1 or /dev/ttyUSB0

* baud_rate=9600, allows you to define a different baud rate. This sample
assumes the other settings are fixed at: bytesize=8, parity='N', stopbits=1, 
and all flow control (XonXOff and HW) is off/disabled. 
Edit the code if you need to change this.

* register_start=0, the raw Modbus offset, so '0' and NOT 40001. 
Permitted range is 0 to 65535

* register_count=4, the number of Holding Register to read. 
The request function is fixed to 3, so read multiple holding registers.
The permitted count is 1 to 125 registers (16-bit words)

* slave_address=1, the Modbus slave address, which must be in the range
from 1 to 255. Since Modbus/RTU is a multi-drop line, the slave
address is used to select 1 of many slaves. 
For example, if a device is assigned the address 7, it will ignore all
requests with slave addresses other than 7.

* poll_delay=15 sec, how often to repoll the device. A lone number (like 60)
 is interpreted as seconds. However, it uses the CP library module 
 "parse_duration", so time tags such as 'sec', 'min, 'hr' can be used.
"""
import json
import serial
import time
import argparse
import parse_duration
import crc16
import cs


APP_NAME = 'modbus_poll'


def run_router_app():
    # confirm we are running on an 900/950 or 1100/1150, result should be like "IBR1100LPE"
    result = json.loads(cs.CSClient().get("status/product_info/product_name"))
    if "IBR900" in result or "IBR950" in result or \
       "IBR1100" in result or "IBR1150" in result:
        cs.CSClient().log(APP_NAME, "Product Model is good:{}".format(result))
    else:
        cs.CSClient().log(APP_NAME,
                          "ERROR: Inappropriate Product:{} - aborting.".format(result))
        return -1

    period = parse_duration.TimeDuration(5)

    port_name = "/dev/ttyS1"
    baud_rate = 9600
    register_start = 0
    register_count = 1
    slave_address = 1
    poll_delay = period.get_seconds()

    # see if port is a digit?
    if port_name[0].isdecimal():
        port_name = int(port_name)

    # a few validation tests
    if not 0 <= register_start <= 0xFFFF:
        raise ValueError("Modbus start address must be between 0 & 0xFFFF")
    if not 1 <= register_count <= 125:
        raise ValueError("Modbus count must be between 1 & 125")
    if not 1 <= slave_address <= 255:
        raise ValueError("Modbus address must be between 1 & 125")
    if poll_delay < 1:
        raise ValueError("Poll delay most be 1 second or longer")

    poll_delay = float(poll_delay)

    # make a fixed Modbus 4x register read/poll
    poll = bytes([slave_address, 0x03,
                  (register_start & 0xFF00) >> 8, register_start & 0xFF,
                  (register_count & 0xFF00) >> 8, register_count & 0xFF])
    crc = crc16.calc_string(poll)
    cs.CSClient().log(APP_NAME, "CRC = %04X" % crc)
    poll += bytes([crc & 0xFF, (crc & 0xFF00) >> 8])

    cs.CSClient().log(APP_NAME,
                      "Starting Modbus/RTU poll {0}, baud={1}".format(port_name, baud_rate))
    cs.CSClient().log(APP_NAME,
                      "Modbus/RTU request is {0}".format(poll))

    try:
        ser = serial.Serial(port_name, baudrate=baud_rate, bytesize=8,
                            parity='N', stopbits=1, timeout=0.25,
                            xonxoff=0, rtscts=0)

    except serial.SerialException:
        cs.CSClient().log(APP_NAME, "ERROR: Open failed!")
        raise

    try:
        while True:

            cs.CSClient().log(APP_NAME, "Send poll")
            ser.write(poll)
            time.sleep(0.1)

            try:
                response = ser.read(size=255)
            except KeyboardInterrupt:
                cs.CSClient().log(APP_NAME,
                                  "WARNING: Keyboard Interrupt - asked to quit")
                break

            if len(response):
                cs.CSClient().log(APP_NAME,
                                  "Modbus/RTU response is {0}".format(response))

            else:
                cs.CSClient().log(APP_NAME,
                                  "ERROR: no Modbus/RTU response")

            try:
                time.sleep(poll_delay)
            except KeyboardInterrupt:
                cs.CSClient().log(APP_NAME,
                                  "WARNING: Keyboard Interrupt - asked to quit")
                break

    finally:
        ser.close()

    return


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            run_router_app()

        elif command == 'stop':
            # Nothing on stop
            pass

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! ex: {}'.format(APP_NAME, command, ex))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    cs.CSClient().log(APP_NAME, 'args: {})'.format(args))
    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(opt))
        exit()

    action(opt)
