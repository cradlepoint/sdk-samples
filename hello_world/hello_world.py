'''
Outputs a 'Hello World!' log every 10 seconds.
'''

import argparse
import time
import cs
import subprocess

APP_NAME = 'hello_world'


# This function will take action based on the command parameter.
def action(command):
    cs.CSClient().log(APP_NAME, 'action({})'.format(command))

    if command == 'start':
        while True:
            cs.CSClient().log(APP_NAME, 'Hello World!')
            time.sleep(10)

    elif command == 'stop':
        pass


# The main entry point for hello_world.py This will be executed when the
# application is started or stopped as defined in the start.sh and stop.sh
# scripts. It expects either a 'start' or 'stop' argument.
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
