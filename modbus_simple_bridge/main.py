import importlib
import logging
import sys
import time

# local imports
import cp_lib.hw_status as hw_status
from cp_lib.load_settings_json import load_settings_json
from cp_lib.parse_duration import TimeDuration


class MainStartUp(object):

    # the settings used by main.py are in section [startup]
    SECTION_STARTUP = "startup"

    # ["boot_delay_max"] is int, is how long to delay for desired
    #                                conditions to be true
    SET_BOOT_DELAY_SEC = "boot_delay_max"
    DEF_BOOT_DELAY_SEC = 300
    BOOT_DELAY_SLEEP = 5.0

    # ["boot_delay_for_time"] is bool, True to wait for time.time() > 2016
    SET_DELAY_FOR_TIME = "boot_delay_for_time"
    DEF_DELAY_FOR_TIME = True

    # ["boot_delay_for_wan"] is bool, True to wait for WAN/external
    #                                 internet uplink is okay
    SET_DELAY_FOR_WAN = "boot_delay_for_wan"
    DEF_DELAY_FOR_WAN = True

    # ["exit_delay"] is int, is how long to delay at end of main() run
    SETS_EXIT_DELAY = "exit_delay"
    DEFAULT_EXIT_DELAY = None
    EXIT_DELAY_PERIOD = 10.0

    def __init__(self):
        """

        :return:
        """

        # internal settings for MAIN
        self.settings = {}

        return

    def main(self, app_main):
        """
        :param str app_main: the file name, such as "network.tcp_echo"
        :return int: code for sys.exit()
        """

        # in windows, safer to use time.clock(), but is useless in Linux
        start_time = time.time()

        logging.info("Router APP starting: {}".format(app_main))

        # follow SDK design to load settings, should be in root of tar.gzip
        self.settings = load_settings_json()

        # delay until all desired conditions are met
        self.start_delay()

        app_mod = importlib.import_module(app_main)
        app_base = app_mod.RouterApp(app_main)

        if True:
            # app_mod = importlib.import_module(app_main, "RouterApp")
            # app_mod = importlib.import_module("network.tcp_echo.tcp_echo")
            # print(app_mod)
            result = app_base.run()
        else:
            result = 0

        # see if we should delay before existing
        exit_delay = self.DEFAULT_EXIT_DELAY
        if self.SECTION_STARTUP in self.settings:
            # then we do have a [startup] section in settings.json

            if self.SETS_EXIT_DELAY in self.settings[self.SECTION_STARTUP]:
                # how many seconds to wait for boot conditions to be satisfied
                # here is string, we don't care what yet
                exit_delay = self.settings[self.SECTION_STARTUP][
                    self.SETS_EXIT_DELAY].lower()

        if exit_delay in ('forever', 'loop', 'true'):
            # we loop forever - use 'uninstall' action to stop
            while True:
                app_base.logger.debug("App Finished - Looping forever")
                time.sleep(self.EXIT_DELAY_PERIOD)

        elif exit_delay in (None, 'none', 'null', 'false'):
            # default - no delay at all
            app_base.logger.info("App exited - MAIN Exiting without delay")

        else:
            # if this throws exception, well we exit anyway
            # use time_duration to handle "300" or "5 min"
            time_duration = TimeDuration(exit_delay)
            exit_delay = time_duration.get_seconds()

            time_diff = time.time() - start_time
            if time_diff >= exit_delay:
                # app took longer than 'min delay', so just exist
                app_base.logger.info("No need for exit delay")
            else:
                # else, app was short/fast, delay to reduce restart thrashing
                app_base.logger.info(
                    "Exit Delay for at least {} seconds".format(exit_delay))
                while time_diff < exit_delay:
                    app_base.logger.debug(
                        "Exit Delay, wait at least %d seconds more" % int(
                            exit_delay - time_diff))
                    time.sleep(self.EXIT_DELAY_PERIOD)
                    time_diff = time.time() - start_time
                app_base.logger.info("Exit Delay finished")

        return result

    def start_delay(self):
        """
        Delay up to config seconds, waiting for boot conditions to be true

        :return: None
        """
        # we only delay if at least ONE condition is still not satisfied
        wait_conditions = 0

        time_duration = TimeDuration()

        # start with the defaults
        # use time_duration to handle "300" or "5 min"
        time_duration.parse_time_duration_to_seconds(
            self.DEF_BOOT_DELAY_SEC)
        delay_seconds = time_duration.get_seconds()
        delay_for_valid_time = self.DEF_DELAY_FOR_TIME
        delay_for_uplink = self.DEF_DELAY_FOR_WAN

        if self.SECTION_STARTUP in self.settings:
            # then we do have a [startup] section in settings.json

            if self.SET_BOOT_DELAY_SEC in self.settings[self.SECTION_STARTUP]:
                # how many seconds to wait for boot conditions to be satisfied
                time_duration.parse_time_duration_to_seconds(
                    self.settings[self.SECTION_STARTUP][self.SET_BOOT_DELAY_SEC])
                delay_seconds = time_duration.get_seconds()

            if self.SET_DELAY_FOR_TIME in self.settings[self.SECTION_STARTUP]:
                # see if we delay until time.time() is returning valid info,
                # which prevents initial time-series data from being
                # generated with bogus 1-1-1970 time-stamps
                delay_for_valid_time = \
                    self.settings[self.SECTION_STARTUP][self.SET_DELAY_FOR_TIME]

            if self.SET_DELAY_FOR_WAN in self.settings[self.SECTION_STARTUP]:
                # see if we delay until router has a valid WAN uplink, which
                # prevents cloud clients from mistakenly flipping into
                # FAULT/RECOVERY modes because they tried to connect to fast
                delay_for_uplink = self.settings[self.SECTION_STARTUP][
                    self.SET_DELAY_FOR_WAN]

        if delay_for_valid_time:
            wait_conditions += 1

        if delay_for_uplink:
            wait_conditions += 1

        # we cannot use clock() because under Linux it means nothing
        # TODO - what happens when time() jumps?
        start_time = time.time()
        while (wait_conditions > 0) and \
                (time.time() - start_time) < delay_seconds:
            # loop until end of time period, or all conditions are okay

            if delay_for_valid_time and hw_status.router_time_is_valid():
                # then check on time, if okay neutralize our conditions
                delay_for_valid_time = False
                wait_conditions -= 1
            else:
                logging.debug("Delay - waiting for valid time")

            if delay_for_uplink and hw_status.router_wan_online():
                # then check on wan-uplink, is okay neutralize our conditions
                delay_for_uplink = False
                wait_conditions -= 1
            else:
                logging.debug("Delay - waiting for WAN uplink")

            if wait_conditions > 0:
                time.sleep(self.BOOT_DELAY_SLEEP)
            # else we'll break / leave the WHILE loop

        return

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        # the first param must be
        logging.error("usage: python main.py {router app}.py")
        sys.exit(-1)

    maker = MainStartUp()
    _result = maker.main(sys.argv[1])
    if _result:
        logging.error("Exiting, status code is {}".format(_result))

    sys.exit(_result)
