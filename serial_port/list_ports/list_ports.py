import os
import serial
import sys

import cp_lib.hw_status


def do_list_ports(my_logger, my_settings):
    """
    Say hello every 10 seconds

    :param my_logger: a logger
    :type my_logger: logging.Logger
    :param dist my_settings: from the INI file
    :return:
    """

    if cp_lib.hw_status.am_running_on_router():
        # then we are running on Cradlepoint Router:
        pass

        # result = os.listdir("/dev")
        # for name in result:
        #     my_logger.debug("  file:{}".format(name))

        port_list = ("/dev/ttyS0", "/dev/ttyS1")
        name = port_list[1]

        try:
            ser = serial.Serial(name)
            ser.write(name.encode())
            ser.close()
            print("Port({}) exists.".format(name))

        except serial.SerialException:
            print("Port({}) didn't exist.".format(name))

    elif sys.platform == "win32":
        # then handle Windows

        for index in range(1, 17):
            name = "COM%d" % index
            try:
                ser = serial.Serial(name)
                ser.close()
                print("Port({}) exists.".format(name))

            except serial.SerialException:
                print("Port({}) didn't exist.".format(name))

    else:
        raise NotImplementedError(
            "This sample only runs on CP Router or Windows")

    return

if __name__ == "__main__":

    import logging
    import logging.handlers

    logger = logging.getLogger("routerSDK")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")

    # handler = logging.handlers.SysLogHandler(address="/dev/log",
    handler = logging.handlers.SysLogHandler(
        address=("192.168.1.6", 514),
        facility=logging.handlers.SysLogHandler.LOG_LOCAL6)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Starting ...")
    # logger.debug("settings:{}".format(obj.settings))

    do_list_ports(logger, {})
