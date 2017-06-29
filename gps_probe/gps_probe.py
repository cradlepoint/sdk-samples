"""
Probe the GPS hardware and log the results.

Walk through the router API 'status' and 'config' trees, returning
a list of text strings showing if any GPS source exists, if there is
existing last-seen data, and so on.

"""
import argparse
import json
import sys
import time
import cs

APP_NAME = 'gps_probe'


def probe_gps():
    """
    Probe for GPS data and log the results. 
    """

    message = "Probing GPS HW - {}".format(time.strftime("%Y-%m-%d %H:%M:%S",
                                                         time.localtime()))
    cs.CSClient().log(APP_NAME, message)
    report_lines = [message]

    # check the type of Router we are running on
    try:
        result = json.loads(cs.CSClient().get("status/product_info/product_name"))
        message = "Router Model:{}".format(result)
        report_lines.append(message)
        cs.CSClient().log(APP_NAME, message)
    except KeyError:
        cs.CSClient().log(APP_NAME, "App Base is missing 'product_info'")

    result = json.loads(cs.CSClient().get("config/system/gps"))
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
        cs.CSClient().log(APP_NAME, message)

        if result.get("enable_gps_keepalive", False):
            message = "GPS Keepalive is Enabled"
        else:
            message = "GPS Keepalive is NOT Enabled"
        report_lines.append(message)
        cs.CSClient().log(APP_NAME, message)

    if gps_enabled:
        # only do this if enabled!
        result = json.loads(cs.CSClient().get("status/wan/devices"))

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
                        message = "Modem named \"{0}\" lacks GPS data".format(key)

                    report_lines.append(message)
                    cs.CSClient().log(APP_NAME, message)
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
            message = "Router has {0} modems claiming GPS data".format(len(gps_sources))

        report_lines.append(message)
        cs.CSClient().log(APP_NAME, message)

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
            cs.CSClient().log(APP_NAME, message)
            report_lines.append(message)

            json_value = json.dumps(value, ensure_ascii=True, indent=4)
            json_lines = json_value.split(sep='\n')
            for line in json_lines:
                cs.CSClient().log(APP_NAME, line)
                # Save all the gps data in report_lines. This can
                # be saved to a file if needed.
                report_lines.append(line)

    return 0


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            probe_gps()

        elif command == 'stop':
            # Nothing on stop
            pass

    except:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}!'.format(APP_NAME, command))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
