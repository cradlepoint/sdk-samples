from cp_lib.app_base import CradlepointAppBase
from demo.gps_gate.gps_gate import run_router_app


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "network.tcp_echo"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):

        self.logger.debug("__init__ chaining to run_router_app()")

        # we do this wrap to dump any Python exception traceback out to Syslog
        try:
            result = run_router_app(self)
        except:
            self.logger.exception("CradlepointAppBase failed")
            raise

        return result
