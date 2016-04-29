import threading
import time
from cp_lib.app_base import CradlepointAppBase


def run_router_app(app_base):
    """
    Say hello every 10 seconds using a task. Note this sample is rather silly
    as the CP router spawns THIS function (run_router_app()) as a unique
    thread. so no point making 1 thread into two!

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    my_task = HelloOneTask("task1", app_base)
    my_task.start()

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

    # signal sub task to halt
    my_task.please_stop()

    # what until it does - remember, it is sleeping, so will take some time
    my_task.join()
    return 0


class HelloOneTask(threading.Thread):

    def __init__(self, name, app_base):
        """
        prep our thread, but do not start yet

        :param str name: name for the thread
        :param CradlepointAppBase app_base: prepared resources: logger, etc
        """
        threading.Thread.__init__(self, name=name)

        self.app_base = app_base
        self.app_base.logger.info("started INIT")

        if "hello_world" in app_base.settings and \
                "message" in app_base.settings["hello_world"]:
            # see if we have 'message' data in settings.ini
            self.say_what = app_base.settings["hello_world"]["message"]
        else:
            self.say_what = "Hello SDK World!"

        # create an event to manage our stopping
        # (Note: on CP router, this isn't strictly true, as when the parent is
        # stopped/halted, the child dies as well. However, you may want
        # your sub task to clean up before it exists
        self.keep_running = threading.Event()
        self.keep_running.set()

        return

    def run(self):
        """
        Now thread is being asked to start running
        """

        self.app_base.logger.info("started RUN")

        message = "task:{0} says:{1}".format(self.name, self.say_what)
        while self.keep_running.is_set():
            self.app_base.logger.info(message)
            time.sleep(10)

        message = "task:{0} was asked to stop!".format(self.name)
        self.app_base.logger.info(message)
        return 0

    def please_stop(self):
        """
        Now thread is being asked to start running
        """
        self.keep_running.clear()
        return
