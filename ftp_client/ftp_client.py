"""
This app will create a file and then upload it to an FTP server.
The file will be deleted when the app is stopped.
"""

import cs
from ftplib import FTP


APP_NAME = "ftp_client"
TEMP_FILE = 'my_file.txt'


def send_ftp_file():
    cs.CSClient().log(APP_NAME, 'ftp_client send_ftp_file()...')
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
        cs.CSClient().log(APP_NAME, 'Exception occurred! exception: {}'.format(e))
        raise

    finally:
        if fh:
            fh.close()


if __name__ == "__main__":
    cs.CSClient().log(APP_NAME, 'ftp_client main...')
    send_ftp_file()
