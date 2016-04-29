"""
Probe the GPS hardware, return a report as list of text, and actual ASCII file
"""
import json
import sys
import time

from cp_lib.app_base import CradlepointAppBase
# from cp_lib.hw_status import am_running_on_router


def probe_gps(app_base, save_file=None):
    """
    The main GPS task.

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param str save_file: If a name, then save as text file
    :return int:
    """

    message = "Probing GPS HW - {}".format(time.strftime("%Y-%m-%d %H:%M:%S",
                                                         time.localtime()))
    app_base.logger.info(message)
    report_lines = [message]

    if "probe_gps" in app_base.settings:
        if "filename" in app_base.settings["probe_gps"]:
            save_file = app_base.settings["probe_gps"]["filename"]

    # check the type of Router we are running on
    try:
        result = app_base.settings["product_info"]["product_name"]
        message = "Router Model:{}".format(result)
        report_lines.append(message)
        app_base.logger.info(message)
    except KeyError:
        app_base.logger.error("App Base is missing 'product_info'")

    result = app_base.cs_client.get("config/system/gps")
    if not isinstance(result, dict):
        # some error?
        gps_enabled = False

    else:
        # FW 6.1 example of get("config/system/gps")
        # {'connections': [], 'taip_vehicle_id': '0000', 'enabled': True,
        #  'enable_gps_keepalive': True, 'enable_gps_led': True,
        #  'debug': {'log_nmea_to_fs': False, 'flags': 0},
        #            'pwd_enabled': False}
        gps_enabled = result.get("enabled", False)
        if gps_enabled:
            message = "GPS Function is Enabled"
        else:
            message = "GPS Function is NOT Enabled"
        report_lines.append(message)
        app_base.logger.info(message)

        if result.get("enable_gps_keepalive", False):
            message = "GPS Keepalive is Enabled"
        else:
            message = "GPS Keepalive is NOT Enabled"
        report_lines.append(message)
        app_base.logger.info(message)

    if gps_enabled:
        # only do this if enabled!
        app_base.cs_client.show_rsp = False
        result = app_base.cs_client.get("status/wan/devices")
        app_base.cs_client.show_rsp = True
        # logger.debug("Type(result):{}".format(type(result)))
        # logger.debug("Result:{}".format(result))

        # if not am_running_on_router():
        if sys.platform == "win32":
            file_name = ".dump.json"
            app_base.logger.debug("Save file:{}".format(file_name))
            file_han = open(file_name, "w")
            file_han.write(json.dumps(result, ensure_ascii=True, indent=4))
            file_han.close()

        gps_sources = []
        for key in result:
            try:
                if result[key]["info"]["supports_gps"]:
                    # logger.debug("Key:{} supports GPS".format(key))
                    value = result[key]["status"]["gps"]
                    if value is not None and len(value) > 0:
                        # for example, active w/GPS will be like
                        message = "Modem named \"{0}\" has GPS data".format(
                            key)
                        gps_sources.append(key)
                    else:
                        # for example, inactive w/o GPS will be only {}
                        message = "Modem named \"{0}\" lacks GPS data".format(
                            key)
                    report_lines.append(message)
                    app_base.logger.info(message)
            except KeyError:
                # for example, the WAN device 'ethernet-wan' will LACK
                # the key ["info"]["supports_gps"]
                # logger.debug("Key:{} does NOT support GPS".format(key))
                pass

        if len(gps_sources) == 0:
            message = "Router has NO modems claiming to have GPS data"
        elif len(gps_sources) == 1:
            message = "Router has 1 modem claiming to have GPS data"
        else:
            message = "Router has {0} modems claiming GPS data".format(
                len(gps_sources))
        report_lines.append(message)
        app_base.logger.info(message)

        # {'fix': {
        #     'age': 57.38595999999962,
        #     'lock': True,
        #     'longitude': {'second': 5.596799850463867, 'minute': 20,
        #                   'degree': -93},
        #     'time': 204521,
        #     'satellites': 6,
        #     'latitude': {'second': 49.17959976196289, 'minute': 0,
        #                  'degree': 45}
        # },
        # 'nmea': {
        #     'GPGGA': '$GPGGA,204521.0,4500.819660,N,09320.093314,W,1,06,
        #               0.8,286.2,M,-33.0,M,,*66\r\n',
        #     'GPRMC': '$GPRMC,204521.0,A,4500.819660,N,09320.093314,W,0.0,
        #               264.6,140316,0.0,E,A*15\r\n',
        #     'GPVTG': '$GPVTG,264.6,T,264.6,M,0.0,N,0.0,K,A*23\r\n'}
        # }

        if len(gps_sources) > 0:
            value = result[gps_sources[0]]["status"]["gps"]
            message = "GPS data follows"
            app_base.logger.debug(message)
            report_lines.append(message)

            json_value = json.dumps(value, ensure_ascii=True, indent=4)
            json_lines = json_value.split(sep='\n')
            for line in json_lines:
                app_base.logger.debug(line)
                report_lines.append(line)

        if save_file is not None:
            # if am_running_on_router():
            if sys.platform != "win32":
                pass
                # app_base.logger.error(
                #     Skip save to file - am running on router.")
            else:
                app_base.logger.debug("Save file:{}".format(save_file))
                file_han = open(save_file, "w")
                for line in report_lines:
                    file_han.write(line + '\n')
                file_han.close()

    return 0


if __name__ == "__main__":
    import logging

    # get this started, else we don't see anything for a while
    logging.basicConfig(level=logging.DEBUG)

    my_app = CradlepointAppBase("gps/probe_gps")

    _result = probe_gps(my_app)

    my_app.logger.info("Exiting, status code is {}".format(_result))

    sys.exit(_result)
