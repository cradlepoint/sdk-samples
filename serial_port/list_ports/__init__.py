from cp_lib.app_base import CradlepointAppBase
from serial_port.list_ports.list_ports import run_router_app


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "simple.hello_world_app"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):
        try:
            result = run_router_app(self)
        except:
            self.logger.exception("CradlepointAppBase failed")
            raise

        return result
