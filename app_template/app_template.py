"""
A Blank app template as an example
"""
try:
    import sys
    import traceback
    import argparse
    import cs
except Exception as ex:
    cs.CSClient().log("app_template.py", 'Import failure: {}'.format(ex))
    cs.CSClient().log("app_template.py", 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)

APP_NAME = "app_template"


def start_router_app():
    try:
        cs.CSClient().log(APP_NAME, 'start_router_app()')
        gps_clients = [{
            "distance_interval_meters": 0,
            "enabled": True,
            "interval": 10,
            "language": "nmea",
            "name": "test server",
            "nmea": {
                "include_id": True,
                "prepend_id": False,
                "provide_gga": True,
                "provide_rmc": True,
                "provide_vtg": True
            },
            "server": {
                "lan": True,
                "port": 12345,
                "wan": True
            },
            "stationary_distance_threshold_meters": 20,
            "stationary_movement_event_threshold_seconds": 0,
            "stationary_time_interval_seconds": 0,
            "taip": {
                "include_cr_lf_enabled": False,
                "provide_al": True,
                "provide_cp": True,
                "provide_id": True,
                "provide_ln": True,
                "provide_pv": True,
                "report_msg_checksum_enabled": True,
                "vehicle_id_reporting_enabled": True
            }
        }]
        response = cs.CSClient().put('/config/system/gps/connections', gps_clients)
    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Something went wrong in start_router_app()! exception: {}'.format(e))
        raise

    return


def stop_router_app():
    try:
        cs.CSClient().log(APP_NAME, 'stop_router_app()')

    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Something went wrong in stop_router_app()! exception: {}'.format(e))
        raise

    return


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            # Call the function to start the app.
            start_router_app()

        elif command == 'stop':
            # Call the function to start the app.
            stop_router_app()

    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! exception: {}'.format(APP_NAME, command, e))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    # The start.sh and stop.sh should call this script with a start or stop argument
    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
