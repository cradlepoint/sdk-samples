import gc
import random
import threading
import time
from cp_lib.app_base import CradlepointAppBase

# these are required to match in settings.ini
NAME1 = "message1"
NAME2 = "message2"
NAME3 = "message3"

# to make a little more interesting, each sub-task selects a random loop delay
MIN_DELAY = 5
MAX_DELAY = 15


def run_router_app(app_base):
    """
    Say hello every 10 seconds using a task. Note this sample is rather silly
    as the CP router spawns THIS function (run_router_app()) as a unique
    thread. so no point making 1 thread into two!

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """

    # we want a more random pattern; not repeated
    random.seed()

    # task #1 runs "forever"
    my_task1 = HelloOneTask(NAME1, app_base)
    my_task1.start()

    # task #2 runs "forever"
    my_task2 = HelloOneTask(NAME2, app_base)
    my_task2.start()

    # task #3 exits after each delay loop
    my_task3 = HelloOneTask(NAME3, app_base)
    my_task3.start()

    try:
        while True:
            if not my_task3.is_alive():
                # we keep restarting task #3; it will exit always

                # do memory collection, clean-up after old run on task #3
                # else we risk collecting a lot of large chunks
                gc.collect()

                app_base.logger.info("Re-Running task #3")
                my_task3.run()

            time.sleep(30)

    except KeyboardInterrupt:
        # this is only true on a test PC - won't see on router
        # must trap here to prevent try/except in __init__.py from avoiding
        # the graceful shutdown below.
        pass

    # now we need to try & kill off our kids - if we are here
    app_base.logger.info("Okay, exiting")

    # signal sub task to halt
    my_task1.please_stop()
    my_task2.please_stop()
    my_task3.please_stop()

    # what until it does - remember, it is sleeping, so will take some time
    my_task1.join()
    my_task2.join()
    my_task3.join()

    return 0


class HelloOneTask(threading.Thread):

    def __init__(self, name, app_base):
        """
        prep our thread, but do not start yet

        :param str name: name for the thread. We will assume
        :param CradlepointAppBase app_base: prepared resources: logger, etc
        """
        threading.Thread.__init__(self, name=name)

        self.app_base = app_base
        self.app_base.logger.info("started INIT")

        if "hello_world" in app_base.settings and \
                name in app_base.settings["hello_world"]:
            # see if we have 'message' data in settings.ini
            self.say_what = app_base.settings["hello_world"][name]
        else:
            self.say_what = "no message for [%s]!" % name

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
        delay = random.randrange(MIN_DELAY, MAX_DELAY)
        message = "task:{0} Running, delay={1}".format(self.name, delay)
        self.app_base.logger.info(message)

        message = "task:{0} says:{1}".format(self.name, self.say_what)
        self.keep_running.set()
        while self.keep_running.is_set():
            self.app_base.logger.info(message)
            time.sleep(delay)
            if self.name == NAME3:
                # then we exit
                self.keep_running.clear()

        message = "task:{0} was asked to stop!".format(self.name)
        self.app_base.logger.info(message)
        return 0

    def please_stop(self):
        """
        Now thread is being asked to start running
        """
        self.keep_running.clear()
        return
