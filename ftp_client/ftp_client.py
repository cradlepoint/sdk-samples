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

    except:
        e = sys.exc_info()[0]
        cs.CSClient().log(APP_NAME, 'Problem with {} on {}! exception: {}'.format(APP_NAME, command, e))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('opt')
    args = parser.parse_args()

    # The start.sh and stop.sh should call this script with a start or stop argument
    if args.opt not in ['start', 'stop']:
        cs.CSClient().log(APP_NAME, 'Failed to run command: {}'.format(args.opt))
        exit()

    action(args.opt)
