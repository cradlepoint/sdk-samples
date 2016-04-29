"""
Query the 2x2 power connector I/O
"""
import sys
import time

from cp_lib.app_base import CradlepointAppBase

DEF_INPUT_NAME = "status/gpio/CGPIO_CONNECTOR_INPUT"
DEF_OUTPUT_NAME = "status/gpio/CGPIO_CONNECTOR_OUTPUT"
DEF_LOOP_DELAY = 15


def run_router_app(app_base, loop=True):
    """

    :param CradlepointAppBase app_base: the prepared resources: logger,
                                        cs_client, settings, etc
    :param bool loop: T to loop, else exit
    :return:
    """

    # confirm we are running on 1100/1150, result should be like "IBR1100LPE"
    result = app_base.get_product_name()
    if result in ("IBR1100", "IBR1150"):
        app_base.logger.info("Product Model is good:{}".format(result))
    else:
        app_base.logger.error("Inappropriate Product:{} - aborting.".format(
            result))
        return -1

    input_name = DEF_INPUT_NAME
    output_name = DEF_OUTPUT_NAME
    loop_delay = DEF_LOOP_DELAY
    if "gpio_names" in app_base.settings:
        if "input_name" in app_base.settings["gpio_names"]:
            input_name = app_base.settings["gpio_names"]["input_name"]
        if "output_name" in app_base.settings["gpio_names"]:
            output_name = app_base.settings["gpio_names"]["output_name"]
        loop_delay = float(app_base.settings["gpio_names"].get("loop_delay",
                                                               15))

    if not loop:
        # then we'll jump from loop - likely running as test on a PC computer
        loop_delay = None

    app_base.logger.info("GPIO 2x2  input name:{}".format(input_name))
    app_base.logger.info("GPIO 2x2 output name:{}".format(output_name))

    while True:

        # self.state = self.client.get('/status/gpio/%s' % self.name)
        result_in = app_base.cs_client.get(input_name)
        result_out = app_base.cs_client.get(output_name)
        app_base.logger.info("In={} Out={}".format(result_in, result_out))

        if loop_delay is None:
            # do an invert of output
            if result_out in (1, "1"):
                value = 0
            else:
                value = 1

            # self.client.put('/control/gpio', {self.name: self.state})
            result = app_base.cs_client.put("control/gpio",
                                            {"CGPIO_CONNECTOR_OUTPUT": value})

            if value != int(result):
                app_base.logger.error("BAD - change failed {}".format(result))

            # else app_base.logger.info("Change was GOOD {}".format(result))

            break
        else:
            app_base.logger.debug("Looping - delay {} seconds".format(
                loop_delay))
            time.sleep(loop_delay)

    return 0


if __name__ == "__main__":

    my_app = CradlepointAppBase("gpio/power")

    _result = run_router_app(my_app, loop=False)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
