'''
This application will send an alert to the ECM when the
application is started and stopped. The alert must be
setup in the ECM. This is a Router Apps, Custom Alert.

The CSClient function to send an alert is:

  cs.CSClient().alert(name, value)
    :param str name - The 'Alert:' field for the alert in ECM.
    :param str value - The 'Message:' field for the alert in ECM.
'''

import sys
import argparse
import cs

APP_NAME = 'send_alert'


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            cs.CSClient().log(APP_NAME, 'Sent ECM alert that app was started.')
            cs.CSClient().alert(APP_NAME, 'Application has been started')

        elif command == 'stop':
            cs.CSClient().log(APP_NAME, 'Sent ECM alert that app was stopped.')
            cs.CSClient().alert(APP_NAME, 'Application has been stopped')
    except:
        e = sys.exc_info()[0]
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! exception: {}'.format(APP_NAME, command, e))
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
