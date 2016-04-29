from cp_lib.app_base import CradlepointAppBase
from demo.hoops_counter.hoops_counter import run_router_app


class RouterApp(CradlepointAppBase):

    def __init__(self, app_name):
        """
        :param str app_name: the file name, such as "simple.hello_world_app"
        :return:
        """
        CradlepointAppBase.__init__(self, app_name)
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
