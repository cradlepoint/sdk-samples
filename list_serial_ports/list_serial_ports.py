import argparse
import serial
import json
import cs

'''
This sample code runs through one check, then exits.
Assuming you have 'restart' true in your settings.ini file, then
the code restarts forever.

Based on the model of router you have, it checks to see if the ports below
exist, can be opened, and the name of the port written to it.

Real Physical ports:

* /dev/ttyS1 (only on models such as IBR1100)
* /dev/ttyS2 (normally will fail/not exist)

USB serial ports:

* /dev/ttyUSB0
* /dev/ttyUSB1
* /dev/ttyUSB2
* /dev/ttyUSB3
* /dev/ttyUSB4

Most USB-serial devices with an FTDI-chipset can be used.
'''

# this exists on most, but is for internal use.
IGNORE_TTYS0 = True

PORT_LIST_PHYSICAL = (1, 2)
PORT_LIST_USB = (0, 1, 2, 3, 4)

APP_NAME = 'list_serial_ports'


def run_router_app():
    """
    Do the probe/check of
    """

    # as of Mat-2016/FW=6.1, PySerial is version 2.6 (2.6-pre1)
    cs.CSClient().log(APP_NAME, "serial.VERSION = {}.".format(serial.VERSION))

    # probe_physical = True, set False to NOT probe real physical serial ports.
    # On models without physical ports, this setting is ignored.
    probe_physical = True

    # probe_usb = True, set False to NOT probe for USB serial ports.
    probe_usb = True

    # write_name = True, set False to NOT send out the port name, which is
    # sent to help you identify between multiple ports.
    write_name = False

    # probe_directory(app_base, "/dev")
    port_list = []

    # confirm we are running on an 1100/1150 or 900/950, result should be "IBR1100LPE"
    result = cs.CSClient().get("status/product_info/product_name").get('data')
    if "IBR1100" in result or "IBR1150" in result or "IBR900" in result or "IBR950" in result:
        name = "/dev/ttyS1"
        cs.CSClient().log(APP_NAME, "Product Model {} has 1 builtin port:{}".format(result, name))
        port_list.append(name)

    elif "IBR300" in result or "IBR350" in result:
        cs.CSClient().log(APP_NAME, "Product Model {} has no serial support".format(result))

    else:
        cs.CSClient().log(APP_NAME, "Inappropriate Product:{} - aborting.".format(result))
        return -1

    if probe_physical:
        # fixed ports - 1100 only?
        if not IGNORE_TTYS0:
            # only check S0 if 'requested' to, else ignore
            name = "/dev/ttyS0"
            if name not in port_list:
                port_list.append(name)

        for port in PORT_LIST_PHYSICAL:
            name = "/dev/ttyS%d" % port
            if name not in port_list:
                port_list.append(name)

    if probe_usb:
        # try first 5 USB
        for port in PORT_LIST_USB:
            name = "/dev/ttyUSB%d" % port
            if name not in port_list:
                port_list.append(name)

    # cycle through and probe the desired ports
    for name in port_list:
        probe_serial(name, write_name)

    return 0


def probe_serial(port_name, write_name=False):
    """
    dump a directory in router FW
    """
    try:
        ser = serial.Serial(port_name, dsrdtr=False, rtscts=False)
        if write_name:
            port_name += '\r\n'
            ser.write(port_name.encode())

        cs.CSClient().log(APP_NAME, "Port({}) exists.".format(port_name))

        # as of Mat-2016/FW=6.1, PySerial is version 2.6
        # therefore .getDSR() works and .dsr does not!
        try:
            cs.CSClient().log(APP_NAME, " serial.dsr = {}.".format(ser.dsr))
        except AttributeError:
            cs.CSClient().log(APP_NAME, " serial.dsr is not supported!")

        try:
            cs.CSClient().log(APP_NAME, " serial.getDSR() = {}.".format(ser.getDSR()))
        except AttributeError:
            cs.CSClient().log(APP_NAME, " serial.getDSR() is not supported!")

        ser.close()
        return True

    except (serial.SerialException, FileNotFoundError):
        cs.CSClient().log(APP_NAME, "Port({}) didn't exist.".format(port_name))
        return False


def probe_directory(base_dir):
    """
    dump a directory in router FW
    """
    import os

    cs.CSClient().log(APP_NAME, "Dump Directory:{}".format(base_dir))
    result = os.access(base_dir, os.R_OK)
    if result:
        cs.CSClient().log(APP_NAME, "GOOD name:{}".format(base_dir))
    else:
        cs.CSClient().log(APP_NAME, "BAD name:{}".format(base_dir))

    if result:
        result = os.listdir(base_dir)
        for name in result:
            cs.CSClient().log(APP_NAME, "  file:{}".format(name))
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

    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
