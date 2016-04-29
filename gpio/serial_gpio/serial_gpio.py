"""
Query the 2x2 power connector I/O
"""
import sys
import time

from cp_lib.app_base import CradlepointAppBase

DEF_SERIAL_NAME_1 = "status/gpio/CGPIO_SERIAL_INPUT_1"
DEF_SERIAL_NAME_2 = "status/gpio/CGPIO_SERIAL_INPUT_2"
DEF_SERIAL_NAME_3 = "status/gpio/CGPIO_SERIAL_INPUT_3"

DEF_LOOP_DELAY = 15


def read_gpio(app_base, loop=True):
    """

    :param CradlepointAppBase app_base: the prepared resources: logger, cs_client, settings, etc
    :param bool loop: T to loop, else exit
    :return:
    """

    # confirm we are running on an 1100/1150, result should be like "IBR1100LPE"
    result = app_base.get_product_name()
    if result in ("IBR1100", "IBR1150"):
        app_base.logger.info("Product Model is good:{}".format(result))
    else:
        app_base.logger.error("Inappropriate Product:{} - aborting.".format(result))
        return -1

    loop_delay = DEF_LOOP_DELAY
    if "gpio_names" in app_base.settings:
        loop_delay = float(app_base.settings["gpio_names"].get("loop_delay", 15))

    if not loop:
        # then we'll jump from loop - likely we are running as test on a PC computer
        loop_delay = None

    # confirm we have the 1100 serial GPIO enabled, so return is True or False
    result = app_base.cs_client.get_bool("status/system/gpio_actions/")
    app_base.logger.debug("GET: status/system/gpio_actions/ = [{}]".format(result))
    if result is None:
        # then the serial GPIO function is NOT enabled
        app_base.logger.error("The Serial GPIO is NOT enabled!")
        app_base.logger.info("Router Application is exiting")
        return -1

    while loop_delay:
        # loop as long as not None or zero
        result1 = app_base.cs_client.get(DEF_SERIAL_NAME_1)
        result2 = app_base.cs_client.get(DEF_SERIAL_NAME_2)
        result3 = app_base.cs_client.get(DEF_SERIAL_NAME_3)
        app_base.logger.info("Inp = ({}, {}, {})".format(result1, result2, result3))

        app_base.logger.debug("Looping - delay {} seconds".format(loop_delay))
        time.sleep(loop_delay)

    app_base.logger.info("Router Application is exiting")
    return 0


if __name__ == "__main__":
    my_app = CradlepointAppBase("gpio/serial_gpio")

    _result = read_gpio(my_app, loop=False)

    my_app.logger.info("Exiting, status code is {}".format(_result))

    sys.exit(_result)
