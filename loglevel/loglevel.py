'''
This reference application will change the router logging level to 'info' when
the app is started and then to 'debug' when it is stopped (i.e. unloaded or purged).
'''
import argparse
import cs

APP_NAME = 'loglevel'


def action(command):
    try:
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        # Read the logging level
        ret_value = cs.CSClient().get('/config/system/logging/level')

        # Output a syslog for the current logging level
        cs.CSClient().log(APP_NAME, 'Current Logging level = {}'.format(ret_value))
        ret_value = ''

        if command == 'start':
            # Set the logging level to info when the app is started.
            ret_value = cs.CSClient().put('/config/system/logging', {'level': 'info'})
        elif command == 'stop':
            # Set the logging level to debug when the app is stopped.
            ret_value = cs.CSClient().put('/config/system/logging', {'level': 'debug'})

        # Output a syslog for the new current logging level
        cs.CSClient().log(APP_NAME, 'New Logging level = {}'.format(ret_value))
    except:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}!'.format(APP_NAME, command))
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
