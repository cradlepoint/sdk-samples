from cp_lib.app_base import CradlepointAppBase
from network.tcp_echo.tcp_echo import tcp_echo_server


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "network.tcp_echo"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):

        self.logger.debug("__init__ chaining to tcp_echo_server()")

        # we do this wrap to dump any Python exception traceback out to Syslog
        try:
            result = tcp_echo_server(self)
        except:
            self.logger.exception("CradlepointAppBase failed")
            raise

        return result
