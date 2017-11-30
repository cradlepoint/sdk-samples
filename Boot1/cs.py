"""
sdk_config_store.py - Communication module for sdk apps

Copyright (c) 2017 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

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
    END_OF_HEADER = b"\r\n\r\n"
    STATUS_HEADER_RE = re.compile(b"status: \w*")
    CONTENT_LENGTH_HEADER_RE = re.compile(b"content-length: \w*")
    MAX_PACKET_SIZE = 8192
    RECV_TIMEOUT = 2.0

    _instances = {}

    @classmethod
    def is_initialized(cls):
        return (cls in cls._instances)

    def __new__(cls, *na, **kwna):
        """ Singleton factory (with subclassing support) """
        if not cls.is_initialized():
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, init=False):
        if not init:
            return

    @staticmethod
    def _get_router_access_info():
        """Should only be called when running in a computer. It will return the
           dev_client_ip, dev_client_username, and dev_client_password as defined in
           the sdk section of the sdk_settings.ini file."""
        router_ip = ''
        router_username = ''
        router_password = ''

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
                    router_ip = config[sdk_key][ip_key]
                else:
                    print('ERROR 1: The {} key does not exist in {}'.format(ip_key, settings_file))

                if username_key in config[sdk_key]:
                    router_username = config[sdk_key][username_key]
                else:
                    print('ERROR 2: The {} key does not exist in {}'.format(username_key, settings_file))

                if password_key in config[sdk_key]:
                    router_password = config[sdk_key][password_key]
                else:
                    print('ERROR 3: The {} key does not exist in {}'.format(password_key, settings_file))
            else:
                print('ERROR 4: The {} section does not exist in {}'.format(sdk_key, settings_file))

        return router_ip, router_username, router_password

    def get(self, base, query='', tree=0):
        """Send a get request."""
        if sys.platform == 'linux2':
            cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the get to the router.
            import requests
            router_ip, router_username, router_password = self._get_router_access_info()
            router_api = 'http://{}/api/{}/{}'.format(router_ip, base, query)

            try:
                response = requests.get(router_api,
                                        auth=requests.auth.HTTPDigestAuth(router_username, router_password))

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: router at {} did not respond.".format(router_ip))
                return None

            return json.loads(response.text)

    def put(self, base, value='', query='', tree=0):
        """Send a put request."""
        value = json.dumps(value).replace(' ', '')
        if sys.platform == 'linux2':
            cmd = "put\n{}\n{}\n{}\n{}\n".format(base, query, tree, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the put to the router.
            import requests
            router_ip, router_username, router_password = self._get_router_access_info()
            router_api = 'http://{}/api/{}/{}'.format(router_ip, base, query)

            try:
                response = requests.put(router_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=requests.auth.HTTPDigestAuth(router_username, router_password),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: router at {} did not respond.".format(router_ip))
                return None

            return response.text

    def append(self, base, value='', query=''):
        """Send an append request."""
        value = json.dumps(value).replace(' ', '')
        if sys.platform == 'linux2':
            cmd = "post\n{}\n{}\n{}\n".format(base, query, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the post to the router.
            import requests
            router_ip, router_username, router_password = self._get_router_access_info()
            router_api = 'http://{}/api/{}/{}'.format(router_ip, base, query)

            try:
                response = requests.post(router_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=requests.auth.HTTPDigestAuth(router_username, router_password),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: router at {} did not respond.".format(router_ip))
                return None

            return response.text

    def delete(self, base, query=''):
        """Send a delete request."""
        if sys.platform == 'linux2':
            cmd = "delete\n{}\n{}\n".format(base, query)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the delete to the router.
            import requests
            router_ip, router_username, router_password = self._get_router_access_info()
            router_api = 'http://{}/api/{}/{}'.format(router_ip, base, query)

            try:
                response = requests.delete(router_api,
                                           headers={"Content-Type": "application/x-www-form-urlencoded"},
                                           auth=requests.auth.HTTPDigestAuth(router_username, router_password))
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: router at {} did not respond.".format(router_ip))
                return None

            return response.text

    def alert(self, app_name='', value=''):
        """Send a request to create an alert."""
        if sys.platform == 'linux2':
            cmd = "alert\n{}\n{}\n".format(app_name, value)
            return self._dispatch(cmd)
        else:
            print('Alert is only available when running the app in NCOS.')
            print('Alert Text: {}'.format(value))

    def log(self, name='', value='', level='DEBUG'):
        """Send a request to create a log entry."""
        if sys.platform == 'linux2':
            cmd = "log\n{}\n{}\n".format(name, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so just use print for the log.
            print('[{}]: {}'.format(name, value))

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
