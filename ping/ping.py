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
                ping_data = cs.CSClient().get('/control/ping').get('data')
                # Need to collect the results as it is cleared when read.
                result = ping_data.get('result')

                if result != '':
                    lines = result.split('\n')
                    ping_results.extend(lines)

                status = ping_data.get('status')

                if status == 'done' or status == 'error':
                    done = True

            # Now that the ping is done, log the results
            for line in ping_results:
                cs.CSClient().log(APP_NAME, 'Ping Results: {}'.format(line))

        elif command == 'stop':
            # Nothing on stop
            pass

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! ex: {}'.format(APP_NAME, command, ex))
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
