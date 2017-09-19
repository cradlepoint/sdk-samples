"""
This app will start an FTP server. This is done by using
pyftplib and also asynchat.py and asyncore.py. For detail
information about pyftplib, see https://pythonhosted.org/pyftpdlib/.
"""

import sys
import argparse
import cs
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from threading import Thread

APP_NAME = "ftp_server"

# This requires a USB compatible storage device plugged into
# the router. It will mount to /var/media.
FTP_DIR = '/var/media'


def start_ftp_server():
    try:
        authorizer = DummyAuthorizer()
        # Define a new user having full r/w permissions and a read-only
        # anonymous user
        authorizer.add_user('user', '12345', FTP_DIR, perm='elradfmwM')
        authorizer.add_anonymous(FTP_DIR)

        # Instantiate FTP handler class
        handler = FTPHandler
        handler.authorizer = authorizer

        # Define a customized banner (string returned when client connects)
        handler.banner = "pyftpdlib based ftpd ready."

        # Instantiate FTP server class and listen on 0.0.0.0:2121.
        # Application can only use ports higher that 1024 and the port
        # will need to be allowed in the router firewall
        address = ('', 2121)
        server = FTPServer(address, handler)

        # set a limit for connections
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # start ftp server
        cs.CSClient().log(APP_NAME, 'Starting FTP server...')
        server.serve_forever()
        t = Thread(target=server.serve_forever())
        t.start()

    except Exception as e:
        cs.CSClient().log(APP_NAME, 'Something went wrong in start_ftp_server()! exception: {}'.format(e))
        raise

    return


def stop_router_app():
    """
        Perform any cleanup or other actions.
    """
    return


def action(command):
    try:
        # Log the action for the app.
        cs.CSClient().log(APP_NAME, 'action({})'.format(command))

        if command == 'start':
            # Call the function to start the app.
            start_ftp_server()

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
