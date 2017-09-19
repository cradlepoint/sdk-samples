"""
Serial echo

Wait for data to enter the serial port, then echo back out. 
Data will be processed byte by byte, although you could edit the 
sample code to wait for an end-of-line character.

"""

import json
import serial
import argparse
import cs

APP_NAME = 'serial_echo'

# set to None to disable, or set to bytes to send
ASK_ARE_YOU_THERE = b"u there?"


def run_router_app():
    # confirm we are running on an 1100/1150, 900/950, or 600/650. result should be like "IBR1100LPE"
    result = json.loads(cs.CSClient().get("status/product_info/product_name"))
    if "IBR1100" in result or "IBR1150" in result or \
       "IBR900" in result or "IBR950" in result or \
       "IBR600" in result or "IBR650" in result:
        cs.CSClient().log(APP_NAME, "Product Model is good:{}".format(result))
    else:
        cs.CSClient().log(APP_NAME,
                          "Inappropriate Product:{} - aborting.".format(result))
        return -1

    port_name = 9600
    baud_rate = '/dev/ttyS1'

    # see if port is a digit?
    if port_name[0].isdecimal():
        port_name = int(port_name)

    old_pyserial = serial.VERSION.startswith("2.6")

    message = "Starting serial echo on {0}, baud={1}".format(port_name,
                                                             baud_rate)
    cs.CSClient().log(APP_NAME, message)

    try:
        ser = serial.Serial(port_name, baudrate=baud_rate, bytesize=8,
                            parity='N', stopbits=1, timeout=1,
                            xonxoff=0, rtscts=0)

    except serial.SerialException:
        cs.CSClient().log(APP_NAME, "ERROR: Open failed!")
        raise

    # start as None to force at least 1 change
    dsr_was = None
    cts_was = None

    try:
        while True:
            try:
                data = ser.read(size=1)
            except KeyboardInterrupt:
                cs.CSClient().log(APP_NAME,
                                  "WARNING: Keyboard Interrupt - asked to quit")
                break

            if len(data):
                cs.CSClient().log(APP_NAME, str(data))
                ser.write(data)
            elif ASK_ARE_YOU_THERE is not None:
                ser.write(ASK_ARE_YOU_THERE)
            # else:
            #     app_base.logger.debug(b".")

            if old_pyserial:
                # as of May-2016/FW 6.1, this is PySerial v2.6, so it uses
                # the older style control signal access
                if dsr_was != ser.getDSR():
                    # do this 'get' twice to handle first pass as None
                    dsr_was = ser.getDSR()
                    cs.CSClient().log(APP_NAME,
                                      "DSR changed to {}, setting DTR".format(dsr_was))
                    ser.setDTR(dsr_was)

                if cts_was != ser.getCTS():
                    cts_was = ser.getCTS()
                    cs.CSClient().log(APP_NAME,
                                      "CTS changed to {}, setting RTS".format(cts_was))
                    ser.setRTS(cts_was)
            else:
                if dsr_was != ser.dsr:
                    dsr_was = ser.dsr
                    cs.CSClient().log(APP_NAME,
                                      "DSR changed to {}, setting DTR".format(dsr_was))
                    ser.dtr = dsr_was

                if cts_was != ser.cts:
                    cts_was = ser.cts
                    cs.CSClient().log(APP_NAME,
                                      "CTS changed to {}, setting RTS".format(cts_was))
                    ser.rts = cts_was

            # if you lose the serial port - like disconnected, then
            # ser.getDSR() will throw OSError #5 Input/Output error

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
