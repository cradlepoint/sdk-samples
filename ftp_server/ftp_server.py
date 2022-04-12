"""
This app will start an FTP server. This is done by using
pyftplib and also asynchat.py and asyncore.py. For detail
information about pyftplib, see https://pythonhosted.org/pyftpdlib/.
"""

import os
import sys
from csclient import EventingCSClient

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


cp = EventingCSClient("ftp_server")

# This requires a USB compatible storage device plugged into
# the router. It will mount to /var/media.
if sys.platform == "linux2":
    # FTP_DIR = '/var/media'
    FTP_DIR = "./"
else:
    FTP_DIR = os.getcwd()

cp.log("start_ftp_server()...")
try:
    authorizer = DummyAuthorizer()
    # Define a new user having full r/w permissions and a read-only
    # anonymous user
    authorizer.add_user("user", "12345", FTP_DIR, perm="elradfmwM")
    authorizer.add_anonymous(FTP_DIR)

    # Instantiate FTP handler class
    handler = FTPHandler
    handler.authorizer = authorizer

    # Define a customized banner (string returned when client connects)
    handler.banner = "pyftpdlib based ftpd ready."

    # Instantiate FTP server class and listen on 0.0.0.0:2121.
    # Application can only use ports higher that 1024 and the port
    # will need to be allowed in the router firewall
    address = ("", 2121)
    server = FTPServer(address, handler)

    # set a limit for connections
    server.max_cons = 256
    server.max_cons_per_ip = 5

    # start ftp server
    cp.log("Starting FTP server...")
    server.serve_forever()
    # This will run the server in another thread
    # t = Thread(target=server.serve_forever())
    # t.start()

except Exception as e:
    cp.log("Exception occurred! exception: {}".format(e))
