"""
This app will create a file and then upload it to an FTP server.
The file will be deleted when the app is stopped.
"""

from csclient import EventingCSClient
from ftplib import FTP

cp = EventingCSClient("ftp_client")
TEMP_FILE = "my_file.txt"

cp.log("ftp_client send_ftp_file()...")
# Create a temporary file to upload to an FTP server
try:
    f = open(TEMP_FILE, "w")
    f.write("This is a test!!")
    f.write("This is another test!!")
    f.close()
except OSError as msg:
    cp.log("Failed to open file: {}. error: {}".format(TEMP_FILE, msg))

try:
    # Connect to an FTP test server
    ftp = FTP("speedtest.tele2.net")

    # Login to the server
    reply = ftp.login("anonymous", "anonymous")
    cp.log("FTP login reply: {}".format(reply))

    # Change to the proper directory for upload
    ftp.cwd("/upload/")

    # Open the file and upload it to the server
    fh = open(TEMP_FILE, "rb")
    reply = ftp.storlines("STOR a.txt", fh)
    cp.log("FTP STOR reply: {}".format(reply))

except Exception as e:
    cp.log("Exception occurred! exception: {}".format(e))
    raise

finally:
    if fh:
        fh.close()
