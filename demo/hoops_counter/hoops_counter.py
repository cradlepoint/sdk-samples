import threading
import time

import network.digit_web
import data.jsonrpc_settings
from cp_lib.app_base import CradlepointAppBase


def run_router_app(app_base, wait_for_child=True):
    """
    Start our thread

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param bool wait_for_child: T to wait in loop, F to return immediately
    :return:
    """

    # confirm we are running on 1100/1150, result should be like "IBR1100LPE"
    result = app_base.get_product_name()
    if result in ("IBR1100", "IBR1150"):
        app_base.logger.info(
            "Product Model is good:{}".format(result))
    else:
        app_base.logger.error(
            "Inappropriate Product:{} - aborting.".format(result))
        return -1

    app_base.logger.info("STARTING the Web Server Task")
    web_task = network.digit_web.run_router_app(app_base)
    app_base.logger.info("  Web Server Task started")

    app_base.logger.info("STARTING the JSON Server Task")
    json_task = data.jsonrpc_settings.run_router_app(app_base)
    app_base.logger.info("  JSON Server Task started")

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


def stop_router_app(app_base):
    """
    Stop the thread

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    return 0


