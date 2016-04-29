"""
Issue a ping, via Router API control/ping
"""
from cp_lib.app_base import CradlepointAppBase
from cp_lib.cs_ping import cs_ping


# this name "run_router_app" is not important, reserved, or demanded
# - but must match below in __main__ and also in __init__.py
def run_router_app(app_base, ping_ip=None):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param str ping_ip: the IP to ping
    :return:
    """
    if ping_ip is None:
        # then try settings.ini
        if "ping" in app_base.settings:
            ping_ip = app_base.settings["ping"].get("ping_ip", '')
    # else, just assume passed in value is best

    result = cs_ping(app_base, ping_ip)
    return result


if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/send_ping")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
