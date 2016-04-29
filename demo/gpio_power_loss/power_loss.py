import threading
import time

from cp_lib.app_base import CradlepointAppBase
from cp_lib.cp_email import cp_send_email
from cp_lib.parse_duration import TimeDuration
from cp_lib.parse_data import parse_boolean, parse_none

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


def stop_router_app(app_base):
    """
    Stop the thread

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    global power_loss_task

    if power_loss_task is not None:
        app_base.logger.info("Signal PowerLoss sub-task to stop")

        # signal sub task to halt
        power_loss_task.please_stop()

        # what until it does - remember, it is sleeping, so will take some time
        power_loss_task.join()

    return 0


class PowerLoss(threading.Thread):

    DEF_INPUT_NAME = "status/gpio/CGPIO_CONNECTOR_INPUT"

    def __init__(self, name, app_base):
        """
        prep our thread, but do not start yet

        :param str name: name for the thread
        :param CradlepointAppBase app_base: prepared resources: logger, etc
        """
        threading.Thread.__init__(self, name=name)

        self.app_base = app_base
        self.app_base.logger.info("started INIT")

        # how long to delay between checking the GPIO
        self.loop_delay = self.app_base.settings["power_loss"].get(
            "check_input_delay", 15)
        # support things like '1 min' or 15
        duration = TimeDuration(self.loop_delay)
        self.loop_delay = float(duration.get_seconds())

        # how long to wait, to double-check LOSS
        self.loss_delay = self.app_base.settings["power_loss"].get(
            "loss_delay", 1)
        self.loss_delay = duration.parse_time_duration_to_seconds(
            self.loss_delay)

        # how long to wait, to double-check RESTORE
        self.restore_delay = self.app_base.settings["power_loss"].get(
            "restore_delay", 1)
        self.restore_delay = duration.parse_time_duration_to_seconds(
            self.restore_delay)

        # when GPIO matches this state, then power is lost
        self.state_in_alarm = self.app_base.settings["power_loss"].get(
            "match_on_power_loss", False)
        # support 'true', '1' etc - but finally is True/False
        self.state_in_alarm = parse_boolean(self.state_in_alarm)

        # when 'power is lost', send to LED
        self.led_in_alarm = self.app_base.settings["power_loss"].get(
            "led_on_power_loss", None)
        try:
            # see if the setting is None, to disable
            self.led_in_alarm = parse_none(self.led_in_alarm)

        except ValueError:
            # support 'true', '1' etc - but finally is True/False
            self.led_in_alarm = parse_boolean(self.led_in_alarm)

        # when GPIO matches this state, then power is lost
        self.site_name = self.app_base.settings["power_loss"].get(
            "site_name", "My Site")

        # create an event to manage our stopping
        # (Note: on CP router, this isn't strictly true, as when the parent is
        # stopped/halted, the child dies as well. However, you may want
        # your sub task to clean up before it exists
        self.keep_running = threading.Event()
        self.keep_running.set()

        # hold the .get_power_loss_status()
        self.last_state = None

        # special tweak to announce 'first poll' more smartly
        self.starting_up = True

        self.email_settings = dict()
        self.prep_email_settings()

        return

    def run(self):
        """
        Now thread is being asked to start running
        """

        self.app_base.logger.info("Running")

        self.app_base.cs_client.show_rsp = False

        while self.keep_running.is_set():

            # check the GPIO input status, likely is string
            result = self.get_power_loss_status()
            if result == self.last_state:
                # then no change
                pass
                # self.app_base.logger.debug(
                #     "State has not changed, still={}".format(result))

            elif result is None:
                # handle hiccups? Try again?
                pass

            else:
                # else state has been changed
                self.last_state = result
                if self.last_state:
                    # changed state = True, power has been LOST
                    self.app_base.logger.debug(
                        "State changed={}, POWER LOST!".format(
                            self.last_state))

                    # double-check if really lost
                    self.app_base.logger.debug(
                        "Delay %d sec to double-check" % int(
                            self.loss_delay))
                    time.sleep(self.loss_delay)
                    result = self.get_power_loss_status()
                    if result:
                        # then power really is lost
                        self.do_power_lost_event()
                    else:
                        self.last_state = result
                        self.app_base.logger.debug("False Alarm")

                else:
                    # changed state = False, power has been RESTORED
                    self.app_base.logger.info(
                        "State changed={}, POWER OKAY".format(
                            self.last_state))

                    # double-check if really restored
                    self.app_base.logger.debug(
                        "Delay %d sec to double-check" % int(
                            self.restore_delay))
                    time.sleep(self.restore_delay)
                    result = self.get_power_loss_status()
                    if not result:
                        # then power really is restored
                        self.do_power_restore_event()
                    else:
                        self.last_state = result
                        self.app_base.logger.debug("False Alarm")

            time.sleep(self.loop_delay)

        self.app_base.logger.info("Stopping")
        return 0

    def please_stop(self):
        """
        Now thread is being asked to start running
        """
        self.keep_running.clear()
        return

    def get_power_loss_status(self):
        """
        Fetch the GPIO input state, return reading, which may not
        be directly related to power status.

        :return bool: return True/False, for condition of 'power is lost'
        """
        # check the GPIO input status, likely is string
        result = self.app_base.cs_client.get(self.DEF_INPUT_NAME)
        if result in (1, '1'):
            result = True
        elif result in (0, '0'):
            result = False
        else:
            # ?? what if we hiccup & have a bad reading?
            return None

        # self.app_base.logger.debug("result:{} alarm:{} is_lost:{}".format(
        #     result, self.state_in_alarm, self.power_is_lost(result)))

        return self.power_is_lost(result)

    def do_power_lost_event(self):
        """
        Do what we need to when power is lost
        :return:
        """
        if self.starting_up:
            # special tweak to announce 'first poll' more smartly
            self.starting_up = False
            message =\
                "Starting Up: AC Power OFF at site: {}".format(self.site_name)
        else:
            message =\
                "Bad News! AC Power lost at site: {}".format(self.site_name)
        self._do_event(message, alarm=True)

        if self.led_in_alarm is not None:
            # then affect LED output, since in alarm, set to led_in_alarm
            self.app_base.cs_client.put(
                "control/gpio",
                {"CGPIO_CONNECTOR_OUTPUT": int(self.led_in_alarm)})
        return

    def do_power_restore_event(self):
        """
        Do what we need to when power is restored
        :return:
        """
        if self.starting_up:
            # special tweak to announce 'first poll' more smartly
            self.starting_up = False
            message =\
                "Starting Up: AC Power ON at site: {}".format(self.site_name)
        else:
            message =\
                "Good News! AC Power restored at site: {}".format(
                    self.site_name)
        self._do_event(message, alarm=False)

        if self.led_in_alarm is not None:
            # affect LED output, since not in alarm, set to NOT led_in_alarm
            self.app_base.cs_client.put(
                "control/gpio",
                {"CGPIO_CONNECTOR_OUTPUT": int(not self.led_in_alarm)})
        return

    def _do_event(self, message, alarm):
        """
        Wrap the logging anf email action

        :param str message: the email subject with site_name
        :param bool alarm: T/F if this is bad/alarm, of good/return-to-normal
        :return:
        """
        self.email_settings['subject'] = message

        time_string = self.format_time_message()
        self.email_settings['body'] = self.email_settings['subject'] + \
            '\n' + time_string + '\n'

        self.email_settings['logger'] = self.app_base.logger
        result = cp_send_email(self.email_settings)

        if alarm:
            self.app_base.logger.warning(message)
            self.app_base.logger.warning(time_string)
        else:
            self.app_base.logger.info(message)
            self.app_base.logger.info(time_string)
        return

    @staticmethod
    def format_time_message(now=None):
        """
        Produce a string such as "2016-04-20 10:54:23 Mountain Time"

        :param now: optional time ot use
        :return:
        """
        if now is None:
            now = time.time()

        return "  at time: {}".format(
            time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(now)))

    def power_is_lost(self, value):
        """
        Given current state, form the string
        :param value:
        :return:
        """
        return bool(value == self.state_in_alarm)

    def prep_email_settings(self):
        """

        :return:
        """
        # Required keys
        # ['smtp_tls]   = T/F to use TLS, defaults to True
        # ['smtp_url']  = URL, such as 'smtp.gmail.com'
        # ['smtp_port'] = TCP port like 587 - be careful, as some servers
        #                 have more than one, with the number defining the
        #                 security demanded.
        # ['username']  = your smtp user name (often your email acct address)
        # ['password']  = your smtp acct password
        # ['email_to']  = the target email address, as str or list
        # ['subject']   = the email subject

        # Optional keys
        # ['email_from'] = the from address - any smtp server will ignore,
        #                  and force this to be your user/acct email address;
        #                  def = ['username']
        # ['body']       = the email body; def = ['subject']

        # we allow KeyError is any of these are missing
        self.email_settings['smtp_tls'] = True
        self.email_settings['smtp_url'] = \
            self.app_base.settings['power_loss']['smtp_url']
        self.email_settings['smtp_port'] = \
            self.app_base.settings['power_loss']['smtp_port']
        self.email_settings['username'] = \
            self.app_base.settings['power_loss']['username']
        self.email_settings['password'] = \
            self.app_base.settings['power_loss']['password']

        email_to = self.app_base.settings['power_loss']['email_to']
        self.app_base.logger.debug("email_to:typ:{} {}".format(
            type(email_to), email_to))

        if isinstance(email_to, str):
            # if already string, check if like '["add1@c.com","add2@d.com"]
            email_to = email_to.strip()
            if email_to[0] in ("[", "("):
                email_to = list(eval(email_to))
                self.app_base.logger.debug("lister:typ:{} {}".format(
                    type(email_to), email_to))
            else:
                email_to = [email_to]
                self.app_base.logger.debug("elslie:typ:{} {}".format(
                    type(email_to), email_to))

        self.email_settings['email_to'] = email_to

        return

