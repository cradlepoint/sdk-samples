try:
    import cs
    import sys
    import traceback
    import argparse
    import os
    import time
    import json
    import zlib

    from app_logging import AppLogger

except Exception as ex:
    cs.CSClient().log('cpu_usage.py', 'Import failure: {}'.format(ex))
    cs.CSClient().log('cpu_usage.py',
                      'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)

log = AppLogger()


def start_app():
    """ Add functionality to execute when the app is started. """
    try:
        log.info('start_app()')

        create_folder()
        create_csv()
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


def create_folder():
    """ Try and create folder in /var/media/. """
    try:
        if not os.path.exists('/var/media/usage_data/'):
            try:
                os.makedirs('/var/media/usage_data/')

            except Exception as e:
                log.error('Exception creating /var/media/usage_data/!'
                          'Is a usb stick attached \
                           and formatted to fat32? exception: {}'.format(e))
    except Exception as e:
        log.error('Exception creating /var/media/usage_data/!'
                  'Is a usb stick attached \
                   and formatted to fat32? exception: {}'.format(e))


def create_csv():
    """ Write headers """
    try:
        os.chdir('/var/media/usage_data/')

        # set to write mode so it overwrites on start of the application.
        with open('usage_info.csv', 'w') as f:
            f.seek(0, 0)
            f.write(
                'Hostname, Time, Memory Available, Memory Free, Memory Total,'
                'Load 15 Min, Load 1 Min, Load 5 Min, CPU Usage\n')

    except Exception as e:
        log.error(
            'Exception creating /var/media/usage_data/usage_info.csv,\
             exception: {}'.format(e))
        create_folder()
        create_csv()


def get_usage():
    while True:
        usb_status = cs.CSClient().get('/status/usb/connection/state')
        system_id = cs.CSClient().get('/config/system/system_id')
        memory = cs.CSClient().get('/status/system/memory')
        load_avg = cs.CSClient().get('/status/system/load_avg')
        cpu = cs.CSClient().get('/status/system/cpu')

        if 'mounted' in usb_status['data']:
            try:
                os.chdir('/var/media/usage_data/')

                with open('usage_info.csv', 'a') as f:
                    # write row to csv.
                    f.write(str(system_id['data']) + ',' +
                            str(time.asctime()) + ',' +
                            str(('{:,.0f}'.format(
                                memory['data']['memavailable']
                                / float(1 << 20))+" MB")) + ',' +
                            str(('{:,.0f}'.format(
                                memory['data']['memfree']
                                / float(1 << 20))+" MB")) + ',' +
                            str(('{:,.0f}'.format(
                                memory['data']['memtotal']
                                / float(1 << 20))+" MB")) + ',' +
                            str(load_avg['data']['15min']) + ',' +
                            str(load_avg['data']['1min']) + ',' +
                            str(load_avg['data']['5min']) + ',' +
                            str(round(float(cpu['data']['nice']) +
                                      float(cpu['data']['system']) +
                                      float(cpu['data']['user']) *
                                      float(100))) + '%\n')

                    log.info('Saved CPU and Memory usage info to CSV.\
                              Sleeping for 15 seconds.')

            except Exception as e:
                log.error('Exception during save! exception: {}'.format(e))

            time.sleep(15)

        else:
            log.info('USB Mount Status: ' + str(usb_status['data']) +
                     '. Is your usb drive plugged in and formatted to fat32?')

            # print results to info log.
            log.info('Mem Available :' + str(('{:,.0f}'.format(
                memory['data']['memavailable']
                / float(1 << 20))+" MB")) + ',' +
                'Mem Free :' + str(('{:,.0f}'.format(
                    memory['data']['memfree'] /
                    float(1 << 20))+" MB")) + ',' +
                'Mem Total :' + str(('{:,.0f}'.format(
                    memory['data']['memtotal']
                    / float(1 << 20))+" MB")) + ',' +
                'CPU Load :' + str(
                round(float(cpu['data']['nice']) +
                      float(cpu['data']['system']) +
                      float(cpu['data']['user']) *
                      float(100))) + '%\n')

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
