"""
This app will create a file and then upload it to an FTP server.
The file will be deleted when the app is stopped.
"""

import sys
import argparse
from ftplib import FTP
import os
import cs


APP_NAME = "ftp_client"
TEMP_FILE = '/var/tmp/my_file.txt'

# A USB Storage device will be mounted at /var/media
# if it is plugged into the USB port of the router.
# Note: Not all USB devices are compatible.
TEMP_FILE_USB = '/var/media/my_file.txt'


def start_router_app():
    # Create a temporary file to upload to an FTP server
    try:
        f = open(TEMP_FILE, 'w')
        f.write('This is a test!!')
        f.write('This is another test!!')
        f.close()
    except OSError as msg:
        cs.CSClient().log(APP_NAME, 'Failed to open file: {}. error: {}'.format(TEMP_FILE, msg))

    try:
        # Connect to an FTP test server
        ftp = FTP('speedtest.tele2.net')

        # This can be used for ftp debug logs.
        # The required argument level means:
        # 0: no debugging output (default)
        # 1: print commands and responses but not body text etc.
        # 2: also print raw lines read and sent before stripping CR/LF'''
        # ftp.set_debuglevel(0)

        # Login to the server
        reply = ftp.login('anonymous', 'anonymous')
        cs.CSClient().log(APP_NAME, 'FTP login reply: {}'.format(reply))

        # Change to the proper directory for upload
        ftp.cwd('/upload/')

        # Open the file and upload it to the server
        fh = open(TEMP_FILE, 'rb')
        reply = ftp.storlines('STOR a.txt', fh)
        cs.CSClient().log(APP_NAME, 'FTP STOR reply: {}'.format(reply))

    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Something went wrong in start_router_app()! exception: {}'.format(e))
        raise

    finally:
        if ftp:
            ftp.quit()

        if fh:
            fh.close()
    return


def stop_router_app():
    # delete the temporary file if it exists
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
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
