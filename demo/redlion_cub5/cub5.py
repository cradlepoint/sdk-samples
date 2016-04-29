import threading
import time

from cp_lib.app_base import CradlepointAppBase
from cp_lib.cp_email import cp_send_email
from cp_lib.parse_duration import TimeDuration
from cp_lib.parse_data import parse_boolean

power_loss_task = None


def run_router_app(app_base, wait_for_child=True):
    """
    Start our thread

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param bool wait_for_child: T to wait in loop, F to return immediately
    :return:
    """
    global power_loss_task

    # confirm we are running on 1100/1150, result should be like "IBR1100LPE"
    result = app_base.get_product_name()
    if result in ("IBR1100", "IBR1150"):
        app_base.logger.info(
            "Product Model is good:{}".format(result))
    else:
        app_base.logger.error(
            "Inappropriate Product:{} - aborting.".format(result))
        return -1

    power_loss_task = PowerLoss("power_loss", app_base)
    power_loss_task.start()

    if wait_for_child:
        # we block on this sub task - for testing
        try:
            while True:
                time.sleep(300)

        except KeyboardInterrupt:
            # this is only true on a test PC - won't see on router
            # must trap here to prevent try/except in __init__.py from avoiding
            # the graceful shutdown below.
            pass

        # now we need to try & kill off our kids - if we are here
        app_base.logger.info("Okay, exiting")

        stop_router_app(app_base)

    else:
        # we return ASAP, assume this is 1 of many tasks run by single parent
        app_base.logger.info("Exit immediately, leave sub-task run")

    return 0
