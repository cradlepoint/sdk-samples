import os
import serial
import sys

import cp_lib.hw_status
from cp_lib.app_base import CradlepointAppBase


def run_router_app(app_base):
    """
    Do the probe/check of

    :param CradlepointAppBase app_base: the prepared resources: logger,
                                        cs_client, settings, etc
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

    return 0

if __name__ == "__main__":

    my_app = CradlepointAppBase("serial_port/list_ports")

    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
