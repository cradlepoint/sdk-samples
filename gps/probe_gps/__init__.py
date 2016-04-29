import time
from cp_lib.app_base import CradlepointAppBase
from gps.probe_gps.probe_gps import probe_gps

SLEEP_DELAY = 60.0


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "network.tcp_echo"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):
        self.logger.debug("__init__ chaining to probe_gps()")

        # if user included a different timeout in settings
        try:
            delay = float(self.settings['probe_gps']['delay'])

        except (KeyError, ValueError):
            delay = SLEEP_DELAY

        # we do this wrap to dump any Python exception traceback out to Syslog
        result = -1
        while True:
            try:
                result = probe_gps(self)
            except:
                self.logger.exception("CradlepointAppBase failed")
                raise

            self.logger.debug("sleep to delay for {} seconds".format(delay))
            time.sleep(delay)

        return result
