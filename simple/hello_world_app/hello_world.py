import time
from cp_lib.app_base import CradlepointAppBase


def do_hello_world(app_base):
    """
    Say hello every 10 seconds

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    if "hello_world" in app_base.settings and \
            "message" in app_base.settings["hello_world"]:
        # see if we have 'message' data in settings.ini
        say_what = app_base.settings["hello_world"]["message"]
    else:
        say_what = "Hello SDK World!"

    while True:
        app_base.logger.info(say_what)
        time.sleep(10)
