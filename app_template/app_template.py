"""
A Blank app template as an example
"""
APP_NAME = "app_template"

try:
    import sys
    import traceback
    import argparse
    import cs
except Exception as ex:
    cs.CSClient().log(APP_NAME, 'Import failure: {}'.format(ex))
    cs.CSClient().log(APP_NAME, 'Traceback: {}'.format(traceback.format_exc()))
    sys.exit(-1)


def start_router_app():
    try:
        cs.CSClient().log(APP_NAME, 'start_router_app()')

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

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! exception: {}'.format(APP_NAME, command, ex))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    cs.CSClient().log(APP_NAME, 'args: {})'.format(args))
    opt = args.opt.strip()
    if opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(opt))
        exit()

    action(opt)
