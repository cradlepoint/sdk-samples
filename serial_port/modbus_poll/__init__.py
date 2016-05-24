from cp_lib.app_base import CradlepointAppBase
from serial_port.modbus_poll.modbus_poll import run_router_app


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "serial.serial_echo"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):
        self.logger.debug("__init__ chaining to run_main()")

        # we do this wrap to dump any Python exception traceback out to Syslog
        try:
            result = run_router_app(self)
        except:
            self.logger.exception("CradlepointAppBase failed")
            raise

        return result
