'''
This application will ping an address and log the results
'''
import sys
import argparse
import time
import json
import cs

APP_NAME = 'ping'


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            ping_data = {
                'host': 'www.google.com',  # Can also be an IP address
                'size': 64
            }

            result = cs.CSClient().put('/control/ping/start', ping_data)
            cs.CSClient().log(APP_NAME, 'Start ping: {}'.format(result))

            done = False
            ping_results = []
            while not done:
                time.sleep(1)
                ping_data = json.loads(cs.CSClient().get('/control/ping'))
                # Need to collect the results as it is cleared when read.
                result = ping_data['result']

                if result != '':
                    lines = result.split('\n')
                    ping_results.extend(lines)

                status = ping_data['status']

                if status == 'done' or status == 'error':
                    done = True

            # Now that the ping is done, log the results
            for line in ping_results:
                cs.CSClient().log(APP_NAME, 'Ping Results: {}'.format(line))

        elif command == 'stop':
            # Nothing on stop
            pass
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
