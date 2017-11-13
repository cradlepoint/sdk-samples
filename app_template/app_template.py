"""
An app template as an example
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
    # Output logs indicating what import failed.
    cs.CSClient().log('app_template.py', 'Import failure: {}'.format(ex))
    cs.CSClient().log('app_template.py', 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)


# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()


def start_router_app():
    try:
        log.debug('start_router_app()')

    except Exception as e:
        log.error('Exception during start_router_app()! exception: {}'.format(e))
        raise


def stop_router_app():
    try:
        log.debug('stop_router_app()')

    except Exception as e:
        log.error('Exception during stop_router_app()! exception: {}'.format(e))
        raise


def action(command):
    try:
        # Log the action for the app.
        log.debug('action({})'.format(command))

        if command == 'start':
            # Call the function when the app is started.
            start_router_app()

        elif command == 'stop':
            # Call the function when the app is stopped.
            stop_router_app()

    except Exception as e:
        log.error('Exception during {}! exception: {}'.format(command, e))
        raise


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
