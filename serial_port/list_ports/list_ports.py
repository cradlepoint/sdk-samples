import serial
import sys

import cp_lib.hw_status
from cp_lib.app_base import CradlepointAppBase
from cp_lib.parse_data import parse_boolean

DEF_PROBE_PHYSICAL = True
DEF_PROBE_USB = True
DEF_WRITE_NAME = False
# this exists on most, but is for internal use.
IGNORE_TTYS0 = True

PORT_LIST_PHYSICAL = (1, 2)
PORT_LIST_USB = (0, 1, 2, 3, 4)


def run_router_app(app_base):
    """
    Do the probe/check of

    :param CradlepointAppBase app_base: the prepared resources: logger,
                                        cs_client, settings, etc
    :return:
    """

    # as of Mat-2016/FW=6.1, PySerial is version 2.6 (2.6-pre1)
    app_base.logger.info("serial.VERSION = {}.".format(serial.VERSION))

    probe_physical = DEF_PROBE_PHYSICAL
    probe_usb = DEF_PROBE_USB
    write_name = DEF_WRITE_NAME

    app_key = "list_ports"
    if app_key in app_base.settings:
        if "probe_physical" in app_base.settings[app_key]:
            probe_physical = parse_boolean(
                app_base.settings[app_key]["probe_physical"])
        if "probe_usb" in app_base.settings[app_key]:
            probe_usb = parse_boolean(
                app_base.settings[app_key]["probe_usb"])
        if "write_name" in app_base.settings[app_key]:
            write_name = parse_boolean(
                app_base.settings[app_key]["write_name"])

    if cp_lib.hw_status.am_running_on_router():
        # then we are running on Cradlepoint Router:

        # probe_directory(app_base, "/dev")
        port_list = []

        # confirm we are running on an 1100/1150, result should be "IBR1100LPE"
        result = app_base.get_product_name()
        if result in ("IBR1100", "IBR1150"):
            name = "/dev/ttyS1"
            app_base.logger.info(
                "Product Model {} has 1 builtin port:{}".format(
                    result, name))
            port_list.append(name)

        elif result in ("IBR300", "IBR350"):
            app_base.logger.warning(
                "Product Model {} has no serial support".format(result))

        else:
            app_base.logger.error(
                "Inappropriate Product:{} - aborting.".format(result))
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
            probe_serial(app_base, name, write_name)

    elif sys.platform == "win32":
        # then handle Windows

        for index in range(1, 17):
            name = "COM%d" % index
            try:
                ser = serial.Serial(name)
                ser.close()
                app_base.logger.info("Port({}) exists.".format(name))

            except serial.SerialException:
                app_base.logger.info("Port({}) didn't exist.".format(name))

    else:
        raise NotImplementedError(
            "This sample only runs on CP Router or Windows")

    return 0


def probe_serial(app_base, port_name, write_name=False):
    """
    dump a directory in router FW

    :param CradlepointAppBase app_base: resources: logger, settings, etc
    :param str port_name: the port name
    :param bool write_name: if T, write out the name
    """
    try:
        ser = serial.Serial(port_name, dsrdtr=False, rtscts=False)
        if write_name:
            port_name += '\r\n'
            ser.write(port_name.encode())
        app_base.logger.info("Port({}) exists.".format(port_name))

        # as of Mat-2016/FW=6.1, PySerial is version 2.6
        # therefore .getDSR() works and .dsr does not!
        try:
            app_base.logger.info(" serial.dsr = {}.".format(ser.dsr))
        except AttributeError:
            app_base.logger.info(" serial.dsr is not supported!")

        try:
            app_base.logger.info(" serial.getDSR() = {}.".format(ser.getDSR()))
        except AttributeError:
            app_base.logger.info(" serial.getDSR() is not supported!")

        ser.close()
        return True

    except (serial.SerialException, FileNotFoundError):
        app_base.logger.info("Port({}) didn't exist.".format(port_name))
        return False


def probe_directory(app_base, base_dir):
    """
    dump a directory in router FW

    :param CradlepointAppBase app_base: resources: logger, settings, etc
    :param str base_dir: the directory to dump
    """
    import os

    app_base.logger.debug("Dump Directory:{}".format(base_dir))
    result = os.access(base_dir, os.R_OK)
    if result:
        app_base.logger.debug("GOOD name:{}".format(base_dir))
    else:
        app_base.logger.debug("BAD name:{}".format(base_dir))

    if result:
        result = os.listdir(base_dir)
        for name in result:
            app_base.logger.debug("  file:{}".format(name))
    return

if __name__ == "__main__":

    my_app = CradlepointAppBase("serial_port/list_ports")

    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
