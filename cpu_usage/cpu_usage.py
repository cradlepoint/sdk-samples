try:
    import cs
    import sys
    import traceback
    import argparse

    import os
    import time

    from app_logging import AppLogger

except Exception as ex:
    # Output DEBUG logs indicating what import failed. Use the logging in the
    # CSClient since app_logging may not be loaded.
    cs.CSClient().log('app_template.py', 'Import failure: {}'.format(ex))
    cs.CSClient().log('app_template.py', 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)

log = AppLogger()


def start_app():
    """ Add functionality to execute when the app is started. """
    try:
        log.info('start_app()')

        # Calling the function to write and log the cpu usage.
        get_usage()

    except Exception as e:
        log.error('Exception during start_app()! exception: {}'.format(e))
        raise


def stop_app():
    """ Add functionality to execute when the app is stopped. """
    try:
        log.info('stop_app()')

    except Exception as e:
        log.error('Exception during stop_app()! exception: {}'.format(e))
        raise


def action(command):
    """ This function will take action based on the command parameter. """
    try:
        # Log the action for the app.
        log.info('action({})'.format(command))

        if command == 'start':
            # Call the start function when the app is started.
            start_app()

        elif command == 'stop':
            # Call the stop function when the app is stopped.
            stop_app()

    except Exception as e:
        log.error('Exception during {}! exception: {}'.format(command, e))
        raise


def get_usage():

    while True:
        mount_status = cs.CSClient().get('/status/usb/connection/state')
        usb_status = cs.CSClient().get('/status/usb/mass/state')
        system_id = cs.CSClient().get('/config/system/system_id')
        memory = cs.CSClient().get('/status/system/memory')
        load_avg = cs.CSClient().get('/status/system/load_avg')
        cpu = cs.CSClient().get('/status/system/cpu')

        csv_data = (
            str(system_id['data']) + ',' +
            str(time.asctime()) + ',' +
            str(('{:.0f}'.format(
                memory['data']['memavailable']
                / float(1 << 20))+" MB")) + ',' +
            str(('{:.0f}'.format(
                memory['data']['memfree']
                / float(1 << 20))+" MB")) + ',' +
            str(('{:.0f}'.format(
                memory['data']['memtotal']
                / float(1 << 20))+" MB")) + ',' +
            str(load_avg['data']['15min']) + ',' +
            str(load_avg['data']['1min']) + ',' +
            str(load_avg['data']['5min']) + ',' +
            str(round(float(cpu['data']['nice']) +
                      float(cpu['data']['system']) +
                      float(cpu['data']['user']) *
                      float(100))) + '%\n')

        log_data = (
            'Memory Available: ' + str(('{:,.0f}'.format(
                memory['data']['memavailable'] / float(1 << 20))+" MB,")) +
            ' Memory Free: ' + str(('{:,.0f}'.format(
                memory['data']['memfree'] / float(1 << 20))+" MB,")) +
            ' Memory Total: ' + str(('{:,.0f}'.format(
                memory['data']['memtotal'] / float(1 << 20))+" MB,")) +
            ' CPU Usage: ' +
            str(round(float(cpu['data']['nice']) +
                      float(cpu['data']['system']) +
                      float(cpu['data']['user']) *
                      float(100))) + '%\n')

        if mount_status['data'] == 'mounted' and usb_status['data'] == 'plugged':
            try:
                os.chdir('/var/media/')

                if not os.path.isfile('/var/media/usage_info.csv'):

                    with open('usage_info.csv', 'w') as f:
                        f.seek(0, 0)
                        f.write(
                            'Hostname, Time, Memory Available, Memory Free, Memory Total,'
                            'Load 15 Min, Load 1 Min, Load 5 Min, CPU Usage\n')
                        f.close()

                        log.info('Created new usage_info.csv')
                        continue
                else:
                    with open('usage_info.csv', 'a') as f:

                        f.write(csv_data)
                        f.close()

                        log.info(log_data)

                        log.info('USB Mount Status: ' + str(usb_status['data'].title()))

            except Exception as e:
                log.error('Exception during save! exception: {}'.format(e))

            time.sleep(15)

        else:
            log.info('USB Mount Status: ' + str(usb_status['data'].title()))

            log.info(log_data)

            time.sleep(15)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        log.info('Failed to run command: {}'.format(opt))
        exit()

    action(opt)

    log.info('App is exiting')
