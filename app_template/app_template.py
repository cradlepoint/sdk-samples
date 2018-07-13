"""
An app template that can be used to create a new application.
This template covers several aspect of an application that
my not be needed in every case. It is meant as a guide and not
a must.
"""

# A try/except is wrapped around the imports to catch an
# attempt to import a file or library that does not exist
# in NCOS. Very useful during app development if one is
# adding python libraries.
try:
    import cs
    import sys
    import traceback
    import argparse

    from app_logging import AppLogger

except Exception as ex:
    # Output DEBUG logs indicating what import failed. Use the logging in the
    # CSClient since app_logging may not be loaded.
    cs.CSClient().log('app_template.py', 'Import failure: {}'.format(ex))
    cs.CSClient().log('app_template.py', 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()


# Add functionality to execute when the app is started
def start_app():
    try:
        log.debug('start_app()')

    except Exception as e:
        log.error('Exception during start_app()! exception: {}'.format(e))
        raise


# Add functionality to execute when the app is stopped
def stop_app():
    try:
        log.debug('stop_app()')

    except Exception as e:
        log.error('Exception during stop_app()! exception: {}'.format(e))
        raise


# This function will take action based on the command parameter.
def action(command):
    try:
        # Log the action for the app.
        log.debug('action({})'.format(command))

        if command == 'start':
            # Call the start function when the app is started.
            start_app()

        elif command == 'stop':
            # Call the stop function when the app is stopped.
            stop_app()

    except Exception as e:
        log.error('Exception during {}! exception: {}'.format(command, e))
        raise


# The main entry point for app_template.py This will be executed when the
# application is started or stopped as defined in the start.sh and stop.sh
# scripts. It expects either a 'start' or 'stop' argument.
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        log.debug('Failed to run command: {}'.format(opt))
        exit()

    action(opt)

    log.debug('App is exiting')
