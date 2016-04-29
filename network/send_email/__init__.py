from cp_lib.app_base import CradlepointAppBase
from network.send_email.send_email import send_one_email


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "network.tcp_echo"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):
        self.logger.debug("__init__ chaining to send_one_email()")

        # we do this wrap to dump any Python exception traceback out to Syslog
        try:
            result = send_one_email(self)
        except:
            self.logger.exception("CradlepointAppBase failed")
            raise
