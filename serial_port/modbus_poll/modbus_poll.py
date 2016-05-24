"""
Serial echo
"""
import sys
import serial
import time

from cp_lib.app_base import CradlepointAppBase
from cp_lib.parse_duration import TimeDuration
from serial_port.modbus_poll.crc16 import calc_string

DEF_BAUD_RATE = 9600
DEF_PORT_NAME = "/dev/ttyS1"
DEF_REG_START = 0
DEF_REG_COUNT = 1
DEF_SLAVE_ADDRESS = 1
DEF_POLL_DELAY = 5


def run_router_app(app_base):
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

    period = TimeDuration(DEF_POLL_DELAY)

    port_name = DEF_PORT_NAME
    baud_rate = DEF_BAUD_RATE
    register_start = DEF_REG_START
    register_count = DEF_REG_COUNT
    slave_address = DEF_SLAVE_ADDRESS
    poll_delay = period.get_seconds()

    app_key = "modbus"
    if app_key in app_base.settings:
        if "port_name" in app_base.settings[app_key]:
            port_name = app_base.settings[app_key]["port_name"]
        if "baud_rate" in app_base.settings[app_key]:
            baud_rate = int(app_base.settings[app_key]["baud_rate"])
        if "register_start" in app_base.settings[app_key]:
            register_start = int(app_base.settings[app_key]["register_start"])
        if "register_count" in app_base.settings[app_key]:
            register_count = int(app_base.settings[app_key]["register_count"])
        if "slave_address" in app_base.settings[app_key]:
            slave_address = int(app_base.settings[app_key]["slave_address"])
        if "poll_delay" in app_base.settings[app_key]:
            poll_delay = app_base.settings[app_key]["poll_delay"]
            poll_delay = period.parse_time_duration_to_seconds(poll_delay)

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
    crc = calc_string(poll)
    app_base.logger.debug("CRC = %04X" % crc)
    poll += bytes([crc & 0xFF, (crc & 0xFF00) >> 8])

    app_base.logger.info(
        "Starting Modbus/RTU poll {0}, baud={1}".format(port_name, baud_rate))
    app_base.logger.info(
        "Modbus/RTU request is {0}".format(poll))

    try:
        ser = serial.Serial(port_name, baudrate=baud_rate, bytesize=8,
                            parity='N', stopbits=1, timeout=0.25,
                            xonxoff=0, rtscts=0)

    except serial.SerialException:
        app_base.logger.error("Open failed!")
        raise

    try:
        while True:

            app_base.logger.info("Send poll")
            ser.write(poll)
            time.sleep(0.1)

            try:
                response = ser.read(size=255)
            except KeyboardInterrupt:
                app_base.logger.warning(
                    "Keyboard Interrupt - asked to quit")
                break

            if len(response):
                app_base.logger.info(
                    "Modbus/RTU response is {0}".format(response))

            else:
                app_base.logger.error(
                    "no Modbus/RTU response")

            try:
                time.sleep(poll_delay)
            except KeyboardInterrupt:
                app_base.logger.warning(
                    "Keyboard Interrupt - asked to quit")
                break

    finally:
        ser.close()

    return


if __name__ == "__main__":
    my_app = CradlepointAppBase("serial/serial_echo")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
