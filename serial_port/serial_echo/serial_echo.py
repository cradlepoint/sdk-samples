"""
Serial echo
"""
import sys
import serial

from cp_lib.app_base import CradlepointAppBase

DEF_BAUD_RATE = 9600
DEF_PORT_NAME = "/dev/ttyS1"


def run_main(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return list:
    """
    # confirm we are running on an 1100/1150, result should be "IBR1100LPE"
    result = app_base.get_product_name()
    if result in ("IBR1100", "IBR1150"):
        app_base.logger.info("Product Model is good:{}".format(result))
    else:
        app_base.logger.error(
            "Inappropriate Product:{} - aborting.".format(result))
        return -1

    port_name = DEF_PORT_NAME
    baud_rate = DEF_BAUD_RATE
    if "serial_echo" in app_base.settings:
        if "port_name" in app_base.settings["serial_echo"]:
            port_name = app_base.settings["serial_echo"]["port_name"]
        if "baud_rate" in app_base.settings["serial_echo"]:
            baud_rate = int(app_base.settings["serial_echo"]["baud_rate"])

    message = "Starting serial echo on {0}, baud={1}".format(port_name,
                                                             baud_rate)
    app_base.logger.info(message)

    ser = serial.Serial(port_name, baudrate=baud_rate, bytesize=8, parity='N',
                        stopbits=1, timeout=1, xonxoff=0, rtscts=0)

    # start as None to force at least 1 change
    dsr_was = None
    cts_was = None

    try:
        while True:
            data = ser.read(size=1)
            if len(data):
                app_base.logger.debug(str(data))
                ser.write(data)
            # else:
            #     app_base.logger.debug(b".")

            if dsr_was != ser.dsr:
                dsr_was = ser.dsr
                app_base.logger.info(
                    "DSR changed to {}, setting DTR".format(dsr_was))
                ser.dtr = dsr_was

            if cts_was != ser.cts:
                cts_was = ser.cts
                app_base.logger.info(
                    "CTS changed to {}, setting RTS".format(cts_was))
                ser.rts = cts_was

    finally:
        ser.close()

    return


if __name__ == "__main__":
    my_app = CradlepointAppBase("serial/serial_echo")

    _result = run_main(my_app)

    my_app.logger.info("Exiting, status code is {}".format(_result))

    sys.exit(_result)
