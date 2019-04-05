"""
NCOS communication module for SDK applications.

Copyright (c) 2018 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

This file contains confidential information of CradlePoint, Inc. and your use of
this file is subject to the CradlePoint Software License Agreement distributed with
this file. Unauthorized reproduction or distribution of this file is subject to civil and
criminal penalties.
"""

import json
import re
import socket
import sys


class SdkCSException(Exception):
    pass


CSCLIENT_NAME = 'SDK CSClient'


class CSClient(object):
    """
    The CSClient class is the NCOS SDK mechanism for communication between apps and the router tree/config store.
    Instances of this class communicate with the router using either an explicit socket or with http method calls.

    Apps running locally on the router use a socket on the router to send commands from the app to the router tree
    and to receive data (JSON) from the router tree.

    Apps running remotely use the requests library to send HTTP method calls to the router and to receive data from
    the router tree. This allows one to use an IDE to run and debug the application on a the computer. Although,
    there are limitations with respect to the device hardware access (i.e. serial, USB, etc.).
    """
    END_OF_HEADER = b"\r\n\r\n"
    STATUS_HEADER_RE = re.compile(b"status: \w*")
    CONTENT_LENGTH_HEADER_RE = re.compile(b"content-length: \w*")
    MAX_PACKET_SIZE = 8192
    RECV_TIMEOUT = 2.0

    _instances = {}

    @classmethod
    def is_initialized(cls):
        return cls in cls._instances

    def __new__(cls, *na, **kwna):
        """ Singleton factory (with subclassing support) """
        if not cls.is_initialized():
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, init=False):
        if not init:
            return

    def get(self, base, query='', tree=0):
        """
        Constructs and sends a get request to retrieve specified data from a device.

        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly queries the router tree to retrieve the
              specified data.
            - If the app running remotely from a computer it calls the HTTP GET method to retrieve the specified data.

        Args:
            base: String representing a path to a resource on a router tree,
                  (i.e. '/config/system/logging/level').
            query: Not required.
            tree: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}

        """
        if sys.platform == 'linux2':
            cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the get to the device.
            import requests
            device_ip, username, password = self._get_device_access_info()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.get(device_api, auth=self._get_auth(device_ip, username, password))

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def put(self, base, value='', query='', tree=0):
        """
        Constructs and sends a put request to update or add specified data to the device router tree.

        The behavior of this method is contextual:
            - If the app is installed on(and executed from) a device, it directly updates or adds the specified data to
              the router tree.
            - If the app running remotely from a computer it calls the HTTP PUT method to update or add the specified
              data.

        Args:
            base: String representing a path to a resource on a router tree,
                  (i.e. '/config/system/logging/level').
            value: Not required.
            query: Not required.
            tree: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}
        """
        value = json.dumps(value).replace(' ', '')
        if sys.platform == 'linux2':
            cmd = "put\n{}\n{}\n{}\n{}\n".format(base, query, tree, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the put to the device.
            import requests
            device_ip, username, password = self._get_device_access_info()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.put(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_auth(device_ip, username, password),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def alert(self, app_name='', value=''):
        """
        Constructs and sends a custom alert to NCM for the device. Apps calling this method must be running
        on the target device to send the alert. If invoked while running on a computer, then only a log is output.

        Args:
        app_name: String name of your application.
        value: String to displayed for the alert.

        Returns:
            Success: None
            Failure: An error
        """
        if sys.platform == 'linux2':
            cmd = "alert\n{}\n{}\n".format(app_name, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer and can't actually send the alert.
            print('Alert is only available when running the app in NCOS.')
            print('Alert Text: {}'.format(value))

    def log(self, name='', value=''):
        """
        Adds a DEBUG log to the device SYSLOG.
        Note: It is recommend that app_logging.py be used for logging which
              supports all logging levels.

        Args:
        name: String of the name of your application.
        value: String text for the log.

        Returns:
        None
        """
        if sys.platform == 'linux2':
            cmd = "log\n{}\n{}\n".format(name, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so just use print for the log.
            print('[{}]: {}'.format(name, value))

    def _get_auth(self, device_ip, username, password):
        # This is only needed when the app is running in a computer.
        # Returns the proper HTTP Auth for the global username and password.
        # Digest Auth is used for NCOS 6.4 and below while Basic Auth is
        # used for NCOS 6.5 and up.
        import requests
        from http import HTTPStatus

        use_basic = False
        device_api = 'http://{}/api/status/product_info'.format(device_ip)

        try:
            response = requests.get(device_api, auth=requests.auth.HTTPBasicAuth(username, password))
            if response.status_code == HTTPStatus.OK:
                use_basic = True

        except:
            use_basic = False

        if use_basic:
            return requests.auth.HTTPBasicAuth(username, password)
        else:
            return requests.auth.HTTPDigestAuth(username, password)

    @staticmethod
    def _get_device_access_info():
        # Should only be called when running in a computer. It will return the
        # dev_client_ip, dev_client_username, and dev_client_password as defined in
        # the sdk section of the sdk_settings.ini file.
        device_ip = ''
        device_username = ''
        device_password = ''

        if sys.platform != 'linux2':
            import os
            import configparser

            settings_file = os.path.join(os.path.dirname(os.getcwd()), 'sdk_settings.ini')
            config = configparser.ConfigParser()
            config.read(settings_file)

            # Keys in sdk_settings.ini
            sdk_key = 'sdk'
            ip_key = 'dev_client_ip'
            username_key = 'dev_client_username'
            password_key = 'dev_client_password'

            if sdk_key in config:
                if ip_key in config[sdk_key]:
                    device_ip = config[sdk_key][ip_key]
                else:
                    print('ERROR 1: The {} key does not exist in {}'.format(ip_key, settings_file))

                if username_key in config[sdk_key]:
                    device_username = config[sdk_key][username_key]
                else:
                    print('ERROR 2: The {} key does not exist in {}'.format(username_key, settings_file))

                if password_key in config[sdk_key]:
                    device_password = config[sdk_key][password_key]
                else:
                    print('ERROR 3: The {} key does not exist in {}'.format(password_key, settings_file))
            else:
                print('ERROR 4: The {} section does not exist in {}'.format(sdk_key, settings_file))

        return device_ip, device_username, device_password

    def _safe_dispatch(self, cmd):
        """Send the command and return the response."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect('/var/tmp/cs.sock')
            sock.sendall(bytes(cmd, 'ascii'))
            return self._receive(sock)

    def _dispatch(self, cmd):
        errmsg = None
        result = ""
        try:
            result = self._safe_dispatch(cmd)
        except Exception as err:
            # ignore the command error, continue on to next command
            errmsg = "dispatch failed with exception={} err={}".format(type(err), str(err))
        if errmsg is not None:
            self.log(CSCLIENT_NAME, errmsg)
            pass
        return result

    def _safe_receive(self, sock):
        sock.settimeout(self.RECV_TIMEOUT)
        data = b""
        eoh = -1
        while eoh < 0:
            # In the event that the config store times out in returning data, lib returns
            # an empty result. Then again, if the config store hangs for 2+ seconds,
            # the app's behavior is the least of our worries.
            try:
                buf = sock.recv(self.MAX_PACKET_SIZE)
            except socket.timeout:
                return {"status": "timeout", "data": None}
            if len(buf) == 0:
                break
            data += buf
            eoh = data.find(self.END_OF_HEADER)

        status_hdr = self.STATUS_HEADER_RE.search(data).group(0)[8:]
        content_len = self.CONTENT_LENGTH_HEADER_RE.search(data).group(0)[16:]
        remaining = int(content_len) - (len(data) - eoh - len(self.END_OF_HEADER))

        # body sent from csevent_xxx.sock will have id, action, path, & cfg
        while remaining > 0:
            buf = sock.recv(self.MAX_PACKET_SIZE)  # TODO: This will hang things as well.
            if len(buf) == 0:
                break
            data += buf
            remaining -= len(buf)
        body = data[eoh:].decode()
        try:
            result = json.loads(body)
        except json.JSONDecodeError as e:
            # config store receiver doesn't give back
            # proper json for 'put' ops, body
            # contains verbose error message
            # so putting the error msg in result
            result = body.strip()
        return {"status": status_hdr.decode(), "data": result}

    def _receive(self, sock):
        errmsg = None
        result = ""
        try:
            result = self._safe_receive(sock)
        except Exception as err:
            # ignore the command error, continue on to next command
            errmsg = "_receive failed with exception={} err={}".format(type(err), str(err))
        if errmsg is not None:
            self.log(CSCLIENT_NAME, errmsg)
        return result
