from cp_lib.app_base import CradlepointAppBase
from serial_port.list_ports.list_ports import do_list_ports


class RouterApp(CradlepointAppBase):

    def __init__(self, app_main):
        """
        :param str app_main: the file name, such as "simple.hello_world_app"
        :return:
        """
        CradlepointAppBase.__init__(self, app_main)
        return

    def run(self):
        return do_list_ports(self.logger, self.settings)
