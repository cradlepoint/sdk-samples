"""
NCOS communication module for SDK applications.

This module provides a comprehensive interface for communicating with NCOS (Network
Control Operating System) routers. It includes classes and functions for:

- Direct communication with router configuration store
- Event-driven programming with config store events
- Status monitoring and retrieval
- Device control and management
- Network configuration and monitoring
- GPS and location services
- Certificate management
- Firewall and security management

The module supports both local execution on NCOS devices and remote execution
from development machines using HTTP API calls.

Copyright (c) 2025 Ericsson Enterprise Wireless Solutions <www.cradlepoint.com>.
All rights reserved.

This file contains confidential information of Ericsson Enterprise Wireless Solutions
and your use of this file is subject to the Ericsson Enterprise Wireless Solutions
Software License Agreement distributed with this file. Unauthorized reproduction
or distribution of this file is subject to civil and criminal penalties.
"""
import json
import os
import re
import select
import socket
import threading
import logging.handlers
import signal
import sys
import time
import configparser
import urllib.request
import urllib.parse
import traceback
import requests
import base64
import datetime
import random
import string
import http.server
import socketserver
import mimetypes
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Literal
from http import HTTPStatus
from datetime import datetime, timedelta
from enum import Enum

try:
    pass  # traceback already imported above
except ImportError:
    traceback = None


class SdkCSException(Exception):
    """Custom exception for SDK communication errors.
    
    This exception is raised when errors occur during communication
    with the NCOS configuration store or when SDK operations fail.
    """
    pass


class CSClient(object):
    """NCOS SDK mechanism for communication between apps and the router tree/config store.
    
    The CSClient class provides the primary interface for communicating with NCOS routers.
    Instances of this class communicate with the router using either socket connections
    (for local execution) or HTTP method calls (for remote execution).
    
    Apps running locally on the router use a Unix domain socket to send commands from
    the app to the router tree and to receive data (JSON) from the router tree.
    
    Apps running remotely use the requests library to send HTTP method calls to the
    router and to receive data from the router tree. This allows developers to use
    an IDE to run and debug the application on a computer, though with limitations
    regarding device hardware access (e.g., serial, USB, etc.).
    
    Attributes:
        app_name (str): The name of the application using this client.
        ncos (bool): Whether the client is running on an NCOS device.
        logger (logging.Logger): Logger instance for the application.
    """
    END_OF_HEADER = b"\r\n\r\n"
    STATUS_HEADER_RE = re.compile(rb"status: \w*")
    CONTENT_LENGTH_HEADER_RE = re.compile(rb"content-length: \w*")
    MAX_PACKET_SIZE = 8192
    RECV_TIMEOUT = 2.0

    _instances = {}

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the singleton instance has been created.
        
        Returns:
            bool: True if the singleton instance exists, False otherwise.
        """
        return cls in cls._instances

    def __new__(cls, *na: Any, **kwna: Any) -> 'CSClient':
        """Create or return the singleton instance with subclassing support.
        
        Args:
            *na: Variable length argument list (not used).
            **kwna: Arbitrary keyword arguments (not used).
            
        Returns:
            CSClient: The singleton instance of the class.
        """
        if not cls.is_initialized():
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, app_name: str, init: bool = False, enable_logging: bool = False, ncos: bool = False) -> None:
        """Initialize the CSClient instance.
        
        Args:
            app_name (str): The name of the application using this client.
            init (bool): Flag to perform full initialization. If False, only
                        the singleton instance is returned without initialization.
            enable_logging (bool): Whether to enable logging. Defaults to False.
            ncos (bool): Whether running on NCOS. Defaults to False.
        """
        if not init:
            return
        
        self.app_name = app_name
        self.enable_logging = enable_logging
        self.ncos = ncos

        # Cache device access credentials to avoid reading config file on every API call
        self._cached_device_ip = None
        self._cached_username = None
        self._cached_password = None
        self._cached_auth = None

        if self.ncos and self.enable_logging: 
            handlers = [logging.StreamHandler()]
        
            handlers.append(logging.handlers.SysLogHandler(address='/dev/log'))
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s: %(message)s', datefmt='%b %d %H:%M:%S',
                            handlers=handlers)
            self.logger = logging.getLogger(app_name)
        else:
            self.logger = None
        
        # Disable urllib3 connection pool logging to reduce noise
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

    def get(self, base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
        """Construct and send a GET request to retrieve specified data from a device.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              queries the router tree to retrieve the specified data.
            - If the app is running remotely from a computer, it calls the HTTP GET
              method to retrieve the specified data.
        
        Args:
            base (str): String representing a path to a resource on a router tree
                       (e.g., '/config/system/logging/level').
            query (str): Optional query string for the request. Defaults to empty string.
            tree (int): Optional tree identifier. Defaults to 0.
        
        Returns:
            dict or None: A dictionary containing the response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails.
        """
        if self.ncos:
            cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd).get('data')
        else:
            # Running in a computer so use http to send the get to the device.
            device_ip, username, password = self._get_cached_credentials()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.get(device_api, auth=self._get_cached_auth())

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text).get('data')

    def decrypt(self, base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
        """Construct and send a decrypt/GET request to retrieve encrypted data from a device.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              queries the router tree to retrieve and decrypt the specified data.
            - If the app is running remotely from a computer, it calls the HTTP GET
              method to retrieve the specified data.
        
        Args:
            base (str): String representing a path to a resource on a router tree
                       (e.g., '/config/system/logging/level').
            query (str): Optional query string for the request. Defaults to empty string.
            tree (int): Optional tree identifier. Defaults to 0.
        
        Returns:
            dict or None: A dictionary containing the decrypted response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails or if running remotely.
        """
        if self.ncos:
            cmd = "decrypt\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd).get('data')
        else:
            # Running in a computer and can't actually send the alert.
            print('Decrypt is only available when running the app in NCOS.')

    def put(self, base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
        """Construct and send a PUT request to update or add specified data to the device router tree.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              updates or adds the specified data to the router tree.
            - If the app is running remotely from a computer, it calls the HTTP PUT
              method to update or add the specified data.
        
        Args:
            base (str): String representing a path to a resource on a router tree
                       (e.g., '/config/system/logging/level').
            value (Any): The value to set at the specified path. Will be JSON serialized.
                        Defaults to empty string.
            query (str): Optional query string for the request. Defaults to empty string.
            tree (int): Optional tree identifier. Defaults to 0.
        
        Returns:
            dict or None: A dictionary containing the response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails.
        """
        value = json.dumps(value)
        if self.ncos:
            cmd = "put\n{}\n{}\n{}\n{}\n".format(base, query, tree, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the put to the device.
            device_ip, username, password = self._get_cached_credentials()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.put(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_cached_auth(),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def post(self, base: str, value: Any = '', query: str = '') -> Optional[Dict[str, Any]]:
        """Construct and send a POST request to update or add specified data to the device router tree.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              updates or adds the specified data to the router tree.
            - If the app is running remotely from a computer, it calls the HTTP POST
              method to update or add the specified data.
        
        Args:
            base (str): String representing a path to a resource on a router tree
                       (e.g., '/config/system/logging/level').
            value (Any): The value to set at the specified path. Will be JSON serialized.
                        Defaults to empty string.
            query (str): Optional query string for the request. Defaults to empty string.
        
        Returns:
            dict or None: A dictionary containing the response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails.
        """
        value = json.dumps(value)
        if self.ncos:
            cmd = f"post\n{base}\n{query}\n{value}\n"
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the post to the device.
            device_ip, username, password = self._get_cached_credentials()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.post(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_cached_auth(),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def patch(self, value: List[Any]) -> Optional[Dict[str, Any]]:
        """Construct and send a PATCH request to update or add specified data to the device router tree.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              updates or adds the specified data to the router tree.
            - If the app is running remotely from a computer, it calls the HTTP PUT
              method to update or add the specified data.
        
        Args:
            value (List[Any]): List containing dict of add/changes, and list of removals:
                              [{add}, [remove]].
        
        Returns:
            dict or None: A dictionary containing the response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails.
        """

        if self.ncos:
            if value[0].get("config"):
                adds = value[0]
            else:
                adds = {"config": value[0]}
            adds = json.dumps(adds)
            removals = json.dumps(value[1])
            cmd = f"patch\n{adds}\n{removals}\n"
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the put to the device.
            device_ip, username, password = self._get_cached_credentials()
            device_api = 'http://{}/api/'.format(device_ip)

            try:
                response = requests.patch(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_cached_auth(),
                                        data={"data": '{}'.format(json.dumps(value))})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def delete(self, base: str, query: str = '') -> Optional[Dict[str, Any]]:
        """Construct and send a DELETE request to delete specified data from the device router tree.
        
        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly
              deletes the specified data from the router tree.
            - If the app is running remotely from a computer, it calls the HTTP DELETE
              method to delete the specified data.
        
        Args:
            base (str): String representing a path to a resource on a router tree
                       (e.g., '/config/system/logging/level').
            query (str): Optional query string for the request. Defaults to empty string.
        
        Returns:
            dict or None: A dictionary containing the response data
                         (e.g., {"success": True, "data": {}}), or None if the
                         request fails.
        """
        if self.ncos:
            cmd = "delete\n{}\n{}\n".format(base, query)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the delete to the device.
            device_ip, username, password = self._get_cached_credentials()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.delete(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_cached_auth(),
                                        data={"data": '{}'.format(base)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def alert(self, value: str = '') -> Optional[Dict[str, Any]]:
        """Construct and send a custom alert to NCM for the device.
        
        Apps calling this method must be running on the target device to send the alert.
        If invoked while running on a computer, then only a log is output.
        
        Args:
            value (str): String to be displayed for the alert. Defaults to empty string.
        
        Returns:
            dict or None: Success returns None, failure returns an error dictionary.
                         When running remotely, always returns None and logs the alert.
        """
        if self.ncos:
            cmd = "alert\n{}\n{}\n".format(self.app_name, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer and can't actually send the alert.
            print('Alert is only available when running the app in NCOS.')
            print('Alert Text: {}'.format(value))

    def log(self, value: Union[str, Dict[str, Any]] = '') -> None:
        """Add an INFO log to the device SYSLOG.
        
        Args:
            value (Union[str, Dict[str, Any]]): String text or dictionary for the log. 
                If a dictionary is provided, it will be formatted as JSON with indentation.
                Defaults to empty string.
        
        Returns:
            None: This method does not return a value.
        """
        # Check if value is a dictionary and format it as JSON
        if isinstance(value, dict):
            formatted_value = '\n' + json.dumps(value, indent=2)
        else:
            formatted_value = value
            
        if _cs_client.enable_logging:
            # Running in NCOS so write to the logger
            self.logger.info(formatted_value)
        elif self.ncos:
            # Running in container so write to stdout
            with open('/dev/stdout', 'w') as log:
                log.write(f'{formatted_value}\n')
        else:
            # Running in a computer so just use print for the log.
            print(formatted_value)


    def _get_cached_credentials(self) -> Tuple[str, str, str]:
        """Get cached device credentials, loading them if not already cached.
        
        Returns:
            Tuple[str, str, str]: A tuple containing (device_ip, username, password)
        """
        if self._cached_device_ip is None:
            self._cached_device_ip, self._cached_username, self._cached_password = self._get_device_access_info()
        return self._cached_device_ip, self._cached_username, self._cached_password
    
    def _get_cached_auth(self) -> Any:
        """Get cached authentication object, creating it if not already cached.
        
        Returns:
            requests.auth.HTTPBasicAuth or requests.auth.HTTPDigestAuth: The appropriate
            authentication object based on the NCOS version.
        """
        if self._cached_auth is None:
            device_ip, username, password = self._get_cached_credentials()
            self._cached_auth = self._get_auth(device_ip, username, password)
        return self._cached_auth

    def _get_auth(self, device_ip: str, username: str, password: str) -> Any:
        """Return the proper HTTP Auth for the NCOS version.
        
        This is only needed when the app is running on a computer.
        Digest Auth is used for NCOS 6.4 and below while Basic Auth is
        used for NCOS 6.5 and up.
        
        Args:
            device_ip (str): IP address of the target device.
            username (str): Username for authentication.
            password (str): Password for authentication.
        
        Returns:
            requests.auth.HTTPBasicAuth or requests.auth.HTTPDigestAuth: The appropriate
            authentication object based on the NCOS version.
        """

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
    def _get_device_access_info() -> Tuple[str, str, str]:
        """Return device access info from the sdk_settings.ini file.
        
        This should only be called when running on a computer.
        
        Returns:
            Tuple[str, str, str]: A tuple containing (device_ip, username, password)
                                 from the sdk_settings.ini file.
        """
        try:
            device_ip = ''
            device_username = ''
            device_password = ''

            if 'linux' not in sys.platform:

                # Try parent directory first, then fallback to current directory
                parent_settings_file = os.path.join(os.path.dirname(os.getcwd()), 'sdk_settings.ini')
                current_settings_file = os.path.join(os.getcwd(), 'sdk_settings.ini')
                
                # Check which file exists
                if os.path.exists(parent_settings_file):
                    settings_file = parent_settings_file
                elif os.path.exists(current_settings_file):
                    settings_file = current_settings_file
                else:
                    settings_file = parent_settings_file  # Use parent as default for error messages
                
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
        except Exception as e:
            print(f"Error getting device access info: {e}")
            return '', '', ''

    def _safe_dispatch(self, cmd: str) -> Dict[str, Any]:
        """Send the command and return the response.
        
        Args:
            cmd (str): The command string to send to the router.
        
        Returns:
            dict: A dictionary containing the response with 'status' and 'data' keys.
        """
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect('/var/tmp/cs.sock')
                sock.sendall(bytes(cmd, 'ascii'))
                return self._receive(sock)
        except Exception as e:
            self.log(f"Error in safe dispatch: {e}")
            return {"status": "error", "data": str(e)}

    def _dispatch(self, cmd: str) -> Dict[str, Any]:
        """Safely dispatch a command to the router.
        
        Args:
            cmd (str): The command string to send to the router.
        
        Returns:
            dict: A dictionary containing the response from the router.
        """
        errmsg = None
        result = ""
        try:
            result = self._safe_dispatch(cmd)
        except Exception as err:
            # ignore the command error, continue on to next command
            errmsg = "dispatch failed with exception={} err={}".format(type(err), str(err))
        if errmsg is not None:
            self.log(errmsg)
            pass
        return result

    def _safe_receive(self, sock: socket.socket) -> Dict[str, Any]:
        """Safely receive data from a socket.
        
        Args:
            sock (socket.socket): The socket to receive data from.
        
        Returns:
            dict: A dictionary containing the response with 'status' and 'data' keys.
        """
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

    def _receive(self, sock: socket.socket) -> Dict[str, Any]:
        """Receive data from a socket with error handling.
        
        Args:
            sock (socket.socket): The socket to receive data from.
        
        Returns:
            dict: A dictionary containing the response from the socket.
        """
        errmsg = None
        result = ""
        try:
            result = self._safe_receive(sock)
        except Exception as err:
            # ignore the command error, continue on to next command
            errmsg = "_receive failed with exception={} err={}".format(type(err), str(err))
        if errmsg is not None:
            self.log(errmsg)
        return result


class EventingCSClient(CSClient):
    """Event-driven CSClient for handling config store events.
    
    The EventingCSClient extends CSClient to provide event-driven programming
    capabilities. It allows applications to register callbacks that are triggered
    when specific config store events occur (e.g., when values are set or retrieved).
    
    This class manages a background thread that listens for config store events
    and invokes registered callbacks when events occur.
    
    Attributes:
        running (bool): Whether the event handling loop is currently running.
        registry (dict): Dictionary mapping event IDs to callback information.
        eids (int): Counter for generating unique event IDs.
        on (method): Alias for the register method.
        un (method): Alias for the unregister method.
    """
    running = False
    registry = {}
    eids = 1

    def __init__(self, app_name: str, init: bool = True, enable_logging: bool = False, ncos: bool = False) -> None:
        """Initialize the EventingCSClient and set up aliases for register/unregister.
        
        Args:
            app_name (str): The name of the application using this client.
            init (bool): Flag to perform full initialization. Defaults to True.
            enable_logging (bool): Whether to enable logging. Defaults to False.
            ncos (bool): Whether running on NCOS. Defaults to False.
        """
        super().__init__(app_name, init, enable_logging, ncos)
        self.on = self.register
        self.un = self.unregister

    def start(self) -> None:
        """Start the event handling loop in a separate thread.
        
        This method creates a Unix domain socket, starts a background thread
        to handle config store events, and begins listening for incoming events.
        """
        try:
            if self.running:
                self.log(f"Eventing Config Store {self.pid} already running")
                return
            self.running = True
            self.pid = os.getpid()
            self.f = '/var/tmp/csevent_%d.sock' % self.pid
            try:
                os.unlink(self.f)
            except FileNotFoundError:
                pass
            self.event_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.event_sock.bind(self.f)
            self.event_sock.listen()  # backlog is optional. already set on value found in /proc
            self.event_sock.setblocking(False)
            self.eloop = threading.Thread(target=self._handle_events)
            self.eloop.start()
        except Exception as e:
            self.log(f"Error starting event handling loop: {e}")
            self.running = False

    def stop(self) -> None:
        """Stop the event handling loop and clean up resources.
        
        This method unregisters all callbacks, closes the event socket,
        removes the socket file, and stops the background thread.
        """
        try:
            if not self.running:
                return
            self.log(f"Stopping")
            for k in list(self.registry.keys()):
                self.unregister(k)
            self.event_sock.close()
            os.unlink(self.f)
            self.running = False
        except Exception as e:
            self.log(f"Error stopping event handling loop: {e}")
            self.running = False

    def _handle_events(self) -> None:
        """The main event loop for handling config store events.
        
        This method runs in a separate thread and continuously polls for
        incoming config store events. When events are received, it invokes
        the appropriate registered callbacks.
        """
        poller = select.poll()
        poller.register(self.event_sock,
                        select.POLLIN | select.POLLERR | select.POLLHUP)  # I don't unregsiter this in cleaning up!
        while self.running:
            try:
                events = poller.poll(1000)
                for f, ev in events:
                    if ev & (select.POLLERR | select.POLLHUP):
                        self.log("Hangup/error received. Stopping")
                        self.stop()  # TODO: restart w/ cached registrations. Will no longer be an error case

                    if ev & select.POLLIN:
                        conn, addr = self.event_sock.accept()
                        result = self._receive(conn)
                        eid = int(result['data']['id'])
                        try:
                            cb = self.registry[eid]['cb']
                            args = self.registry[eid]['args']
                            try:
                                # PUTting just a string to config store results in a json encoded string returned.
                                # e.g. set /config/system/logging/level "debug", result['data']['cfg'] is '"debug"'
                                cfg = json.loads(result['data']['cfg'])
                            except TypeError as e:
                                # Non-string path
                                cfg = result['data']['cfg']
                            try:
                                cb_return = cb(result['data']['path'], cfg, args)
                            except:
                                if traceback:
                                    traceback.print_exc()
                                self.log(f"Exception during callback for {str(self.registry[eid])}")
                            if result['data']['action'] == 'get':  # We've something to send back.
                                # config_store_receiver expects json
                                cb_return = json.JSONEncoder().encode(cb_return)
                                conn.sendall(
                                    cb_return.encode())  # No dispatch. Config store receiver will put to config store.
                        except (NameError, ValueError) as e:
                            self.log(f"Could not find register data for eid {eid}")
            except OSError as e:
                self.log(f"OSError: {e}")
                raise

    def register(self, action: str = 'set', path: str = '', callback: Callable = None, *args: Any) -> Dict[str, Any]:
        """Register a callback for a config store event.
        
        Args:
            action (str): The action to listen for (e.g., 'set', 'get'). Defaults to 'set'.
            path (str): The config store path to monitor. Defaults to empty string.
            callback (callable): The function to call when the event occurs. Defaults to None.
            *args: Additional arguments to pass to the callback.
        
        Returns:
            dict: The result of the registration command.
        """
        try:
            if not self.running:
                self.start()
            # what about multiple registration?
            eid = self.eids
            self.eids += 1
            self.registry[eid] = {'cb': callback, 'action': action, 'path': path, 'args': args}
            cmd = "register\n{}\n{}\n{}\n{}\n".format(self.pid, eid, action, path)
            return self._dispatch(cmd)
        except Exception as e:
            self.log(f"Error registering callback for {path}: {e}")
            return {}

    def unregister(self, eid: int = 0) -> Dict[str, Any]:
        """Unregister a callback by its event ID.
        
        Args:
            eid (int): The event ID returned by register. Defaults to 0.
        
        Returns:
            dict: The result of the unregistration command.
        """
        ret = ""
        try:
            e = self.registry[eid]
        except KeyError:
            pass
        else:
            if self.running:
                cmd = "unregister\n{}\n{}\n{}\n{}\n".format(self.pid, eid, e['action'], e['path'])
                ret = self._dispatch(cmd)
            del self.registry[eid]
        return ret

    # ============================================================================
    # GRANULAR STATUS GET METHODS
    # ============================================================================
    
    def get_gps_status(self) -> Dict[str, Any]:
        """Get GPS status and return detailed information with decimal coordinates.
        
        Returns:
            dict: Dictionary containing GPS status information including:

                - gps_lock (bool): Whether GPS has a lock
                - satellites (int): Number of satellites in view
                - location (dict): GPS coordinates in degrees/minutes/seconds format
                - latitude (float): GPS latitude in decimal format
                - longitude (float): GPS longitude in decimal format
                - altitude (float): Altitude in meters
                - speed (float): Ground speed in knots
                - heading (float): Heading in degrees
                - accuracy (float): GPS accuracy in meters
                - last_fix_age (int): Age of last GPS fix
        """
        try:
            gps_data = self.get('status/gps')
            if not gps_data:
                return {"gps_lock": False, "satellites": 0}
            
            analysis = {
                "gps_lock": False,
                "satellites": 0,
                "location": None,
                "latitude": None,
                "longitude": None,
                "altitude": None,
                "speed": None,
                "heading": None,
                "accuracy": None,
                "last_fix_age": None
            }
            
            fix = gps_data.get("fix", {})
            if fix:
                analysis.update({
                    "gps_lock": fix.get("lock", False),
                    "satellites": fix.get("satellites", 0),
                    "altitude": fix.get("altitude_meters"),
                    "speed": fix.get("ground_speed_knots"),
                    "heading": fix.get("heading"),
                    "accuracy": fix.get("accuracy"),
                    "last_fix_age": fix.get("age")
                })
                
                if fix.get("latitude") and fix.get("longitude"):
                    analysis["location"] = {
                        "latitude": f"{fix['latitude']['degree']}°{fix['latitude']['minute']}'{fix['latitude']['second']}\"",
                        "longitude": f"{fix['longitude']['degree']}°{fix['longitude']['minute']}'{fix['longitude']['second']}\""
                    }
                    
                    # Add decimal coordinates to the root level
                    try:
                        lat_deg = fix['latitude']['degree']
                        lat_min = fix['latitude']['minute']
                        lat_sec = fix['latitude']['second']
                        long_deg = fix['longitude']['degree']
                        long_min = fix['longitude']['minute']
                        long_sec = fix['longitude']['second']
                        
                        decimal_lat = dec(lat_deg, lat_min, lat_sec)
                        decimal_long = dec(long_deg, long_min, long_sec)
                        
                        analysis["latitude"] = decimal_lat
                        analysis["longitude"] = decimal_long
                    except Exception as coord_error:
                        self.log(f"Error converting coordinates to decimal: {coord_error}")
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing GPS status: {e}")
            return {"error": str(e)}

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and return detailed information.
        
        Returns:
            dict: Dictionary containing system status information including:

                - uptime (int): System uptime in seconds
                - temperature (float): System temperature
                - cpu_usage (dict): CPU usage statistics
                - memory_usage (dict): Memory usage statistics
                - services_running (int): Number of running services
                - services_disabled (int): Number of disabled services
                - internal_apps_running (int): Number of running internal applications
                - external_apps_running (int): Number of running external applications
        """
        try:
            system_data = self.get('status/system')
            if not system_data:
                return {}
            
            analysis = {
                "uptime": system_data.get("uptime"),
                "temperature": system_data.get("temperature"),
                "cpu_usage": system_data.get("cpu", {}),
                "memory_usage": system_data.get("memory", {}),
                "services_running": 0,
                "services_disabled": 0,
                "internal_apps_running": 0,
                "external_apps_running": 0
            }
            
            services = system_data.get("services", {})
            for service, info in services.items():
                if isinstance(info, dict) and info.get("state") == "started":
                    analysis["services_running"] += 1
                elif isinstance(info, dict) and info.get("state") == "disabled":
                    analysis["services_disabled"] += 1
            
            # Count internal apps (from system/apps)
            internal_apps = system_data.get("apps", [])
            analysis["internal_apps_running"] = len([app for app in internal_apps if app.get("state") == "started"])
            
            # Count external apps (from system/sdk/apps)
            sdk_data = system_data.get("sdk", {})
            external_apps = sdk_data.get("apps", [])
            analysis["external_apps_running"] = len([app for app in external_apps if app.get("state") == "started"])
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing system status: {e}")
            return {"error": str(e)}

    def get_wlan_status(self) -> Dict[str, Any]:
        """Get WLAN status and return detailed information.
        
        Returns:
            dict: Dictionary containing WLAN status information including:

                - wlan_state (str): WLAN operational state
                - radios (list): List of radio information including:
                    - radio_id (int): Radio identifier
                    - band (str): Radio band (e.g., "2.4 GHz")
                    - channel (int): Current channel number
                    - channel_locked (bool): Whether channel is locked
                    - channel_list (list): Available channels
                    - channel_contention (int): Channel contention value
                    - txpower (int): Transmission power
                    - region_code (int): Regulatory region code
                    - reconnecting (bool): Whether radio is reconnecting
                    - bss_count (int): Number of BSS (Basic Service Sets)
                    - clients_count (int): Number of clients on this radio
                    - survey_data (int): Number of survey data points
                - clients_connected (int): Total number of connected clients across all radios
        """
        try:
            wlan_data = self.get('status/wlan')
            if not wlan_data:
                return {}
            
            analysis = {
                "wlan_state": wlan_data.get("state"),
                "radios": [],
                "clients_connected": 0
            }
            
            radios = wlan_data.get("radio", [])
            total_clients = 0
            for i, radio in enumerate(radios):
                radio_info = {
                    "radio_id": i,
                    "band": radio.get("band"),
                    "channel": radio.get("channel"),
                    "channel_locked": radio.get("channel_locked"),
                    "channel_list": radio.get("channel_list", []),
                    "channel_contention": radio.get("channel_contention"),
                    "txpower": radio.get("txpower"),
                    "region_code": radio.get("region_code"),
                    "reconnecting": radio.get("reconnecting"),
                    "bss_count": len(radio.get("bss", [])),
                    "clients_count": len(radio.get("clients", [])),
                    "survey_data": len(radio.get("survey", []))
                }
                analysis["radios"].append(radio_info)
                total_clients += radio_info["clients_count"]
            
            analysis["clients_connected"] = total_clients
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing WLAN status: {e}")
            return {"error": str(e)}

    def get_wan_status(self) -> Dict[str, Any]:
        """Get WAN status and return detailed information.
        
        Returns:
            dict: Dictionary containing WAN status information including:
                - primary_device (str): Primary WAN device identifier
                - connection_state (str): Overall connection state
                - cellular_health_score (str): Overall cellular health score
                - devices (list): List of WAN device information including:
                    - uid (str): Device unique identifier
                    - connection_state (str): Device connection state
                    - signal_strength (str): Signal strength indicator
                    - cellular_health (str): Cellular health category
                    - ip_address (str): Device IP address
                    - uptime (int): Device uptime in seconds
                    - For modem devices (uid starts with "mdm"), additional fields:
                        - active_apn (str): Active APN name
                        - carrier_id (str): Carrier identifier
                        - cell_id (str): Cell tower identifier
                        - cur_plmn (str): Current PLMN code
                        - dbm (str): Signal strength in dBm
                        - imei (str): Device IMEI
                        - lte_bandwidth (str): LTE bandwidth
                        - model (str): Device model
                        - mdn (str): Mobile directory number
                        - home_carrier (str): Home carrier
                        - phy_cell_id (str): Physical cell ID
                        - rf_band (str): Radio frequency band
                        - rf_channel (str): Radio frequency channel
                        - rsrp (str): Reference signal received power
                        - rsrq (str): Reference signal received quality
                        - service_discovery (str): Service discovery info
                        - sim_number (str): SIM slot number
                        - sinr (str): Signal to interference plus noise ratio
                        - service_type (str): Service type (4G/5G)
                        - service_type_details (str): Detailed service information
                        - tac (str): Tracking area code
                        - dl_frequency (str): Downlink frequency
                        - ul_frequency (str): Uplink frequency
                        - rsrp_5g (str): 5G RSRP value
                        - rsrq_5g (str): 5G RSRQ value
                        - sinr_5g (str): 5G SINR value
                        - stats (dict): Device statistics including:
                            - collisions (int): Collision count
                            - idrops (int): Input drop count
                            - ierrors (int): Input error count
                            - in_bytes (int): Input bytes
                            - ipackets (int): Input packet count
                            - multicast (int): Multicast count
                            - odrops (int): Output drop count
                            - oerrors (int): Output error count
                            - opackets (int): Output packet count
                            - out_bytes (int): Output bytes
                    - For ethernet devices (uid starts with "ethernet"), additional fields:
                        - capabilities (str): Device capabilities
                        - config_id (str): Configuration identifier
                        - interface (str): Interface name
                        - mac_address (str): MAC address
                        - mtu (int): Maximum transmission unit
                        - port (str): Port number
                        - port_name (dict): Port name mapping
                        - type (str): Device type
        """
        try:
            wan_data = self.get('status/wan')
            if not wan_data:
                return {}
            
            analysis = {
                "primary_device": wan_data.get("primary_device"),
                "connection_state": None,
                "cellular_health_score": None,
                "devices": []
            }
            
            devices = wan_data.get("devices", {})
            for device_id, device_info in devices.items():
                device_analysis = {
                    "uid": device_id,
                    "connection_state": device_info.get("status", {}).get("connection_state"),
                    "signal_strength": device_info.get("status", {}).get("signal_strength"),
                    "cellular_health": device_info.get("status", {}).get("cellular_health_category"),
                    "ip_address": device_info.get("status", {}).get("ipinfo", {}).get("ip_address"),
                    "uptime": device_info.get("status", {}).get("uptime")
                }
                
                # Add modem diagnostics for modem devices
                if device_id.startswith("mdm"):
                    try:
                        diagnostics = self.get(f'status/wan/devices/{device_id}/diagnostics')
                        if diagnostics:
                            device_analysis.update({
                                "active_apn": diagnostics.get("ACTIVEAPN"),
                                "carrier_id": diagnostics.get("CARRID"),
                                "cell_id": diagnostics.get("CELL_ID"),
                                "cur_plmn": diagnostics.get("CUR_PLMN"),
                                "dbm": diagnostics.get("DBM"),
                                "imei": diagnostics.get("DISP_IMEI"),
                                "lte_bandwidth": diagnostics.get("LTEBANDWIDTH"),
                                "model": diagnostics.get("MDL"),
                                "mdn": diagnostics.get("MDN"),
                                "home_carrier": diagnostics.get("HOMECARRID"),
                                "phy_cell_id": diagnostics.get("PHY_CELL_ID"),
                                "rf_band": diagnostics.get("RFBAND"),
                                "rf_channel": diagnostics.get("RFCHANNEL"),
                                "rsrp": diagnostics.get("RSRP"),
                                "rsrq": diagnostics.get("RSRQ"),
                                "service_discovery": diagnostics.get("SERDIS"),
                                "sim_number": diagnostics.get("SIM_NUM"),
                                "sinr": diagnostics.get("SINR"),
                                "service_type": diagnostics.get("SRVC_TYPE"),
                                "service_type_details": diagnostics.get("SRVC_TYPE_DETAILS"),
                                "tac": diagnostics.get("TAC"),
                                "dl_frequency": diagnostics.get("DLFRQ"),
                                "ul_frequency": diagnostics.get("ULFRQ"),
                                "rsrp_5g": diagnostics.get("RSRP_5G"),
                                "rsrq_5g": diagnostics.get("RSRQ_5G"),
                                "sinr_5g": diagnostics.get("SINR_5G")
                            })
                        
                        # Add modem statistics
                        stats = self.get(f'status/wan/devices/{device_id}/stats')
                        if stats:
                            device_analysis.update({
                                "stats": {
                                    "collisions": stats.get("collisions"),
                                    "idrops": stats.get("idrops"),
                                    "ierrors": stats.get("ierrors"),
                                    "in_bytes": stats.get("in"),
                                    "ipackets": stats.get("ipackets"),
                                    "multicast": stats.get("multicast"),
                                    "odrops": stats.get("odrops"),
                                    "oerrors": stats.get("oerrors"),
                                    "opackets": stats.get("opackets"),
                                    "out_bytes": stats.get("out")
                                }
                            })
                    except Exception as e:
                        self.log(f"Error getting modem diagnostics for {device_id}: {e}")
                
                # Add ethernet device information for ethernet devices
                elif device_id.startswith("ethernet"):
                    try:
                        info = self.get(f'status/wan/devices/{device_id}/info')
                        if info:
                            device_analysis.update({
                                "capabilities": info.get("capabilities"),
                                "config_id": info.get("config_id"),
                                "interface": info.get("iface"),
                                "mac_address": info.get("mac"),
                                "mtu": info.get("mtu"),
                                "port": info.get("port"),
                                "port_name": info.get("port_name"),
                                "type": info.get("type")
                            })
                    except Exception as e:
                        self.log(f"Error getting ethernet info for {device_id}: {e}")
                
                analysis["devices"].append(device_analysis)
                
                # Set connection state and cellular health score from first device
                if analysis["connection_state"] is None:
                    analysis["connection_state"] = device_analysis["connection_state"]
                if analysis["cellular_health_score"] is None and device_analysis.get("cellular_health"):
                    analysis["cellular_health_score"] = device_analysis["cellular_health"]
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing WAN status: {e}")
            return {"error": str(e)}

    def get_wan_devices(self) -> Dict[str, Any]:
        """Get WAN device information only.
        
        Returns:
            dict: Dictionary containing WAN device information including:
                - primary_device (str): Primary WAN device identifier
                - devices (list): List of WAN device information including:
                    - uid (str): Device unique identifier
                    - connection_state (str): Device connection state
                    - signal_strength (str): Signal strength indicator
                    - cellular_health (str): Cellular health category
                    - ip_address (str): Device IP address
                    - uptime (int): Device uptime in seconds
        """
        try:
            wan_data = self.get('status/wan')
            if not wan_data:
                return {}
            
            devices = wan_data.get("devices", {})
            device_list = []
            
            for device_id, device_info in devices.items():
                device_analysis = {
                    "uid": device_id,
                    "connection_state": device_info.get("status", {}).get("connection_state"),
                    "signal_strength": device_info.get("status", {}).get("signal_strength"),
                    "cellular_health": device_info.get("status", {}).get("cellular_health_category"),
                    "ip_address": device_info.get("status", {}).get("ipinfo", {}).get("ip_address"),
                    "uptime": device_info.get("status", {}).get("uptime")
                }
                device_list.append(device_analysis)
            
            return {
                "primary_device": wan_data.get("primary_device"),
                "devices": device_list
            }
        except Exception as e:
            self.log(f"Error analyzing WAN devices: {e}")
            return {"error": str(e)}

    def get_wan_modem_diagnostics(self, device_id: str) -> Dict[str, Any]:
        """Get modem diagnostics for a specific WAN device.
        
        Args:
            device_id (str): WAN device identifier to get diagnostics for
            
        Returns:
            dict: Dictionary containing modem diagnostics including:
                - device_id (str): Device identifier
                - diagnostics (dict): Modem diagnostics including:
                    - active_apn (str): Active APN name
                    - carrier_id (str): Carrier identifier
                    - cell_id (str): Cell tower identifier
                    - cur_plmn (str): Current PLMN code
                    - dbm (str): Signal strength in dBm
                    - imei (str): Device IMEI
                    - lte_bandwidth (str): LTE bandwidth
                    - model (str): Device model
                    - mdn (str): Mobile directory number
                    - home_carrier (str): Home carrier
                    - phy_cell_id (str): Physical cell ID
                    - rf_band (str): Radio frequency band
                    - rf_channel (str): Radio frequency channel
                    - rsrp (str): Reference signal received power
                    - rsrq (str): Reference signal received quality
                    - service_discovery (str): Service discovery info
                    - sim_number (str): SIM slot number
                    - sinr (str): Signal to interference plus noise ratio
                    - service_type (str): Service type (4G/5G)
                    - service_type_details (str): Detailed service information
                    - tac (str): Tracking area code
                    - dl_frequency (str): Downlink frequency
                    - ul_frequency (str): Uplink frequency
                    - rsrp_5g (str): 5G RSRP value
                    - rsrq_5g (str): 5G RSRQ value
                    - sinr_5g (str): 5G SINR value
        """
        try:
            if not device_id.startswith("mdm"):
                return {"device_id": device_id, "error": "Device is not a modem"}
            
            diagnostics = self.get(f'status/wan/devices/{device_id}/diagnostics')
            if not diagnostics:
                return {"device_id": device_id}
            
            return {
                "device_id": device_id,
                "diagnostics": {
                    "active_apn": diagnostics.get("ACTIVEAPN"),
                    "carrier_id": diagnostics.get("CARRID"),
                    "cell_id": diagnostics.get("CELL_ID"),
                    "cur_plmn": diagnostics.get("CUR_PLMN"),
                    "dbm": diagnostics.get("DBM"),
                    "imei": diagnostics.get("DISP_IMEI"),
                    "lte_bandwidth": diagnostics.get("LTEBANDWIDTH"),
                    "model": diagnostics.get("MDL"),
                    "mdn": diagnostics.get("MDN"),
                    "home_carrier": diagnostics.get("HOMECARRID"),
                    "phy_cell_id": diagnostics.get("PHY_CELL_ID"),
                    "rf_band": diagnostics.get("RFBAND"),
                    "rf_channel": diagnostics.get("RFCHANNEL"),
                    "rsrp": diagnostics.get("RSRP"),
                    "rsrq": diagnostics.get("RSRQ"),
                    "service_discovery": diagnostics.get("SERDIS"),
                    "sim_number": diagnostics.get("SIM_NUM"),
                    "sinr": diagnostics.get("SINR"),
                    "service_type": diagnostics.get("SRVC_TYPE"),
                    "service_type_details": diagnostics.get("SRVC_TYPE_DETAILS"),
                    "tac": diagnostics.get("TAC"),
                    "dl_frequency": diagnostics.get("DLFRQ"),
                    "ul_frequency": diagnostics.get("ULFRQ"),
                    "rsrp_5g": diagnostics.get("RSRP_5G"),
                    "rsrq_5g": diagnostics.get("RSRQ_5G"),
                    "sinr_5g": diagnostics.get("SINR_5G")
                }
            }
        except Exception as e:
            self.log(f"Error getting modem diagnostics for {device_id}: {e}")
            return {"device_id": device_id, "error": str(e)}

    def get_wan_modem_stats(self, device_id: str) -> Dict[str, Any]:
        """Get modem statistics for a specific WAN device.
        
        Args:
            device_id (str): WAN device identifier to get statistics for
            
        Returns:
            dict: Dictionary containing modem statistics including:
                - device_id (str): Device identifier
                - stats (dict): Modem statistics including:
                    - collisions (int): Collision count
                    - idrops (int): Input drop count
                    - ierrors (int): Input error count
                    - in_bytes (int): Input bytes
                    - ipackets (int): Input packet count
                    - multicast (int): Multicast count
                    - odrops (int): Output drop count
                    - oerrors (int): Output error count
                    - opackets (int): Output packet count
                    - out_bytes (int): Output bytes
        """
        try:
            if not device_id.startswith("mdm"):
                return {"device_id": device_id, "error": "Device is not a modem"}
            
            stats = self.get(f'status/wan/devices/{device_id}/stats')
            if not stats:
                return {"device_id": device_id}
            
            return {
                "device_id": device_id,
                "stats": {
                    "collisions": stats.get("collisions"),
                    "idrops": stats.get("idrops"),
                    "ierrors": stats.get("ierrors"),
                    "in_bytes": stats.get("in"),
                    "ipackets": stats.get("ipackets"),
                    "multicast": stats.get("multicast"),
                    "odrops": stats.get("odrops"),
                    "oerrors": stats.get("oerrors"),
                    "opackets": stats.get("opackets"),
                    "out_bytes": stats.get("out")
                }
            }
        except Exception as e:
            self.log(f"Error getting modem stats for {device_id}: {e}")
            return {"device_id": device_id, "error": str(e)}

    def get_wan_ethernet_info(self, device_id: str) -> Dict[str, Any]:
        """Get ethernet device information for a specific WAN device.
        
        Args:
            device_id (str): WAN device identifier to get information for
            
        Returns:
            dict: Dictionary containing ethernet device information including:
                - device_id (str): Device identifier
                - info (dict): Ethernet device information including:
                    - capabilities (str): Device capabilities
                    - config_id (str): Configuration identifier
                    - interface (str): Interface name
                    - mac_address (str): MAC address
                    - mtu (int): Maximum transmission unit
                    - port (str): Port number
                    - port_name (dict): Port name mapping
                    - type (str): Device type
        """
        try:
            if not device_id.startswith("ethernet"):
                return {"device_id": device_id, "error": "Device is not ethernet"}
            
            info = self.get(f'status/wan/devices/{device_id}/info')
            if not info:
                return {"device_id": device_id}
            
            return {
                "device_id": device_id,
                "info": {
                    "capabilities": info.get("capabilities"),
                    "config_id": info.get("config_id"),
                    "interface": info.get("iface"),
                    "mac_address": info.get("mac"),
                    "mtu": info.get("mtu"),
                    "port": info.get("port"),
                    "port_name": info.get("port_name"),
                    "type": info.get("type")
                }
            }
        except Exception as e:
            self.log(f"Error getting ethernet info for {device_id}: {e}")
            return {"device_id": device_id, "error": str(e)}

    def get_wan_connection_state(self) -> Dict[str, Any]:
        """Get WAN connection state status.
        
        Returns:
            dict: Dictionary containing WAN connection state information including:
                - connection_state (str): Overall WAN connection state
                - timestamp (str): Timestamp when the state was retrieved
        """
        try:
            connection_state = self.get('status/wan/connection_state')
            if connection_state is None:
                return {"connection_state": "unknown", "timestamp": None}
            
            return {
                "connection_state": connection_state,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.log(f"Error getting WAN connection state: {e}")
            return {"connection_state": "error", "error": str(e)}

    def get_lan_status(self) -> Dict[str, Any]:
        """Get LAN status and return detailed information.
        
        Returns:
            dict: Dictionary containing LAN status information including:
                - total_ipv4_clients (int): Number of connected IPv4 clients
                - total_ipv6_clients (int): Number of connected IPv6 clients
                - lan_stats (dict): Overall LAN statistics including:
                    - bps (int): Total bits per second
                    - collisions (int): Collision count
                    - ibps (int): Input bits per second
                    - idrops (int): Input drop count
                    - ierrors (int): Input error count
                    - imcasts (int): Input multicast count
                    - in_bytes (int): Input bytes
                    - ipackets (int): Input packet count
                    - noproto (int): No protocol count
                    - obps (int): Output bits per second
                    - oerrors (int): Output error count
                    - omcasts (int): Output multicast count
                    - opackets (int): Output packet count
                    - out_bytes (int): Output bytes
                    - timestamp (float): Statistics timestamp
                - ipv4_clients (list): List of connected IPv4 clients including:
                    - ip_address (str): Client IP address
                    - mac (str): Client MAC address
                - ipv6_clients (list): List of connected IPv6 clients including:
                    - ip_address (str): Client IP address
                    - mac (str): Client MAC address
                - networks (list): List of network information including:
                    - name (str): Network identifier
                    - display_name (str): Human-readable network name
                    - ip_address (str): Network IP address
                    - netmask (str): Network netmask
                    - broadcast (str): Network broadcast address
                    - hostname (str): Network hostname
                    - type (str): Network type
                    - devices (list): Network devices including:
                        - interface (str): Device interface name
                        - state (str): Device state
                        - type (str): Device type
                        - uid (str): Device unique identifier
                - devices (list): List of device information with statistics including:
                    - name (str): Device name
                    - interface (str): Device interface
                    - link_state (str): Device link state
                    - type (str): Device type
                    - stats (dict): Device statistics including:
                        - collisions (int): Collision count
                        - idrops (int): Input drop count
                        - ierrors (int): Input error count
                        - in_bytes (int): Input bytes
                        - ipackets (int): Input packet count
                        - multicast (int): Multicast count
                        - odrops (int): Output drop count
                        - oerrors (int): Output error count
                        - opackets (int): Output packet count
                        - out_bytes (int): Output bytes
        """
        try:
            lan_data = self.get('status/lan')
            if not lan_data:
                return {}
            
            # Get LAN statistics
            lan_stats = self.get('status/lan/stats') or {}
            
            # Get client information using get_lan_clients
            client_data = self.get_lan_clients()
            
            analysis = {
                "total_ipv4_clients": client_data.get("total_ipv4_clients", 0),
                "total_ipv6_clients": client_data.get("total_ipv6_clients", 0),
                "lan_stats": {
                    "bps": lan_stats.get("bps"),
                    "collisions": lan_stats.get("collisions"),
                    "ibps": lan_stats.get("ibps"),
                    "idrops": lan_stats.get("idrops"),
                    "ierrors": lan_stats.get("ierrors"),
                    "imcasts": lan_stats.get("imcasts"),
                    "in_bytes": lan_stats.get("in"),
                    "ipackets": lan_stats.get("ipackets"),
                    "noproto": lan_stats.get("noproto"),
                    "obps": lan_stats.get("obps"),
                    "oerrors": lan_stats.get("oerrors"),
                    "omcasts": lan_stats.get("omcasts"),
                    "opackets": lan_stats.get("opackets"),
                    "out_bytes": lan_stats.get("out"),
                    "timestamp": lan_stats.get("ts")
                },
                "ipv4_clients": client_data.get("ipv4_clients", []),
                "ipv6_clients": client_data.get("ipv6_clients", []),
                "networks": [],
                "devices": []
            }
            
            # Process networks
            networks = lan_data.get("networks", {})
            for network_name, network_info in networks.items():
                network_analysis = {
                    "name": network_name,
                    "display_name": network_info.get("info", {}).get("name"),
                    "ip_address": network_info.get("info", {}).get("ip_address"),
                    "netmask": network_info.get("info", {}).get("netmask"),
                    "broadcast": network_info.get("info", {}).get("broadcast"),
                    "hostname": network_info.get("info", {}).get("hostname"),
                    "type": network_info.get("info", {}).get("type"),
                    "devices": []
                }
                
                # Add network devices
                for device in network_info.get("devices", []):
                    device_info = {
                        "interface": device.get("iface"),
                        "state": device.get("state"),
                        "type": device.get("type"),
                        "uid": device.get("uid")
                    }
                    network_analysis["devices"].append(device_info)
                
                analysis["networks"].append(network_analysis)
            
            # Process devices with statistics
            devices = lan_data.get("devices", {})
            for device_name, device_info in devices.items():
                device_analysis = {
                    "name": device_name,
                    "interface": device_info.get("info", {}).get("iface"),
                    "link_state": device_info.get("status", {}).get("link_state"),
                    "type": device_info.get("info", {}).get("type")
                }
                
                # Add device statistics
                try:
                    device_stats = self.get(f'status/lan/devices/{device_name}/stats')
                    if device_stats:
                        device_analysis["stats"] = {
                            "collisions": device_stats.get("collisions"),
                            "idrops": device_stats.get("idrops"),
                            "ierrors": device_stats.get("ierrors"),
                            "in_bytes": device_stats.get("in"),
                            "ipackets": device_stats.get("ipackets"),
                            "multicast": device_stats.get("multicast"),
                            "odrops": device_stats.get("odrops"),
                            "oerrors": device_stats.get("oerrors"),
                            "opackets": device_stats.get("opackets"),
                            "out_bytes": device_stats.get("out")
                        }
                except Exception as e:
                    self.log(f"Error getting device stats for {device_name}: {e}")
                
                analysis["devices"].append(device_analysis)
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing LAN status: {e}")
            return {"error": str(e)}

    def get_lan_clients(self) -> Dict[str, Any]:
        """Get LAN client information only.
        
        Returns:
            dict: Dictionary containing LAN client information including:
                - total_ipv4_clients (int): Number of connected IPv4 clients
                - total_ipv6_clients (int): Number of connected IPv6 clients
                - ipv4_clients (list): List of connected IPv4 clients including:
                    - ip_address (str): Client IP address
                    - mac (str): Client MAC address
                - ipv6_clients (list): List of connected IPv6 clients including:
                    - ip_address (str): Client IP address
                    - mac (str): Client MAC address
        """
        try:
            lan_data = self.get('status/lan')
            if not lan_data:
                return {}
            
            # Get clients and separate IPv4 and IPv6
            all_clients = lan_data.get("clients", [])
            ipv4_clients = [client for client in all_clients if not client.get("ip_address", "").startswith("fe80::")]
            ipv6_clients = [client for client in all_clients if client.get("ip_address", "").startswith("fe80::")]
            
            return {
                "total_ipv4_clients": len(ipv4_clients),
                "total_ipv6_clients": len(ipv6_clients),
                "ipv4_clients": ipv4_clients,
                "ipv6_clients": ipv6_clients
            }
        except Exception as e:
            self.log(f"Error analyzing LAN clients: {e}")
            return {"error": str(e)}

    def get_lan_networks(self) -> Dict[str, Any]:
        """Get LAN network information only.
        
        Returns:
            dict: Dictionary containing LAN network information including:
                - networks (list): List of network information including:
                    - name (str): Network identifier
                    - display_name (str): Human-readable network name
                    - ip_address (str): Network IP address
                    - netmask (str): Network netmask
                    - broadcast (str): Network broadcast address
                    - hostname (str): Network hostname
                    - type (str): Network type
                    - devices (list): Network devices including:
                        - interface (str): Device interface name
                        - state (str): Device state
                        - type (str): Device type
                        - uid (str): Device unique identifier
        """
        try:
            lan_data = self.get('status/lan')
            if not lan_data:
                return {}
            
            networks = lan_data.get("networks", {})
            network_list = []
            
            for network_name, network_info in networks.items():
                network_analysis = {
                    "name": network_name,
                    "display_name": network_info.get("info", {}).get("name"),
                    "ip_address": network_info.get("info", {}).get("ip_address"),
                    "netmask": network_info.get("info", {}).get("netmask"),
                    "broadcast": network_info.get("info", {}).get("broadcast"),
                    "hostname": network_info.get("info", {}).get("hostname"),
                    "type": network_info.get("info", {}).get("type"),
                    "devices": []
                }
                
                # Add network devices
                for device in network_info.get("devices", []):
                    device_info = {
                        "interface": device.get("iface"),
                        "state": device.get("state"),
                        "type": device.get("type"),
                        "uid": device.get("uid")
                    }
                    network_analysis["devices"].append(device_info)
                
                network_list.append(network_analysis)
            
            return {
                "networks": network_list
            }
        except Exception as e:
            self.log(f"Error analyzing LAN networks: {e}")
            return {"error": str(e)}

    def get_lan_devices(self) -> Dict[str, Any]:
        """Get LAN device information only.
        
        Returns:
            dict: Dictionary containing LAN device information including:
                - devices (list): List of device information including:
                    - name (str): Device name
                    - interface (str): Device interface
                    - link_state (str): Device link state
                    - type (str): Device type
        """
        try:
            lan_data = self.get('status/lan')
            if not lan_data:
                return {}
            
            devices = lan_data.get("devices", {})
            device_list = []
            
            for device_name, device_info in devices.items():
                device_analysis = {
                    "name": device_name,
                    "interface": device_info.get("info", {}).get("iface"),
                    "link_state": device_info.get("status", {}).get("link_state"),
                    "type": device_info.get("info", {}).get("type")
                }
                device_list.append(device_analysis)
            
            return {
                "devices": device_list
            }
        except Exception as e:
            self.log(f"Error analyzing LAN devices: {e}")
            return {"error": str(e)}

    def get_lan_statistics(self) -> Dict[str, Any]:
        """Get overall LAN statistics only.
        
        Returns:
            dict: Dictionary containing LAN statistics including:
                - lan_stats (dict): Overall LAN statistics including:
                    - bps (int): Total bits per second
                    - collisions (int): Collision count
                    - ibps (int): Input bits per second
                    - idrops (int): Input drop count
                    - ierrors (int): Input error count
                    - imcasts (int): Input multicast count
                    - in_bytes (int): Input bytes
                    - ipackets (int): Input packet count
                    - noproto (int): No protocol count
                    - obps (int): Output bits per second
                    - oerrors (int): Output error count
                    - omcasts (int): Output multicast count
                    - opackets (int): Output packet count
                    - out_bytes (int): Output bytes
                    - timestamp (float): Statistics timestamp
        """
        try:
            lan_stats = self.get('status/lan/stats')
            if not lan_stats:
                return {}
            
            return {
                "lan_stats": {
                    "bps": lan_stats.get("bps"),
                    "collisions": lan_stats.get("collisions"),
                    "ibps": lan_stats.get("ibps"),
                    "idrops": lan_stats.get("idrops"),
                    "ierrors": lan_stats.get("ierrors"),
                    "imcasts": lan_stats.get("imcasts"),
                    "in_bytes": lan_stats.get("in"),
                    "ipackets": lan_stats.get("ipackets"),
                    "noproto": lan_stats.get("noproto"),
                    "obps": lan_stats.get("obps"),
                    "oerrors": lan_stats.get("oerrors"),
                    "omcasts": lan_stats.get("omcasts"),
                    "opackets": lan_stats.get("opackets"),
                    "out_bytes": lan_stats.get("out"),
                    "timestamp": lan_stats.get("ts")
                }
            }
        except Exception as e:
            self.log(f"Error analyzing LAN statistics: {e}")
            return {"error": str(e)}

    def get_lan_device_stats(self, device_name: str) -> Dict[str, Any]:
        """Get statistics for a specific LAN device.
        
        Args:
            device_name (str): Name of the LAN device to get statistics for
            
        Returns:
            dict: Dictionary containing device statistics including:
                - device_name (str): Name of the device
                - stats (dict): Device statistics including:
                    - collisions (int): Collision count
                    - idrops (int): Input drop count
                    - ierrors (int): Input error count
                    - in_bytes (int): Input bytes
                    - ipackets (int): Input packet count
                    - multicast (int): Multicast count
                    - odrops (int): Output drop count
                    - oerrors (int): Output error count
                    - opackets (int): Output packet count
                    - out_bytes (int): Output bytes
        """
        try:
            device_stats = self.get(f'status/lan/devices/{device_name}/stats')
            if not device_stats:
                return {"device_name": device_name}
            
            return {
                "device_name": device_name,
                "stats": {
                    "collisions": device_stats.get("collisions"),
                    "idrops": device_stats.get("idrops"),
                    "ierrors": device_stats.get("ierrors"),
                    "in_bytes": device_stats.get("in"),
                    "ipackets": device_stats.get("ipackets"),
                    "multicast": device_stats.get("multicast"),
                    "odrops": device_stats.get("odrops"),
                    "oerrors": device_stats.get("oerrors"),
                    "opackets": device_stats.get("opackets"),
                    "out_bytes": device_stats.get("out")
                }
            }
        except Exception as e:
            self.log(f"Error getting device stats for {device_name}: {e}")
            return {"device_name": device_name, "error": str(e)}

    def get_openvpn_status(self) -> Dict[str, Any]:
        """Get OpenVPN status and return detailed information.
        
        Returns:
            dict: Dictionary containing OpenVPN status information including:
                - tunnels_configured (int): Number of configured tunnels
                - tunnels_active (int): Number of active tunnels
                - stats_available (bool): Whether statistics are available
        """
        try:
            openvpn_data = self.get('status/openvpn')
            if not openvpn_data:
                return {}
            
            analysis = {
                "tunnels_configured": len(openvpn_data.get("tunnels", [])),
                "tunnels_active": len([t for t in openvpn_data.get("tunnels", []) if t.get("status") == "up"]),
                "stats_available": bool(openvpn_data.get("stats"))
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing OpenVPN status: {e}")
            return {"error": str(e)}

    def get_hotspot_status(self) -> Dict[str, Any]:
        """Get hotspot status and return detailed information.
        
        Returns:
            dict: Dictionary containing hotspot status information including:
                - clients_connected (int): Number of connected clients
                - sessions_active (int): Number of active sessions
                - domains_allowed (int): Number of allowed domains
                - hosts_allowed (int): Number of allowed hosts
                - rate_limit_triggered (bool): Whether rate limiting is triggered
        """
        try:
            hotspot_data = self.get('status/hotspot')
            if not hotspot_data:
                return {}
            
            analysis = {
                "clients_connected": len(hotspot_data.get("clients", {})),
                "sessions_active": len(hotspot_data.get("sessions", {})),
                "domains_allowed": len(hotspot_data.get("allowed", {}).get("domains", [])),
                "hosts_allowed": len(hotspot_data.get("allowed", {}).get("hosts", {})),
                "rate_limit_triggered": hotspot_data.get("rateLimitTrigger", False)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing hotspot status: {e}")
            return {"error": str(e)}

    def get_obd_status(self) -> Dict[str, Any]:
        """Get OBD status and return detailed information.
        
        Returns:
            dict: Dictionary containing OBD status information including:
                - adapter_configured (bool): Whether OBD adapter is configured
                - adapter_connected (bool): Whether OBD adapter is connected
                - vehicle_connected (bool): Whether vehicle is connected
                - pids_supported (int): Number of supported PIDs
                - pids_enabled (int): Number of enabled PIDs
                - ignition_status (str): Vehicle ignition status
                - pids (list): List of PID information including:
                    - config_name (str): PID configuration name
                    - enabled (bool): Whether PID is enabled
                    - last_value (str): Last value received for this PID
                    - name (str): PID name
                    - pid (int): PID identifier
                    - supported (bool): Whether PID is supported by vehicle
                    - units (str): Units for PID values
                    - update_interval (int): Update interval in milliseconds
                    - values (list): Historical values for this PID
        """
        try:
            obd_data = self.get('status/obd')
            if not obd_data:
                return {}
            
            adapter = obd_data.get("adapter", {})
            vehicle = obd_data.get("vehicle", {})
            
            # Process PIDs data
            pids_data = obd_data.get("pids", [])
            pids_list = []
            
            for pid in pids_data:
                pid_info = {
                    "config_name": pid.get("config_name"),
                    "enabled": pid.get("enabled", False),
                    "last_value": pid.get("last_value", ""),
                    "name": pid.get("name"),
                    "pid": pid.get("pid"),
                    "supported": pid.get("supported", False),
                    "units": pid.get("units"),
                    "update_interval": pid.get("update_interval"),
                    "values": pid.get("values", [])
                }
                pids_list.append(pid_info)
            
            analysis = {
                "adapter_configured": adapter.get("configured", False),
                "adapter_connected": adapter.get("connected", False),
                "vehicle_connected": vehicle.get("ext_tool") != "Disconnected",
                "pids_supported": len([pid for pid in pids_data if pid.get("supported", False)]),
                "pids_enabled": len([pid for pid in pids_data if pid.get("enabled", False)]),
                "ignition_status": vehicle.get("ign_status"),
                "pids": pids_list
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing OBD status: {e}")
            return {"error": str(e)}

    def get_qos_status(self) -> Dict[str, Any]:
        """Get QoS status and return detailed information.
        
        Returns:
            dict: Dictionary containing QoS status information including:
                - qos_enabled (bool): Whether QoS is enabled
                - queues_configured (int): Number of configured queues
                - queues_active (int): Number of active queues
                - total_packets (int): Total packets processed
        """
        try:
            qos_data = self.get('status/qos')
            if not qos_data:
                return {}
            
            queues = qos_data.get("queues", [])
            analysis = {
                "qos_enabled": qos_data.get("enabled", False),
                "queues_configured": len(queues),
                "queues_active": len([q for q in queues if q.get("ipkts", 0) > 0 or q.get("opkts", 0) > 0]),
                "total_packets": sum(q.get("ipkts", 0) + q.get("opkts", 0) for q in queues)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing QoS status: {e}")
            return {"error": str(e)}

    def get_firewall_status(self) -> Dict[str, Any]:
        """Get firewall status and return detailed information.
        
        Returns:
            dict: Dictionary containing firewall status information including:
                - connections_tracked (int): Number of tracked connections
                - state_timeouts (dict): State timeout configurations
                - hitcounters (list): List of firewall rule hit counters
        """
        try:
            firewall_data = self.get('status/firewall')
            if not firewall_data:
                return {}
            
            connections = firewall_data.get("connections", [])
            hitcounters = firewall_data.get("hitcounter", [])
            
            analysis = {
                "connections_tracked": len(connections),
                "state_timeouts": firewall_data.get("state_timeouts", {}),
                "hitcounters": []
            }
            
            for hc in hitcounters:
                hc_info = {
                    "name": hc.get("name"),
                    "packet_count": hc.get("packet_count", 0),
                    "byte_count": hc.get("bytes_count", 0),
                    "default_action": hc.get("default_action")
                }
                analysis["hitcounters"].append(hc_info)
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing firewall status: {e}")
            return {"error": str(e)}

    def get_dns_status(self) -> Dict[str, Any]:
        """Get DNS status and return detailed information.
        
        Returns:
            dict: Dictionary containing DNS status information including:
                - cache_entries (int): Number of cache entries
                - cache_size (int): Cache size
                - servers_configured (int): Number of configured DNS servers
                - queries_forwarded (int): Number of forwarded queries
        """
        try:
            dns_data = self.get('status/dns')
            if not dns_data:
                return {}
            
            cache = dns_data.get("cache", {})
            servers = cache.get("servers", [])
            
            analysis = {
                "cache_entries": len(cache.get("entries", [])),
                "cache_size": cache.get("size", 0),
                "servers_configured": len(servers),
                "queries_forwarded": cache.get("forwarded", 0)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing DNS status: {e}")
            return {"error": str(e)}

    def get_dhcp_status(self) -> Dict[str, Any]:
        """Get DHCP status and return detailed information.
        
        Returns:
            dict: Dictionary containing DHCP status information including:
                - total_leases (int): Total number of DHCP leases
                - active_leases (int): Number of active leases
                - leases_by_interface (dict): Leases grouped by interface
                - leases_by_network (dict): Leases grouped by network
                - leases (list): List of all DHCP leases including:
                    - client_id (str): Client identifier
                    - expire (int): Lease expiration time
                    - hostname (str): Client hostname
                    - iface (str): Interface name
                    - iface_type (str): Interface type (ethernet, wireless, etc.)
                    - ip_address (str): Assigned IP address
                    - mac (str): Client MAC address
                    - network (str): Network name
                    - ssid (str): SSID for wireless clients
        """
        try:
            dhcp_data = self.get('status/dhcpd')
            if not dhcp_data:
                return {}
            
            leases = dhcp_data.get("leases", [])
            current_time = int(time.time())
            
            # Group leases by interface and network
            leases_by_interface = {}
            leases_by_network = {}
            
            for lease in leases:
                # Group by interface
                iface = lease.get("iface", "unknown")
                if iface not in leases_by_interface:
                    leases_by_interface[iface] = []
                leases_by_interface[iface].append(lease)
                
                # Group by network
                network = lease.get("network", "unknown")
                if network not in leases_by_network:
                    leases_by_network[network] = []
                leases_by_network[network].append(lease)
            
            # Count active leases (not expired)
            active_leases = len([lease for lease in leases if lease.get("expire", 0) > current_time])
            
            analysis = {
                "total_leases": len(leases),
                "active_leases": active_leases,
                "leases_by_interface": leases_by_interface,
                "leases_by_network": leases_by_network,
                "leases": leases
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing DHCP status: {e}")
            return {"error": str(e)}

    def get_wan_primary_device(self) -> Optional[str]:
        """Get the WAN primary device identifier.
        
        Returns:
            str: Primary WAN device identifier, or None if not available
        """
        try:
            primary_device = self.get('status/wan/primary_device')
            return primary_device
        except Exception as e:
            self.log(f"Error retrieving WAN primary device: {e}")
            return None

    def ping_host(self, host: str, count: int = 4, timeout: float = 15.0, 
                  interval: float = 0.5, packet_size: int = 56, 
                  interface: str = None, bind_ip: bool = False) -> Optional[Dict[str, Any]]:
        """Ping a host using the router's diagnostic tools.
        
        Args:
            host: Target hostname or IP address
            count: Number of ping packets to send (default: 4)
            timeout: Timeout in seconds (default: 15.0)
            interval: Interval between packets in seconds (default: 0.5)
            packet_size: Size of ping packets in bytes (default: 56)
            interface: Network interface to use (default: None - uses WAN primary device)
            bind_ip: Whether to bind to specific IP (default: False)
            
        Returns:
            dict: Ping results including statistics with keys:
                - tx: number of pings transmitted
                - rx: number of pings received  
                - loss: percentage of lost pings
                - min: minimum round trip time in milliseconds
                - max: maximum round trip time in milliseconds
                - avg: average round trip time in milliseconds
                - error: error message if not successful
        """
        
        try:
            # Initialize ping parameters - exact UI approach (minimal parameters)
            ping_params = {
                "host": host,
                "size": packet_size,
                "df": True,  # UI uses true, not "do"
                "srcaddr": ""  # UI uses empty string, not null
            }
            
            # Initialize result dictionary with parameters
            pingstats = dict(ping_params)
            
            # Start ping process - match UI approach (simpler)
            self.put('control/ping/start', ping_params)
            
            # Wait for completion, checking status periodically
            result = None
            try_count = 0
            max_tries = 30
            
            while try_count < max_tries:
                result = self.get('control/ping')
                if result and result.get('status') in ["error", "done"]:
                    break
                time.sleep(0.5)
                try_count += 1
            
            if try_count == max_tries:
                pingstats['error'] = "No Results - Execution Timed Out"
            elif result and result.get('status') == "error":
                pingstats['error'] = result.get('result', 'Unknown error occurred')
            elif result and result.get('result'):
                # Parse ping results from text output
                try:
                    parsedresults = result.get('result').split('\n')
                    
                    # Check if we have statistics (ping completed)
                    has_stats = any('---' in line for line in parsedresults)
                    
                    if has_stats:
                        # Parse statistics from completed ping
                        stats_line = None
                        rtt_line = None
                        
                        # Find the statistics and RTT lines
                        for i, line in enumerate(parsedresults):
                            if 'packets transmitted' in line and 'received' in line:
                                stats_line = line
                            elif 'round-trip' in line and 'min/avg/max' in line:
                                rtt_line = line
                        
                        if stats_line:
                            # Extract tx, rx, loss from statistics line
                            tx_match = re.search(r'(\d+)\s+packets transmitted', stats_line)
                            rx_match = re.search(r'(\d+)\s+received', stats_line)
                            loss_match = re.search(r'(\d+\.?\d*)% packet loss', stats_line)
                            
                            if tx_match:
                                pingstats['tx'] = int(tx_match.group(1))
                            if rx_match:
                                pingstats['rx'] = int(rx_match.group(1))
                            if loss_match:
                                pingstats['loss'] = float(loss_match.group(1))
                        
                        if rtt_line:
                            # Extract min, avg, max RTT
                            rtt_match = re.search(r'min/avg/max\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)', rtt_line)
                            if rtt_match:
                                pingstats['min'] = float(rtt_match.group(1))
                                pingstats['avg'] = float(rtt_match.group(2))
                                pingstats['max'] = float(rtt_match.group(3))
                    else:
                        # Parse individual ping responses (ping still running)
                        ping_responses = [line for line in parsedresults if 'icmp_seq=' in line and 'time=' in line]
                        if ping_responses:
                            pingstats['tx'] = len(ping_responses)
                            pingstats['rx'] = len(ping_responses)
                            pingstats['loss'] = 0.0
                            
                            # Calculate RTT statistics from individual responses
                            rtt_times = []
                            for response in ping_responses:
                                try:
                                    time_part = response.split('time=')[1].split(' ms')[0]
                                    rtt_times.append(float(time_part))
                                except:
                                    pass
                            
                            if rtt_times:
                                pingstats['min'] = min(rtt_times)
                                pingstats['max'] = max(rtt_times)
                                pingstats['avg'] = sum(rtt_times) / len(rtt_times)
                        else:
                            pingstats['error'] = 'No ping responses found'
                    
                except Exception as e:
                    self.log(f'Exception parsing ping results: {e}')
                    # Don't override successful ping results with parsing errors
                    if 'tx' not in pingstats:
                        pingstats['error'] = f'Failed to parse results: {e}'
            else:
                pingstats['error'] = 'No results received'
            
            return pingstats
            
        except Exception as e:
            self.log(f"Error pinging host {host}: {e}")
            return {'error': str(e)}

    def traceroute_host(self, host: str, max_hops: int = 30, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Perform traceroute to a host using the router's diagnostic tools.
        
        Args:
            host: Target hostname or IP address
            max_hops: Maximum number of hops (default: 30)
            timeout: Timeout per hop in seconds (default: 5.0)
            
        Returns:
            dict: Traceroute results including hop information
        """
        
        try:
            # Initialize traceroute parameters - minimal approach like ping
            traceroute_params = {
                "host": host
            }
            
            # Initialize result dictionary with parameters
            traceroute_stats = dict(traceroute_params)
            
            # Start traceroute process - same approach as ping
            self.put('control/traceroute/start', traceroute_params)
            
            # Wait for completion, checking status periodically
            result = None
            try_count = 0
            max_tries = 60  # Traceroute can take longer than ping
            
            while try_count < max_tries:
                result = self.get('control/traceroute')
                if result and result.get('status') in ["error", "done", "not started"]:
                    break
                time.sleep(1.0)  # Check every second for traceroute
                try_count += 1
            
            if try_count == max_tries:
                traceroute_stats['error'] = "No Results - Execution Timed Out"
            elif result and result.get('status') == "error":
                traceroute_stats['error'] = result.get('result', 'Unknown error occurred')
            elif result and result.get('result'):
                # Parse traceroute results from text output
                try:
                    traceroute_result = result.get('result')
                    
                    # Handle both string and array formats
                    if isinstance(traceroute_result, list):
                        # API returns array of strings
                        traceroute_output = ''.join(traceroute_result)
                    else:
                        # API returns single string
                        traceroute_output = traceroute_result
                    
                    traceroute_stats['raw_output'] = traceroute_output
                    
                    # Parse hops from traceroute output with detailed latency metrics
                    lines = traceroute_output.split('\n')
                    hops = []
                    hop_details = []
                    all_latencies = []
                    
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('traceroute to'):
                            # Parse hop information
                            if 'ms' in line or '*' in line:
                                hops.append(line)
                                
                                # Parse detailed hop information
                                hop_info = self._parse_traceroute_hop(line)
                                if hop_info:
                                    hop_details.append(hop_info)
                                    # Collect all valid latencies for overall statistics
                                    if hop_info.get('latencies'):
                                        all_latencies.extend(hop_info['latencies'])
                    
                    traceroute_stats['hops'] = hops
                    traceroute_stats['hop_count'] = len(hops)
                    traceroute_stats['hop_details'] = hop_details
                    
                    # Calculate overall latency statistics
                    if all_latencies:
                        traceroute_stats['latency_stats'] = {
                            'min': min(all_latencies),
                            'max': max(all_latencies),
                            'avg': sum(all_latencies) / len(all_latencies),
                            'total_samples': len(all_latencies)
                        }
                    
                except Exception as e:
                    self.log(f'Exception parsing traceroute results: {e}')
                    # Don't override successful traceroute results with parsing errors
                    if 'hops' not in traceroute_stats:
                        traceroute_stats['error'] = f'Failed to parse results: {e}'
            else:
                traceroute_stats['error'] = 'No results received'
            
            return traceroute_stats
            
        except Exception as e:
            self.log(f"Error performing traceroute to {host}: {e}")
            return {'error': str(e)}

    def _parse_traceroute_hop(self, hop_line: str) -> Optional[Dict[str, Any]]:
        """Parse individual traceroute hop line for detailed metrics.
        
        Args:
            hop_line: Raw traceroute hop line (e.g., "1 192.168.1.1 (192.168.1.1)  1.234 ms  1.567 ms  1.890 ms")
            
        Returns:
            dict: Parsed hop information with latencies and IPs
        """
        
        try:
            # Extract hop number
            hop_match = re.match(r'^\s*(\d+)', hop_line)
            if not hop_match:
                return None
                
            hop_num = int(hop_match.group(1))
            
            # Extract IP addresses (both with and without hostnames)
            ip_pattern = r'(\d+\.\d+\.\d+\.\d+)'
            ips = re.findall(ip_pattern, hop_line)
            
            # Extract latency values
            latency_pattern = r'(\d+\.?\d*)\s*ms'
            latencies = [float(match) for match in re.findall(latency_pattern, hop_line)]
            
            # Count timeouts (*)
            timeouts = hop_line.count('*')
            
            hop_info = {
                'hop_number': hop_num,
                'ips': ips,
                'latencies': latencies,
                'timeouts': timeouts,
                'total_probes': len(latencies) + timeouts
            }
            
            # Calculate hop-specific statistics
            if latencies:
                hop_info['latency_stats'] = {
                    'min': min(latencies),
                    'max': max(latencies),
                    'avg': sum(latencies) / len(latencies),
                    'samples': len(latencies)
                }
            
            # Determine primary IP (first non-timeout IP)
            hop_info['primary_ip'] = ips[0] if ips else None
            
            return hop_info
            
        except Exception as e:
            self.log(f'Error parsing hop line "{hop_line}": {e}')
            return None

    def speed_test(self, host: str = "", interface: str = "", duration: int = 5, 
                   packet_size: int = 0, port: int = None, protocol: str = "tcp",
                   direction: str = "both") -> Optional[Dict[str, Any]]:
        """Perform comprehensive network speed test using netperf with both upload and download.
        
        Args:
            host: Target host for speed test (empty for auto-detect)
            interface: Network interface to use (empty for auto-detect)
            duration: Test duration in seconds (default: 5)
            packet_size: Packet size in bytes (0 for default)
            port: Port number (None for default)
            protocol: Protocol to use - "tcp" or "udp" (default: "tcp")
            direction: Test direction - "recv", "send", "both", or "rr" (default: "both")
            
        Returns:
            dict: Speed test results with download_bps, upload_bps, and latency
        """
        
        try:
            # If no interface specified, get the WAN primary device interface
            if not interface:
                primary_device = self.get_wan_primary_device()
                if primary_device:
                    # Get the interface name for the primary device
                    interface = self.get(f'status/wan/{primary_device}/info/iface')
                else:
                    interface = "any"
            
            # Initialize results
            results = {
                'download_bps': 0,
                'upload_bps': 0,
                'latency_ms': 0,
                'test_duration': duration,
                'interface': interface,
                'host': host,
                'protocol': protocol
            }
            
            # Build base speedtest parameters
            speedtest_params = {
                "input": {
                    "options": {
                        "limit": {
                            "size": packet_size,
                            "time": duration
                        },
                        "port": port,
                        "fwport": None,
                        "host": host,
                        "ifc_wan": interface,
                        "tcp": protocol == "tcp",
                        "udp": protocol == "udp",
                        "send": False,
                        "recv": True,
                        "rr": False
                    },
                    "tests": None
                },
                "run": 1
            }
            
            # Clear any existing netperf state
            self.put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)  # Give time for state to clear
            
            # Run download test if direction is "recv" or "both"
            if direction in ["recv", "both"]:
                self.log("Running download test...")
                download_result = self._run_speed_test_with_params(speedtest_params)
                if download_result and 'tcp_down' in download_result:
                    tcp_down = download_result['tcp_down']
                    if tcp_down and 'THROUGHPUT' in tcp_down:
                        throughput = float(tcp_down.get('THROUGHPUT', 0))
                        throughput_units = tcp_down.get('THROUGHPUT_UNITS', '')
                        results['download_bps'] = self._convert_to_bps(throughput, throughput_units)
                        self.log(f"Download result: {results['download_bps']} bps")
                
                # Add delay between tests to prevent caching issues
                if direction == "both":
                    time.sleep(3)  # Increased delay
            
            # Run upload test if direction is "send" or "both"
            if direction in ["send", "both"]:
                # Clear netperf state again before upload test
                self.put('/state/system/netperf', {"run_count": 0})
                time.sleep(1)  # Give time for state to clear
                
                # Modify parameters for upload test
                speedtest_params["input"]["options"]["send"] = True
                speedtest_params["input"]["options"]["recv"] = False
                
                self.log("Running upload test...")
                upload_result = self._run_speed_test_with_params(speedtest_params)
                if upload_result and 'tcp_up' in upload_result:
                    tcp_up = upload_result['tcp_up']
                    if tcp_up and 'THROUGHPUT' in tcp_up:
                        throughput = float(tcp_up.get('THROUGHPUT', 0))
                        throughput_units = tcp_up.get('THROUGHPUT_UNITS', '')
                        results['upload_bps'] = self._convert_to_bps(throughput, throughput_units)
                        self.log(f"Upload result: {results['upload_bps']} bps")
            
            return results
            
        except Exception as e:
            self.log(f"Error performing speed test: {e}")
            return {'error': str(e)}
    
    def _run_speed_test_with_params(self, speedtest_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run a speed test with the given parameters and return raw results.
        
        Args:
            speedtest_params: Speed test parameters
            
        Returns:
            dict: Raw speed test results
        """
        try:
            # Start speedtest
            start_result = self.put('control/netperf', speedtest_params)
            
            if not start_result:
                return {'error': 'Failed to start speedtest'}
            
            # Wait for completion, checking status periodically
            result = None
            try_count = 0
            duration = speedtest_params['input']['options']['limit']['time']
            max_tries = duration + 10  # Wait a bit longer than test duration
            
            while try_count < max_tries:
                result = self.get('control/netperf/output')
                if result and result.get('status') in ['complete', 'error']:
                    break
                time.sleep(1.0)
                try_count += 1
            
            if try_count == max_tries:
                return {'error': 'Speedtest timed out'}
            
            if result.get('status') == 'error':
                return {'error': 'Speedtest failed'}
            
            # Get the results from the performance results path
            if result and result.get('results_path'):
                results_path = result['results_path']
                perf_results = self.get(results_path.lstrip('/'))
                return perf_results
            else:
                return {'error': 'No performance results found'}
            
        except Exception as e:
            self.log(f"Error performing speed test: {e}")
            return {'error': str(e)}
    
    def _convert_to_bps(self, throughput: float, throughput_units: str) -> float:
        """Convert throughput value to bits per second.
        
        Args:
            throughput: Throughput value
            throughput_units: Units of the throughput value
            
        Returns:
            float: Throughput in bits per second
        """
        if '10^6bits/s' in throughput_units:
            # Convert from Mbps to bps
            return throughput * 1000000
        elif 'bits/s' in throughput_units:
            # Already in bps
            return throughput
        elif 'bytes/s' in throughput_units:
            # Convert from bytes/s to bps
            return throughput * 8
        else:
            # Default to treating as bps
            return throughput

    def stop_speed_test(self) -> Optional[Dict[str, Any]]:
        """Stop any running speed test."""
        try:
            result = self.put('control/netperf/stop', '')
            return {'result': result}
        except Exception as e:
            self.log(f"Error stopping speed test: {e}")
            return None

    def start_packet_capture(self, interface: str = "any", filter: str = "", 
                            count: int = 20, timeout: int = 600,
                            wifichannel: str = "", wifichannelwidth: str = "", 
                            wifiextrachannel: str = "", url: str = "") -> Optional[Dict[str, Any]]:
        """Start packet capture using tcpdump API.
        
        Args:
            interface: Network interface to capture on (e.g., "mdm-9a724d09", "mon0", "any")
            filter: BPF filter expression (e.g., "net 192.168.0.0/24 and tcp and not port 80")
            count: Number of packets to capture (default: 20, 0 = unlimited)
            timeout: Capture timeout in seconds (default: 600, 0 = unlimited)
            wifichannel: WiFi channel for wireless captures (default: "")
            wifichannelwidth: WiFi channel width (default: "")
            wifiextrachannel: WiFi extra channel (default: "")
            url: Capture URL endpoint (default: "" - use router default behavior)
            
        Note:
            If both count=0 and timeout=0, the capture will stream forever until interrupted.
            This is useful for continuous monitoring or thread-based captures.
            Use at least one limit (count > 0 or timeout > 0) for finite captures.
            
        Returns:
            dict: Packet capture start result with download URL
        """
        
        try:
            # Log infinite capture mode
            if count == 0 and timeout == 0:
                self.log("INFO: Infinite capture mode - will stream forever until interrupted")
                self.log("Use this mode for continuous monitoring or thread-based captures")
            
            # Generate timestamp-based filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}.pcap"
            
            # Build tcpdump API URL with parameters
            params = {
                "iface": interface,
                "args": filter,
                "wifichannel": wifichannel,
                "wifichannelwidth": wifichannelwidth,
                "wifiextrachannel": wifiextrachannel,
                "timeout": timeout,
                "count": count,
                "url": url
            }
            
            # Create the API endpoint URL with query parameters
            query_string = urllib.parse.urlencode(params)
            api_url = f"tcpdump/{filename}?{query_string}"
            
            # Start packet capture by making GET request to the tcpdump API
            # This will start the capture and return the pcap file
            capture_result = self.get(api_url)
            
            # Handle the response properly
            if isinstance(capture_result, tuple):
                # If it's a tuple, extract the data part
                capture_result = capture_result[1] if len(capture_result) > 1 else capture_result[0]
            
            return {
                'parameters': params,
                'filename': filename,
                'api_url': api_url,
                'capture_result': capture_result,
                'download_url': f"{self._get_cached_credentials()[0]}/api/{api_url}?iface={interface}&args={filter}&wifichannel={wifichannel}&wifichannelwidth={wifichannelwidth}&wifiextrachannel={wifiextrachannel}&timeout={timeout}&count={count}&url={url}"
            }
            
        except Exception as e:
            self.log(f"Error starting packet capture: {e}")
            return {'error': str(e)}

    def stop_packet_capture(self) -> Optional[Dict[str, Any]]:
        """Stop running packet capture.
        
        Note: The tcpdump API doesn't have a specific stop endpoint.
        Captures are typically stopped by timeout or packet count limits.
        
        Returns:
            dict: Stop result (informational)
        """
        try:
            # The tcpdump API doesn't have a stop endpoint
            # Captures are controlled by timeout and count parameters
            return {
                'message': 'Packet capture stop not supported by API',
                'note': 'Captures are controlled by timeout and count parameters',
                'suggestion': 'Use shorter timeout or lower count for shorter captures'
            }
            
        except Exception as e:
            self.log(f"Error stopping packet capture: {e}")
            return {'error': str(e)}

    def get_available_interfaces(self) -> Optional[Dict[str, Any]]:
        """Get available network interfaces for packet capture.
        
        Returns:
            dict: Available interfaces with their types and status
        """
        try:
            # Get WAN devices
            wan_status = self.get('status/wan')
            devices = wan_status.get('devices', {})
            
            interfaces = {}
            
            # Add WAN interfaces
            for device_name, device_data in devices.items():
                if isinstance(device_data, dict) and 'info' in device_data:
                    info = device_data['info']
                    iface = info.get('iface')
                    device_type = info.get('type', 'unknown')
                    status = device_data.get('status', {})
                    connection_state = status.get('connection_state', 'unknown')
                    
                    interfaces[iface] = {
                        'device_name': device_name,
                        'type': device_type,
                        'connection_state': connection_state,
                        'description': f"{device_type} interface ({device_name})"
                    }
            
            # Add common monitoring interfaces
            interfaces['mon0'] = {
                'device_name': 'mon0',
                'type': 'wifi_monitor',
                'connection_state': 'monitor',
                'description': '2.4GHz WiFi monitor interface'
            }
            
            interfaces['mon1'] = {
                'device_name': 'mon1', 
                'type': 'wifi_monitor',
                'connection_state': 'monitor',
                'description': '5GHz WiFi monitor interface'
            }
            
            interfaces['any'] = {
                'device_name': 'any',
                'type': 'any',
                'connection_state': 'any',
                'description': 'Capture on all interfaces'
            }
            
            return {
                'interfaces': interfaces,
                'total_count': len(interfaces)
            }
            
        except Exception as e:
            self.log(f"Error getting available interfaces: {e}")
            return {'error': str(e)}

    def download_packet_capture(self, filename: str, local_path: str = None, capture_params: dict = None) -> Optional[Dict[str, Any]]:
        """Download a packet capture file.
        
        Args:
            filename: Name of the pcap file to download
            local_path: Local path to save the file (default: current directory)
            capture_params: Parameters used in the original capture (optional)
            
        Returns:
            dict: Download result with file path
        """

        
        try:
            if not local_path:
                local_path = f"./{filename}"
            
            # Always use HTTP download - the tcpdump API serves files on-demand
            # Whether running locally or remotely, we need to use the HTTP API
            if self.ncos:
                # Running on router - use localhost
                device_ip = "127.0.0.1"
            else:
                # Running remotely - use cached device IP
                device_ip = self._get_cached_credentials()[0]  # device_ip is at index 0
            
            # Build the download URL with the same parameters used in the capture
            # Based on the HAR file, we need to include the capture parameters
            if capture_params:
                # Use the actual parameters from the capture
                params = urllib.parse.urlencode(capture_params)
                download_url = f"http://{device_ip}/api/tcpdump/{filename}?{params}"
            else:
                # Default parameters if none provided
                download_url = f"http://{device_ip}/api/tcpdump/{filename}?iface=any&args=tcp&wifichannel=&wifichannelwidth=&wifiextrachannel=&timeout=30&count=5"
            
            # Add authentication for the download
            
            # Create a password manager for authentication
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, f"http://{device_ip}", "admin", "1q1q1q1q1q")
            handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            opener = urllib.request.build_opener(handler)
            urllib.request.install_opener(opener)
            
            # Download the file
            urllib.request.urlretrieve(download_url, local_path)
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            return {
                'filename': filename,
                'local_path': local_path,
                'download_url': download_url,
                'file_size': file_size,
                'success': True
            }
            
        except Exception as e:
            self.log(f"Error downloading packet capture: {e}")
            return {'error': str(e)}

    def start_streaming_capture(self, interface: str = "any", filter: str = "", 
                               wifichannel: str = "", wifichannelwidth: str = "", 
                               wifiextrachannel: str = "", url: str = "") -> Optional[Dict[str, Any]]:
        """Start a streaming packet capture that runs forever until interrupted.
        
        This is a convenience method for continuous monitoring or thread-based captures.
        
        Args:
            interface: Network interface to capture on (e.g., "mdm-9a724d09", "mon0", "any")
            filter: BPF filter expression (e.g., "net 192.168.0.0/24 and tcp and not port 80")
            wifichannel: WiFi channel for wireless captures (default: "")
            wifichannelwidth: WiFi channel width (default: "")
            wifiextrachannel: WiFi extra channel (default: "")
            url: Capture URL endpoint (default: "" - use router default behavior)
            
        Returns:
            dict: Streaming capture start result with download URL
        """
        return self.start_packet_capture(
            interface=interface,
            filter=filter,
            count=0,  # Unlimited packets
            timeout=0,  # Unlimited time
            wifichannel=wifichannel,
            wifichannelwidth=wifichannelwidth,
            wifiextrachannel=wifiextrachannel,
            url=url
        )

    def get_packet_capture_status(self) -> Optional[Dict[str, Any]]:
        """Get packet capture status.
        
        Returns:
            dict: Current capture status
        """
        try:
            # Get tcpdump status
            status = self.get('control/system/tcpdump')
            
            # Handle the response properly
            if isinstance(status, tuple):
                # If it's a tuple, extract the data part
                status = status[1] if len(status) > 1 else status[0]
            
            return {
                'status': status
            }
            
        except Exception as e:
            self.log(f"Error getting packet capture status: {e}")
            return None

    def start_file_server(self, folder_path: str = "files", port: int = 8000, 
                         host: str = "0.0.0.0", title: str = "File Download") -> Optional[Dict[str, Any]]:
        """Start a modern web file server for downloading files from a folder.
        
        Args:
            folder_path: Path to the folder to serve files from (default: "files")
                        Always uses subdirectories from current working directory
            port: Port to run the server on (default: 8000)
            host: Host to bind to (default: "0.0.0.0" - all interfaces)
            title: Title for the web page (default: "File Download")
            
        Returns:
            dict: Server start result with URL and status
        """
        
        try:
            # Ensure folder_path is relative to current working directory
            if os.path.isabs(folder_path):
                # If absolute path provided, use just the basename as subdirectory
                folder_path = os.path.basename(folder_path)
            
            # Create full path relative to current working directory
            full_folder_path = os.path.join(os.getcwd(), folder_path)
            
            # Ensure folder exists
            if not os.path.exists(full_folder_path):
                os.makedirs(full_folder_path, exist_ok=True)
            
            class FileServerHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=full_folder_path, **kwargs)
                
                def do_GET(self):
                    if self.path == '/':
                        self.send_file_listing()
                    else:
                        super().do_GET()
                
                def send_file_listing(self):
                    """Send a modern file listing page"""
                    try:
                        files = []
                        total_size = 0
                        
                        for item in os.listdir(full_folder_path):
                            item_path = os.path.join(full_folder_path, item)
                            if os.path.isfile(item_path):
                                stat = os.stat(item_path)
                                size = stat.st_size
                                mtime = datetime.fromtimestamp(stat.st_mtime)
                                files.append({
                                    'name': item,
                                    'size': size,
                                    'size_human': self.format_size(size),
                                    'modified': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                                    'type': mimetypes.guess_type(item)[0] or 'application/octet-stream'
                                })
                                total_size += size
                        
                        # Sort by modification time (newest first)
                        files.sort(key=lambda x: x['modified'], reverse=True)
                        
                        html = self.generate_file_listing_html(files, total_size)
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(html.encode('utf-8'))))
                        self.end_headers()
                        self.wfile.write(html.encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"Error listing files: {e}")
                
                def format_size(self, size):
                    """Format file size in human readable format"""
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size < 1024.0:
                            return f"{size:.1f} {unit}"
                        size /= 1024.0
                    return f"{size:.1f} TB"
                
                def generate_file_listing_html(self, files, total_size):
                    """Generate Ericsson-inspired HTML for file listing"""
                    file_count = len(files)
                    total_size_human = self.format_size(total_size)
                    
                    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #ffffff;
            color: #1a1a1a;
            line-height: 1.6;
            min-height: 100vh;
        }}
        .header {{
            background: #ffffff;
            border-bottom: 1px solid #e5e5e5;
            padding: 2rem;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5rem;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 0.5rem;
        }}
        .header p {{
            color: #666666;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #f8f9fa;
            border: 1px solid #e5e5e5;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            color: #1a1a1a;
            font-weight: 500;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #ffffff;
        }}
        .content {{
            padding: 2rem;
        }}
        .file-list {{
            display: grid;
            gap: 1rem;
        }}
        .file-item {{
            display: flex;
            align-items: center;
            padding: 1.5rem;
            background: #ffffff;
            border: 1px solid #e5e5e5;
            border-radius: 8px;
            transition: all 0.2s ease;
        }}
        .file-item:hover {{
            border-color: #0066cc;
            box-shadow: 0 4px 12px rgba(0, 102, 204, 0.1);
            transform: translateY(-1px);
        }}
        .file-icon {{
            width: 48px;
            height: 48px;
            background: #f8f9fa;
            border: 1px solid #e5e5e5;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666666;
            font-size: 1.2rem;
            margin-right: 1rem;
            flex-shrink: 0;
        }}
        .file-info {{
            flex: 1;
        }}
        .file-name {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 0.25rem;
            word-break: break-all;
        }}
        .file-meta {{
            color: #666666;
            font-size: 0.9rem;
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}
        .download-btn {{
            background: #0066cc;
            color: white;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            font-size: 0.9rem;
            transition: all 0.2s ease;
            display: inline-block;
        }}
        .download-btn:hover {{
            background: #0052a3;
            transform: translateY(-1px);
        }}
        .empty {{
            text-align: center;
            padding: 4rem 2rem;
            color: #666666;
        }}
        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
        .empty h3 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 0.5rem;
        }}
        .empty p {{
            color: #666666;
        }}
        .empty code {{
            background: #f8f9fa;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9rem;
        }}
        @media (max-width: 768px) {{
            .header {{ padding: 1.5rem 1rem; }}
            .header h1 {{ font-size: 2rem; }}
            .content {{ padding: 1rem; }}
            .file-item {{ flex-direction: column; text-align: center; }}
            .file-icon {{ margin: 0 0 1rem 0; }}
            .file-meta {{ justify-content: center; }}
            .stats {{ flex-direction: column; align-items: center; gap: 1rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Download files from the server</p>
            <div class="stats">
                <div class="stat">{file_count} files</div>
                <div class="stat">{total_size_human}</div>
            </div>
        </div>
        <div class="content">
"""
                    
                    if files:
                        html += '<div class="file-list">'
                        for file in files:
                            html += f"""
            <div class="file-item">
                <div class="file-icon">📄</div>
                <div class="file-info">
                    <div class="file-name">{file['name']}</div>
                    <div class="file-meta">
                        <span>📅 {file['modified']}</span>
                        <span>📏 {file['size_human']}</span>
                        <span>🏷️ {file['type']}</span>
                    </div>
                </div>
                <a href="{file['name']}" class="download-btn" download>⬇️ Download</a>
            </div>"""
                        html += '</div>'
                    else:
                        html += f"""
            <div class="empty">
                <div class="empty-icon">📂</div>
                <h3>No files found</h3>
                <p>Upload some files to the <code>{folder_path}</code> directory to see them here.</p>
            </div>"""
                    
                    html += """
        </div>
    </div>
</body>
</html>"""
                    return html
                
                def log_message(self, format, *args):
                    # Use print for file server logging
                    print(f"FileServer: {format % args}")
            
            # Start server in background thread
            def run_server():
                try:
                    with socketserver.TCPServer((host, port), FileServerHandler) as httpd:
                        httpd.serve_forever()
                except Exception as e:
                    self.log(f"File server error: {e}")
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            return {
                'status': 'started',
                'url': f'http://{host}:{port}',
                'folder_path': full_folder_path,
                'port': port,
                'host': host,
                'title': title
            }
        except Exception as e:
            self.log(f"Error starting file server: {e}")
            return {'error': str(e)}

    def create_user(self, username: str, password: str, group: str = "admin") -> dict:
        """Create a new user on the router.
        
        Args:
            username (str): The username for the new user
            password (str): The password for the new user
            group (str): The group for the user (default: "admin")
            
        Returns:
            dict: Result of the user creation operation
        """
        try:
            user_data = {
                "group": group,
                "password": password,
                "username": username
            }
            
            result = self.post('config/system/users/', user_data)
            
            if isinstance(result, tuple):
                result = result[1] if len(result) > 1 else result[0]
                
            return {
                'success': True,
                'username': username,
                'group': group,
                'result': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def get_users(self) -> dict:
        """Get list of all users on the router.
        
        Returns:
            dict: List of users and their information
        """
        try:
            result = self.get('config/system/users/')
            
            if isinstance(result, tuple):
                result = result[1] if len(result) > 1 else result[0]
                
            return {
                'success': True,
                'users': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def delete_user(self, username: str) -> dict:
        """Delete a user from the router.
        
        Args:
            username (str): The username to delete
            
        Returns:
            dict: Result of the user deletion operation
        """
        try:
            # First get the user to find their _id_
            users_result = self.get_users()
            if not users_result.get('success'):
                return users_result
                
            users = users_result.get('users', [])
            user_to_delete = None
            
            if isinstance(users, list):
                for i, user in enumerate(users):
                    if isinstance(user, dict) and user.get('username') == username:
                        user_to_delete = {'user': user, 'index': i, '_id_': user.get('_id_')}
                        break
            
            if not user_to_delete:
                return {
                    'success': False,
                    'error': f'User {username} not found',
                    'username': username
                }
            
            # Try deleting by _id_ first, then by index
            user_id = user_to_delete['_id_']
            index = user_to_delete['index']
            
            # Try by _id_ first
            result = self.delete(f'config/system/users/{user_id}')
            
            if isinstance(result, tuple):
                result = result[1] if len(result) > 1 else result[0]
            
            # If that fails, try by index
            if not result.get('success', True):
                result = self.delete(f'config/system/users/{index}')
                if isinstance(result, tuple):
                    result = result[1] if len(result) > 1 else result[0]
                
            return {
                'success': True,
                'username': username,
                'user_id': user_id,
                'index': index,
                'result': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def ensure_user_exists(self, username: str, password: str, group: str = "admin") -> dict:
        """Ensure a user exists, creating it if it doesn't.
        
        Args:
            username (str): The username to ensure exists
            password (str): The password for the user (used if creating)
            group (str): The group for the user (default: "admin")
            
        Returns:
            dict: Result of the operation
        """
        try:
            # First check if user exists
            users_result = self.get_users()
            if not users_result.get('success'):
                return users_result
                
            users = users_result.get('users', [])
            existing_user = None
            
            if isinstance(users, list):
                for user in users:
                    if isinstance(user, dict) and user.get('username') == username:
                        existing_user = user
                        break
            elif isinstance(users, dict):
                # Handle case where users might be a dict with usernames as keys
                if username in users:
                    existing_user = users[username]
                    
            if existing_user:
                return {
                    'success': True,
                    'username': username,
                    'action': 'exists',
                    'user': existing_user
                }
            else:
                # User doesn't exist, create it
                create_result = self.create_user(username, password, group)
                if create_result.get('success'):
                    create_result['action'] = 'created'
                return create_result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def _generate_random_password(self, length: int = 16) -> str:
        """Generate a random password with mixed characters.
        
        Args:
            length: Length of the password (default: 16)
            
        Returns:
            str: Random password
        """
        
        # Define character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Ensure at least one character from each set
        password = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(special)
        ]
        
        # Fill the rest with random characters from all sets
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - 4):
            password.append(random.choice(all_chars))
        
        # Shuffle the password
        random.shuffle(password)
        return ''.join(password)

    def ensure_fresh_user(self, username: str, group: str = "admin") -> dict:
        """Ensure a user exists with a fresh random password, deleting existing user first.
        
        Args:
            username (str): The username to ensure exists
            group (str): The group for the user (default: "admin")
            
        Returns:
            dict: Result of the operation with the generated password
        """
        try:
            # First, try to delete the user if it exists
            delete_result = self.delete_user(username)
            if delete_result.get('success'):
                self.log(f"Deleted existing user '{username}'")
            else:
                self.log(f"User '{username}' did not exist or deletion failed: {delete_result.get('error', 'Unknown')}")
            
            # Generate a random password
            password = self._generate_random_password()
            
            # Create the user with the new password
            create_result = self.create_user(username, password, group)
            if create_result.get('success'):
                create_result['password'] = password
                create_result['action'] = 'created_fresh'
                self.log(f"Created fresh user '{username}' with random password")
            else:
                create_result['password'] = password
                
            return create_result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'username': username
            }

    def packet_capture(self, 
                      iface: str = None,
                      filter: str = "",
                      count: int = 10,
                      timeout: int = 10,
                      save_directory: str = "captures",
                      capture_user: str = "SDKTCPDUMP") -> dict:
        """Packet capture that handles everything in one call.
        
        This method:
        1. Creates/ensures a dedicated user exists
        2. Captures packets on specified interface
        3. Downloads the pcap file to local directory
        4. Deletes the temporary user after successful completion
        
        Args:
            iface: Network interface to capture on (default: cp.get('config/lan/0/_id_'))
            filter: BPF filter expression (default: "" for all traffic)
            count: Number of packets to capture (default: 10)
            timeout: Capture timeout in seconds (default: 10)
            save_directory: Directory to save captured files (default: "captures")
            capture_user: Username for packet capture operations (default: "SDKTCPDUMP")
            
        Returns:
            dict: Result with all operation details
        """
        result = {
            'success': False,
            'user_creation': None,
            'packet_capture': None,
            'file_download': None,
            'captured_file': None,
            'generated_password': None,
            'monitor_mode_disabled': None,
            'monitor_mode_error': None,
            'user_deletion': None
        }
        
        try:
            # Set default interface if not provided
            if iface is None:
                iface = self.get('config/lan/0/_id_')
            
            # Step 1: Ensure dedicated user exists with fresh random password
            self.log(f"Step 1: Setting up fresh user '{capture_user}' for packet capture...")
            user_result = self.ensure_fresh_user(capture_user, "admin")
            result['user_creation'] = user_result
            result['generated_password'] = user_result.get('password')
            if not user_result.get('success'):
                result['error'] = f"Failed to create user: {user_result.get('error')}"
                return result
            
            # Step 2: Start packet capture
            self.log(f"Step 2: Starting packet capture on {iface}...")
            capture_result = self.start_packet_capture(
                interface=iface,
                filter=filter,
                count=count,
                timeout=timeout
            )
            result['packet_capture'] = capture_result
            
            if not capture_result or 'filename' not in capture_result:
                result['error'] = "Failed to start packet capture"
                return result
            
            filename = capture_result['filename']
            self.log(f"Capture started, filename: {filename}")
            
            # Step 3: Wait for capture to complete and download file
            self.log("Step 3: Waiting for capture to complete...")
            time.sleep(max(3, timeout // 3))  # Wait for capture to complete
            
            # Create save directory
            captures_dir = os.path.join(os.getcwd(), save_directory)
            os.makedirs(captures_dir, exist_ok=True)
            local_path = os.path.join(captures_dir, filename)
            
            # Download the captured file
            self.log(f"Step 4: Downloading captured file {filename}...")
            download_result = self.download_packet_capture(
                filename, 
                local_path, 
                capture_result.get('parameters', {})
            )
            result['file_download'] = download_result
            
            if not download_result.get('success'):
                result['error'] = f"Failed to download pcap file: {download_result.get('error')}"
                return result
            
            file_size = download_result.get('file_size', 0)
            self.log(f"Successfully downloaded pcap file: {local_path} ({file_size} bytes)")
            result['captured_file'] = {
                'filename': filename,
                'local_path': local_path,
                'file_size': file_size
            }
            
            # Disable monitor mode for mon0 or mon1 interfaces after successful capture
            if iface in ['mon0', 'mon1']:
                self.log(f"Disabling monitor mode for interface {iface}...")
                try:
                    monitor_result = self.put('control/wlan/monitor', False)
                    if monitor_result:
                        self.log(f"Successfully disabled monitor mode for {iface}")
                        result['monitor_mode_disabled'] = True
                    else:
                        self.log(f"Warning: Failed to disable monitor mode for {iface}")
                        result['monitor_mode_disabled'] = False
                except Exception as e:
                    self.log(f"Error disabling monitor mode for {iface}: {e}")
                    result['monitor_mode_disabled'] = False
                    result['monitor_mode_error'] = str(e)
            
            # Step 5: Delete the temporary user after successful completion
            self.log(f"Step 5: Deleting temporary user '{capture_user}'...")
            delete_result = self.delete_user(capture_user)
            result['user_deletion'] = delete_result
            
            if not delete_result.get('success'):
                result['error'] = f"Failed to delete user '{capture_user}': {delete_result.get('error', 'Unknown error')}"
                self.log(f"Error: Failed to delete user '{capture_user}': {delete_result.get('error', 'Unknown error')}")
                return result
            
            self.log(f"Successfully deleted user '{capture_user}'")
            result['success'] = True
            self.log("Packet capture completed successfully!")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            self.log(f"Error in packet capture: {e}")
            return result


    def dns_lookup(self, hostname: str, record_type: str = "A") -> Optional[Dict[str, Any]]:
        """Perform DNS lookup using the router's DNS tools.
        
        Args:
            hostname: Hostname to resolve
            record_type: DNS record type (A, AAAA, MX, etc.)
            
        Returns:
            dict: DNS lookup results
        """
        try:
            # Perform DNS lookup
            dns_params = {
                "hostname": hostname,
                "record_type": record_type
            }
            
            result = self.post('control/dns/lookup', dns_params)
            
            return {
                'hostname': hostname,
                'record_type': record_type,
                'result': result
            }
            
        except Exception as e:
            self.log(f"Error performing DNS lookup for {hostname}: {e}")
            return None

    def clear_dns_cache(self) -> Optional[Dict[str, Any]]:
        """Clear the router's DNS cache.
        
        Returns:
            dict: Cache clear result
        """
        try:
            # Clear DNS cache
            result = self.post('control/dns/cache', {"clear": True})
            
            return {
                'result': result
            }
            
        except Exception as e:
            self.log(f"Error clearing DNS cache: {e}")
            return None

    def stop_ping(self) -> Optional[Dict[str, Any]]:
        """Stop any running ping process.
        
        Returns:
            dict: Stop result
        """
        try:
            # Stop ping process
            result = self.put('control/ping/stop', '')
            
            return {
                'result': result
            }
            
        except Exception as e:
            self.log(f"Error stopping ping: {e}")
            return None

    def set_manual_apn(self, device_or_id: str, new_apn: str) -> Optional[Dict[str, Any]]:
        """Set manual APN for a modem device or WAN rule.
        
        Args:
            device_or_id (str): Either a modem device name (starts with 'mdm') or a WAN rule _id_
            new_apn (str): The new APN to set
            
        Returns:
            dict: Result with operation details including:
                - device_id (str): The device identifier used
                - rule_id (str): The WAN rule _id_ that was modified
                - new_apn (str): The APN that was set
                - success (bool): Whether the operation was successful
        """
        try:
            rule_id = None
            
            # Check if input is a modem device name
            if device_or_id.startswith('mdm'):
                # Get device info to find the config_id (WAN rule _id_)
                device_info = self.get(f'status/wan/devices/{device_or_id}/config')
                if not device_info:
                    return {
                        'device_id': device_or_id,
                        'error': f'Device {device_or_id} not found or no config available',
                        'success': False
                    }
                
                rule_id = device_info.get('_id_')
                if not rule_id:
                    return {
                        'device_id': device_or_id,
                        'error': f'No WAN rule _id_ found for device {device_or_id}',
                        'success': False
                    }
            else:
                # Assume it's already a WAN rule _id_
                rule_id = device_or_id
            
            # Update the WAN rule with manual APN configuration
            apn_config = {
                "modem": {
                    "apn_mode": "manual",
                    "manual_apn": new_apn
                }
            }
            
            result = self.put(f'config/wan/rules2/{rule_id}', apn_config)
            
            if result is not None:
                return {
                    'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                    'rule_id': rule_id,
                    'new_apn': new_apn,
                    'success': True
                }
            else:
                return {
                    'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                    'rule_id': rule_id,
                    'error': 'Failed to update WAN rule configuration',
                    'success': False
                }
                
        except Exception as e:
            self.log(f"Error setting manual APN for {device_or_id}: {e}")
            return {
                'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                'error': str(e),
                'success': False
            }

    def remove_manual_apn(self, device_or_id: str) -> Optional[Dict[str, Any]]:
        """Remove manual APN configuration for a modem device or WAN rule.
        
        Args:
            device_or_id (str): Either a modem device name (starts with 'mdm') or a WAN rule _id_
            
        Returns:
            dict: Result with operation details including:
                - device_id (str): The device identifier used
                - rule_id (str): The WAN rule _id_ that was modified
                - success (bool): Whether the operation was successful
        """
        try:
            rule_id = None
            
            # Check if input is a modem device name
            if device_or_id.startswith('mdm'):
                # Get device info to find the config_id (WAN rule _id_)
                device_info = self.get(f'status/wan/devices/{device_or_id}/config')
                if not device_info:
                    return {
                        'device_id': device_or_id,
                        'error': f'Device {device_or_id} not found or no config available',
                        'success': False
                    }
                
                rule_id = device_info.get('_id_')
                if not rule_id:
                    return {
                        'device_id': device_or_id,
                        'error': f'No WAN rule _id_ found for device {device_or_id}',
                        'success': False
                    }
            else:
                # Assume it's already a WAN rule _id_
                rule_id = device_or_id
            
            # Remove the manual APN configuration by setting apn_mode to auto
            apn_config = {
                "modem": {
                    "apn_mode": "auto"
                }
            }
            
            result = self.put(f'config/wan/rules2/{rule_id}', apn_config)
            
            if result is not None:
                return {
                    'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                    'rule_id': rule_id,
                    'success': True
                }
            else:
                return {
                    'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                    'rule_id': rule_id,
                    'error': 'Failed to update WAN rule configuration',
                    'success': False
                }
                
        except Exception as e:
            self.log(f"Error removing manual APN for {device_or_id}: {e}")
            return {
                'device_id': device_or_id if device_or_id.startswith('mdm') else None,
                'error': str(e),
                'success': False
            }

    def add_advanced_apn(self, carrier: str, apn: str) -> Optional[Dict[str, Any]]:
        """Add an advanced APN configuration to the custom APNs list.
        
        Args:
            carrier (str): Carrier name or PLMN identifier
            apn (str): APN name to configure
            
        Returns:
            dict: Result with operation details including:
                - carrier (str): The carrier that was added
                - apn (str): The APN that was added
                - success (bool): Whether the operation was successful
        """
        try:
            # Get existing custom APNs
            existing_apns = self.get('config/wan/custom_apns')
            if not existing_apns:
                existing_apns = []
            
            # Check if this carrier/APN combination already exists
            for existing_apn in existing_apns:
                if (existing_apn.get('carrier') == carrier and 
                    existing_apn.get('apn') == apn):
                    return {
                        'carrier': carrier,
                        'apn': apn,
                        'error': f'Advanced APN for carrier "{carrier}" and APN "{apn}" already exists',
                        'success': False
                    }
            
            # Add the new advanced APN to the existing array
            new_apn_entry = {
                "carrier": carrier,
                "apn": apn
            }
            
            # Append to existing array and update the entire array
            updated_apns = existing_apns + [new_apn_entry]
            result = self.put('config/wan/custom_apns', updated_apns)
            
            if result is not None:
                return {
                    'carrier': carrier,
                    'apn': apn,
                    'success': True
                }
            else:
                return {
                    'carrier': carrier,
                    'apn': apn,
                    'error': 'Failed to add advanced APN configuration',
                    'success': False
                }
                
        except Exception as e:
            self.log(f"Error adding advanced APN for carrier {carrier} and APN {apn}: {e}")
            return {
                'carrier': carrier,
                'apn': apn,
                'error': str(e),
                'success': False
            }

    def delete_advanced_apn(self, carrier_or_apn: str) -> Optional[Dict[str, Any]]:
        """Delete an advanced APN configuration from the custom APNs list.
        
        Args:
            carrier_or_apn (str): Carrier name, PLMN identifier, or APN name to match and delete
            
        Returns:
            dict: Result with operation details including:
                - matched_entries (list): List of entries that were matched and deleted
                - success (bool): Whether the operation was successful
                - deleted_count (int): Number of entries deleted
        """
        try:
            # Get existing custom APNs
            existing_apns = self.get('config/wan/custom_apns')
            if not existing_apns:
                return {
                    'matched_entries': [],
                    'deleted_count': 0,
                    'error': 'No custom APNs found',
                    'success': False
                }
            
            # Find matching entries and create filtered array
            matched_entries = []
            remaining_apns = []
            
            for apn_entry in existing_apns:
                if (apn_entry.get('carrier') == carrier_or_apn or 
                    apn_entry.get('apn') == carrier_or_apn):
                    matched_entries.append(apn_entry)
                else:
                    remaining_apns.append(apn_entry)
            
            if not matched_entries:
                return {
                    'matched_entries': [],
                    'deleted_count': 0,
                    'error': f'No advanced APN found matching "{carrier_or_apn}"',
                    'success': False
                }
            
            # Update the array with remaining entries
            result = self.put('config/wan/custom_apns', remaining_apns)
            
            if result is not None:
                return {
                    'matched_entries': matched_entries,
                    'deleted_count': len(matched_entries),
                    'success': True
                }
            else:
                return {
                    'matched_entries': matched_entries,
                    'deleted_count': 0,
                    'error': 'Failed to update custom APNs configuration',
                    'success': False
                }
                
        except Exception as e:
            self.log(f"Error deleting advanced APN matching {carrier_or_apn}: {e}")
            return {
                'matched_entries': [],
                'deleted_count': 0,
                'error': str(e),
                'success': False
            }

    def monitor_log(self, 
                    pattern: str = None,
                    callback: callable = None,
                    follow: bool = True,
                    max_lines: int = 0,
                    timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Monitor /var/log/messages and optionally match lines against a pattern, sending matches to a callback.
        
        This method provides real-time log monitoring with pattern matching and callback handling.
        It runs in a separate thread to avoid blocking the main application.
        
        Args:
            pattern: Regex pattern to match against log lines (default: None for all lines)
            callback: Function to call with matching lines (default: None for no callback)
            follow: Whether to follow the file (like tail -f) (default: True)
            max_lines: Maximum number of lines to process (0 = unlimited) (default: 0)
            timeout: Timeout in seconds (0 = no timeout) (default: 0)
            
        Returns:
            dict: Result with thread information and status
        """
        import threading
        import re
        import time
        from subprocess import Popen, PIPE
        from queue import Queue, Empty
        
        result = {
            'success': False,
            'thread_id': None,
            'log_file': '/var/log/messages',
            'pattern': pattern,
            'callback': callback is not None,
            'follow': follow,
            'max_lines': max_lines,
            'timeout': timeout,
            'error': None
        }
        
        try:
            # Validate inputs
            log_file = '/var/log/messages'
            if not os.path.exists(log_file):
                result['error'] = f"Log file does not exist: {log_file}"
                return result
            
            if callback and not callable(callback):
                result['error'] = "Callback must be a callable function"
                return result
            
            # Compile regex pattern if provided
            compiled_pattern = None
            if pattern:
                try:
                    compiled_pattern = re.compile(pattern)
                except re.error as e:
                    result['error'] = f"Invalid regex pattern: {e}"
                    return result
            
            # Create a queue for communication between threads
            line_queue = Queue()
            stop_event = threading.Event()
            
            def monitor_worker():
                """Worker thread that monitors the log file."""
                try:
                    # Build tail command
                    cmd = ['/usr/bin/tail']
                    if follow:
                        cmd.append('-F')
                    if max_lines > 0:
                        cmd.extend(['-n', str(max_lines)])
                    cmd.append(log_file)
                    
                    self.log(f"Starting monitor process: {' '.join(cmd)}")
                    monitor_process = Popen(cmd, stdout=PIPE, stderr=PIPE, bufsize=1, universal_newlines=True)
                    
                    line_count = 0
                    start_time = time.time()
                    
                    for line in iter(monitor_process.stdout.readline, ''):
                        if stop_event.is_set():
                            break
                            
                        # Check timeout
                        if timeout > 0 and (time.time() - start_time) > timeout:
                            self.log(f"Monitor timeout reached: {timeout} seconds")
                            break
                        
                        # Check max lines
                        if max_lines > 0 and line_count >= max_lines:
                            self.log(f"Max lines reached: {max_lines}")
                            break
                        
                        line = line.rstrip('\n\r')
                        if not line:
                            continue
                        
                        line_count += 1
                        
                        # Check pattern match
                        if compiled_pattern:
                            if not compiled_pattern.search(line):
                                continue
                        
                        # Send line to callback or queue
                        if callback:
                            try:
                                callback(line)
                            except Exception as e:
                                self.log(f"Error in callback: {e}")
                        else:
                            line_queue.put(line)
                    
                    # Clean up process
                    monitor_process.terminate()
                    monitor_process.wait(timeout=5)
                    
                except Exception as e:
                    self.log(f"Error in monitor worker: {e}")
                    line_queue.put(f"ERROR: {e}")
                finally:
                    line_queue.put(None)  # Signal end of stream
            
            # Start the monitor worker thread
            monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
            monitor_thread.start()
            
            result.update({
                'success': True,
                'thread_id': monitor_thread.ident,
                'thread_name': monitor_thread.name,
                'line_queue': line_queue,
                'stop_event': stop_event
            })
            
            self.log(f"Started monitor_log thread {monitor_thread.ident} for {log_file}")
            
        except Exception as e:
            result['error'] = str(e)
            self.log(f"Error starting monitor_log: {e}")
        
        return result
    
    def stop_monitor_log(self, monitor_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Stop a running monitor_log operation.
        
        Args:
            monitor_result: The result dictionary returned by monitor_log()
            
        Returns:
            dict: Result of the stop operation
        """
        result = {
            'success': False,
            'stopped': False,
            'error': None
        }
        
        try:
            if not monitor_result or not monitor_result.get('success'):
                result['error'] = "Invalid monitor_result provided"
                return result
            
            stop_event = monitor_result.get('stop_event')
            if stop_event:
                stop_event.set()
                result['stopped'] = True
                result['success'] = True
                self.log(f"Stopped monitor_log thread {monitor_result.get('thread_id')}")
            else:
                result['error'] = "No stop_event found in monitor_result"
                
        except Exception as e:
            result['error'] = str(e)
            self.log(f"Error stopping monitor_log: {e}")
        
        return result

    def monitor_sms(self, 
                    callback: callable,
                    timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Monitor SMS messages and send parsed data to a callback function.
        
        This method monitors /var/log/messages for SMS received messages and automatically
        parses the phone number and message content, sending structured data to the callback.
        
        Args:
            callback: Function to call with SMS data (phone_number, message, raw_line)
            timeout: Timeout in seconds (0 = no timeout) (default: 0)
            
        Returns:
            dict: Result with thread information and status
            
        Example:
            def sms_handler(phone_number, message, raw_line):
                print(f"SMS from {phone_number}: {message}")
                # Auto-reply
                cp.execute_cli(f'sms {phone_number} Thanks for your message!')
            
            result = _cs_client.monitor_sms(callback=sms_handler)
        """
        import re
        
        def sms_parser(raw_line: str):
            """Parse SMS log line and extract phone number and message."""
            try:
                # SMS log format is typically: "SMS received: <message> <phone_number>"
                # We need to extract the message and phone number
                
                # Remove timestamp and "SMS received:" prefix
                if "SMS received:" in raw_line:
                    sms_part = raw_line.split("SMS received:", 1)[1].strip()
                    
                    # Split by spaces to get individual parts
                    parts = sms_part.split()
                    
                    if len(parts) >= 2:
                        # Last part is typically the phone number
                        phone_number = parts[-1]
                        
                        # Everything before the last part is the message
                        message = " ".join(parts[:-1])
                        
                        # Call the user's callback with parsed data
                        callback(phone_number, message, raw_line)
                    else:
                        # Fallback: if we can't parse properly, send raw data
                        callback("unknown", sms_part, raw_line)
                        
            except Exception as e:
                self.log(f"Error parsing SMS line: {e}")
                # Call callback with error data
                callback("error", str(e), raw_line)
        
        # Use the existing monitor_log method with SMS-specific parsing
        return self.monitor_log(
            pattern="SMS received:",
            callback=sms_parser,
            timeout=timeout
        )
    
    def stop_monitor_sms(self, monitor_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Stop a running monitor_sms operation.
        
        Args:
            monitor_result: The result dictionary returned by monitor_sms()
            
        Returns:
            dict: Result of the stop operation
        """
        # This is the same as stopping monitor_log since monitor_sms uses it internally
        return self.stop_monitor_log(monitor_result)

    def send_sms(self, 
                 phone_number: str = None,
                 message: str = None,
                 port: str = None) -> Optional[str]:
        """Send an SMS message using the CLI.
        
        This method sends an SMS message using the CLI command with automatic port detection
        if no port is specified. It finds the first connected modem and uses its port.
        
        Args:
            phone_number: The phone number to send the SMS to
            message: The message content to send
            port: The modem port to use (default: None for auto-detection)
            
        Returns:
            str: CLI command output, or None if an error occurred
            
        Example:
            # Send SMS with auto-detected port
            output = _cs_client.send_sms(phone_number="+1234567890", message="Hello from the router!")
            
            # Send SMS with specific port
            output = _cs_client.send_sms(phone_number="+1234567890", message="Hello!", port="ttyUSB0")
        """
        try:
            # Validate required parameters
            if not phone_number:
                self.log("phone_number is required for send_sms")
                return None
            if not message:
                self.log("message is required for send_sms")
                return None
            
            # Auto-detect port if not provided
            if port is None:
                port = self._get_first_connected_modem_port()
                if port is None:
                    self.log("No connected modem found for SMS sending")
                    return None
            
            # Build and execute the SMS command
            sms_command = f'sms {phone_number} "{message}" {port}'
            return self.execute_cli(sms_command)
            
        except Exception as e:
            self.log(f"Error sending SMS: {e}")
            return None
    
    def _get_first_connected_modem_port(self) -> Optional[str]:
        """Get the port of the first connected modem.
        
        Returns:
            str: The port of the first connected modem, or None if none found
        """
        try:
            # Get list of WAN devices
            wan_devices = self.get('status/wan/devices')
            if not wan_devices:
                return None
            
            # Look for connected modems (mdm devices)
            for device_id, device_info in wan_devices.items():
                if device_id.startswith('mdm-'):
                    # Check if device is connected
                    device_status = self.get(f'status/wan/devices/{device_id}/info')
                    if device_status and device_status.get('connected'):
                        # Get the port
                        port = device_status.get('port')
                        if port:
                            self.log(f"Found connected modem {device_id} on port {port}")
                            return port
            
            self.log("No connected modems found")
            return None
            
        except Exception as e:
            self.log(f"Error detecting modem port: {e}")
            return None

    def execute_cli(self, 
                   commands: Union[str, List[str]],
                   timeout: int = 10,
                   soft_timeout: int = 5,
                   clean: bool = True) -> Optional[str]:
        """Execute CLI commands and return the output.
        
        This method provides a simplified interface to execute CLI commands using the
        config store terminal interface. It handles command execution, output capture,
        and cleanup automatically.
        
        Args:
            commands: Single command string or list of commands to execute
            timeout: Absolute maximum number of seconds to wait for output (default: 10)
            soft_timeout: Number of seconds to wait before sending interrupt (default: 5)
            clean: Whether to remove terminal escape sequences from output (default: True)
            
        Returns:
            str: Command output, or None if an error occurred
            
        Example:
            # Single command
            output = _cs_client.execute_cli("show version")
            
            # Multiple commands
            output = _cs_client.execute_cli(["show version", "show interfaces"])
            
            # With custom timeout
            output = _cs_client.execute_cli("show config", timeout=30)
        """
        import random
        import re
        
        try:
            # Validate inputs
            if not commands:
                self.log("No commands provided to execute_cli")
                return None
            
            # Convert single command to list
            if isinstance(commands, str):
                commands = [commands]
            
            # Generate unique session ID
            session_id = f"term-{random.randint(100000000, 999999999)}"
            
            # Add newlines to commands
            commands_with_newlines = [cmd + '\n' for cmd in commands]
            
            # Calculate timeout intervals
            interval = 0.3  # Polling interval
            timeout_cycles = int(timeout / interval)
            soft_timeout_cycles = int(soft_timeout / interval)
            
            # Execute commands
            output = ''
            command_iter = iter(commands_with_newlines)
            current_command = next(command_iter)
            
            cycles_remaining = timeout_cycles
            soft_timeout_remaining = soft_timeout_cycles
            
            while cycles_remaining > 0:
                # Send command
                command_data = {"k": current_command}
                
                self.put(f"/control/csterm/{session_id}", command_data)
                
                # Get response
                response = self.get(f"/control/csterm/{session_id}")
                if response and 'k' in response:
                    output += response['k']
                
                # Check if we've sent all commands and got a prompt
                if current_command == "" and not output.endswith('\n'):
                    break
                
                # Move to next command
                current_command = next(command_iter, None) or ""
                cycles_remaining -= 1
                
                # Handle soft timeout
                if cycles_remaining < (timeout_cycles - soft_timeout_remaining):
                    # Send interrupt (Ctrl+C)
                    interrupt_data = {"k": '\x03'}
                    
                    self.put(f"/control/csterm/{session_id}", interrupt_data)
                    response = self.get(f"/control/csterm/{session_id}")
                    if response and 'k' in response:
                        output += response['k']
                    soft_timeout_remaining = 0
                
                time.sleep(interval)
            
            # Clean up output if requested
            if clean and output:
                # Remove terminal escape sequences
                output = re.sub(r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])', '', output)
                
                # Remove prompt lines
                lines = output.split('\n')
                if lines:
                    # Find the prompt (usually the last non-empty line)
                    prompt = None
                    for line in reversed(lines):
                        if line.strip():
                            prompt = line
                            break
                    
                    if prompt:
                        # Remove lines that start with the prompt
                        lines = [line for line in lines if not line.startswith(prompt)]
                        output = '\n'.join(lines)
            
            self.log(f"CLI execution completed for session {session_id}")
            return output.strip()
            
        except Exception as e:
            self.log(f"Error executing CLI commands: {e}")
            return None


def _get_app_name() -> str:
    """Get the app name from the first section of package.ini.
    
    Returns:
        str: The application name from package.ini, or 'SDK' if not found.
    """
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        package_ini_path = os.path.join(script_dir, 'package.ini')
        
        if os.path.exists(package_ini_path):
            config = configparser.ConfigParser()
            config.read(package_ini_path)
            # Get the first section name
            first_section = config.sections()[0] if config.sections() else 'SDK'
            return first_section
        else:
            return 'SDK'
    except Exception as e:
        print(f"Error getting app name from package.ini: {e}")
        return 'SDK'

def _cs_sock_connection() -> bool:
    sock_path = '/var/tmp/cs.sock'
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(sock_path)
        return True
    except:
        return False

_enable_logging = '/var/mnt/sdk/' in os.getcwd()
_is_ncos = _cs_sock_connection()

# Create a single EventingCSClient instance with name from package.ini
_cs_client = EventingCSClient(_get_app_name(), enable_logging=_enable_logging, ncos=_is_ncos)

def get_uptime() -> int:
    """Return the router uptime in seconds.
    
    Returns:
        int: The router uptime in seconds, or 0 if an error occurs.
    """
    try:
        uptime = int(_cs_client.get('status/system/uptime'))
        return uptime
    except Exception as e:
        _cs_client.log(f"Error getting uptime: {e}")
        return 0

def wait_for_uptime(min_uptime_seconds: int = 60) -> None:
    """Wait for the device uptime to be greater than the specified uptime.
    
    If the current uptime is less than the specified minimum, the function
    will sleep until the uptime requirement is met.
    
    Args:
        min_uptime_seconds (int): Minimum uptime in seconds. Defaults to 60.
    """
    try:
        current_uptime = get_uptime()
        if current_uptime < min_uptime_seconds:
            sleep_duration = min_uptime_seconds - current_uptime
            _cs_client.log(f"Router uptime is less than {min_uptime_seconds} seconds. Sleeping for {sleep_duration} seconds.")
            time.sleep(sleep_duration)
        else:
            _cs_client.log(f"Router uptime is sufficient: {current_uptime} seconds.")
    except Exception as e:
        _cs_client.logger.exception(f"Error validating uptime: {e}")

def wait_for_ntp(timeout: int = 300, check_interval: int = 1) -> bool:
    """Wait until NTP sync age is not null, indicating NTP synchronization.
    
    Args:
        timeout (int): Maximum time to wait in seconds. Defaults to 300.
        check_interval (int): Time between checks in seconds. Defaults to 1.
    
    Returns:
        bool: True if NTP sync was achieved within timeout, False otherwise.
    """
    try:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            sync_age = _cs_client.get('status/system/ntp/sync_age')
            
            if sync_age is not None:
                _cs_client.log(f'NTP sync achieved, sync_age: {sync_age}')
                return True
                
            time.sleep(check_interval)
        
        _cs_client.log(f'NTP sync timeout after {timeout} seconds')
        return False
    except Exception as e:
        _cs_client.log(f"Error waiting for NTP sync: {e}")
        return False

def wait_for_wan_connection(timeout: int = 300) -> bool:
    """Wait for at least one WAN connection to be 'connected'.
    
    Args:
        timeout (int): Maximum time to wait in seconds. Defaults to 300.
    
    Returns:
        bool: True if a connection is established within the timeout, False otherwise.
    """
    try:
        # First check if WAN is already connected
        connection_state = _cs_client.get('status/wan/connection_state')
        if connection_state == 'connected':
            return True
        
        _cs_client.log("Waiting for a WAN connection...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            # Check for a global connection state
            connection_state = _cs_client.get('status/wan/connection_state')
            if connection_state == 'connected':
                _cs_client.log("WAN is connected.")
                return True

            time.sleep(1)
        _cs_client.log(f"Timeout waiting for WAN connection after {timeout} seconds.")
        return False
    except Exception as e:
        _cs_client.log(f"Error waiting for WAN connection: {e}")
        return False

def get_appdata(name: str = '') -> Optional[str]:
    """Get value of appdata from NCOS Config by name.
    
    Args:
        name (str): The name of the appdata to retrieve. Defaults to empty string.
    
    Returns:
        str or None: The value of the appdata, or None if not found or an error occurs.
    """
    try:
        appdata = _cs_client.get('config/system/sdk/appdata')
        return next(iter(x["value"] for x in appdata if x["name"] == name), None)
    except Exception as e:
        _cs_client.log(f"Error getting appdata for {name}: {e}")
        return None

def post_appdata(name: str = '', value: str = '') -> None:
    """Create appdata in NCOS Config by name.
    
    Args:
        name (str): The name of the appdata to create. Defaults to empty string.
        value (str): The value to set for the appdata. Defaults to empty string.
    """
    try:
        _cs_client.post('config/system/sdk/appdata', {"name": name, "value": value})
    except Exception as e:
        _cs_client.log(f"Error posting appdata for {name}: {e}")

def put_appdata(name: str = '', value: str = '') -> None:
    """Set value of appdata in NCOS Config by name.
    
    Args:
        name (str): The name of the appdata to update. Defaults to empty string.
        value (str): The new value to set for the appdata. Defaults to empty string.
    """
    try:
        appdata = _cs_client.get('config/system/sdk/appdata')
        for item in appdata:
            if item["name"] == name:
                _cs_client.put(f'config/system/sdk/appdata/{item["_id_"]}/value', value)
    except Exception as e:
        _cs_client.log(f"Error putting appdata for {name}: {e}")

def delete_appdata(name: str = '') -> None:
    """Delete appdata in NCOS Config by name.
    
    Args:
        name (str): The name of the appdata to delete. Defaults to empty string.
    """
    try:
        appdata = _cs_client.get('config/system/sdk/appdata')
        for item in appdata:
            if item["name"] == name:
                _cs_client.delete(f'config/system/sdk/appdata/{item["_id_"]}')
    except Exception as e:
        _cs_client.log(f"Error deleting appdata for {name}: {e}")

def get_ncm_api_keys() -> Dict[str, Optional[str]]:
    """Get NCM API keys from the router's certificate management configuration.
    
    Returns:
        dict: Dictionary containing all API keys, with None for any missing keys.
            Keys include: 'X-ECM-API-ID', 'X-ECM-API-KEY', 'X-CP-API-ID',
            'X-CP-API-KEY', 'Bearer Token'.
    
    Raises:
        Exception: If there is an error retrieving the API keys.
    """
    try:
        certs = _cs_client.get('config/certmgmt/certs')
        
        api_keys = {
            'X-ECM-API-ID': None,
            'X-ECM-API-KEY': None,
            'X-CP-API-ID': None,
            'X-CP-API-KEY': None,
            'Bearer Token': None
        }

        for cert in certs:
            cert_name = cert.get('name', '')
            for key in api_keys:
                if key in cert_name:
                    api_keys[key] = _cs_client.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')

        # Log warning for any missing keys
        missing = [k for k, v in api_keys.items() if v is None]
        if missing:
            _cs_client.logger.warning(f"Missing API keys: {', '.join(missing)}")

        return api_keys
        
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving NCM API keys: {e}")
        raise

def extract_cert_and_key(cert_name_or_uuid: str = '') -> Tuple[Optional[str], Optional[str]]:
    """Extract and save the certificate and key to the local filesystem.
    
    Args:
        cert_name_or_uuid (str): The name or UUID of the certificate to extract.
                                Defaults to empty string.
    
    Returns:
        Tuple[str, str] or Tuple[None, None]: A tuple containing the filenames
        of the certificate and key files, or (None, None) if the certificate
        is not found or an error occurs.
    """
    try:
        cert_x509 = None
        cert_key = None
        ca_uuid = None
        cert_name = None

        # Check if cert_name_or_uuid is in UUID format
        uuid_regex = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        is_uuid = bool(uuid_regex.match(cert_name_or_uuid))
        match_field = '_id_' if is_uuid else 'name'

        # Get the list of certificates
        certs = _cs_client.get('config/certmgmt/certs')

        # if cert_name is a uuid, find the cert by uuid, otherwise, find the cert by name
        for cert in certs:
            if cert[match_field] == cert_name_or_uuid:
                cert_name = cert.get('name')
                cert_x509 = cert.get('x509')
                cert_key = _cs_client.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')
                ca_uuid = cert.get('ca_uuid')
                break
        else:
            _cs_client.log(f'No certificate "{cert_name_or_uuid}" found')
            return None, None

        # Extract the CA certificate(s) if it exists
        while ca_uuid not in ["", "None", None]:
            for cert in certs:
                if cert.get('_id_') == ca_uuid:
                    cert_x509 += "\n" + cert.get('x509')
                    ca_uuid = cert.get('ca_uuid')

        # Write the fullchain and privatekey .pem files
        if cert_x509 and cert_key:
            with open(f"{cert_name}.pem", "w") as fullchain_file:
                fullchain_file.write(cert_x509)
            with open(f"{cert_name}_key.pem", "w") as privatekey_file:
                privatekey_file.write(cert_key)
            return f"{cert_name}.pem", f"{cert_name}_key.pem"
        elif cert_x509:
            with open(f"{cert_name}.pem", "w") as fullchain_file:
                fullchain_file.write(cert_x509)
            return f"{cert_name}.pem", None
        else:
            _cs_client.log(f'Missing x509 certificate for "{cert_name_or_uuid}"')
            return None, None
    except Exception as e:
        _cs_client.log(f"Error extracting certificate and key for {cert_name_or_uuid}: {e}")
        return None, None

def get_ipv4_wired_clients() -> List[Dict[str, Any]]:
    """Return a list of IPv4 wired clients and their details.
    
    Returns:
        list: List of dictionaries containing wired client information including:
            - mac (str): MAC address of the client
            - hostname (str): Hostname of the client (if available)
            - ip_address (str): IP address of the client
            - network (str): Network the client is connected to
    """
    try:
        wired_clients = []
        lan_clients = _cs_client.get('status/lan/clients') or []
        leases = _cs_client.get('status/dhcpd/leases') or []

        # Filter out IPv6 clients
        lan_clients = [client for client in lan_clients if ":" not in client.get("ip_address", "")]

        for lan_client in lan_clients:
            mac_upper = lan_client.get("mac", "").upper()
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else None
            network = lease.get("network") if lease else None

            # Set hostname to None if it matches the MAC address with hyphens or is "*"
            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wired_clients.append({
                "mac": lan_client.get("mac"),
                "hostname": hostname,
                "ip_address": lan_client.get("ip_address"),
                "network": network
            })
        return wired_clients
    except Exception as e:
        _cs_client.log(f"Error getting IPv4 wired clients: {e}")
        return []

def get_ipv4_wifi_clients() -> List[Dict[str, Any]]:
    """Return a list of IPv4 Wi-Fi clients and their details.
    
    Returns:
        list: List of dictionaries containing Wi-Fi client information including:
            - mac (str): MAC address of the client
            - hostname (str): Hostname of the client (if available)
            - ip_address (str): IP address of the client
            - radio (int): Radio ID the client is connected to
            - bss (int): BSS ID the client is connected to
            - ssid (str): SSID the client is connected to
            - network (str): Network the client is connected to
            - band (str): Frequency band (2.4 GHz or 5 GHz)
            - mode (str): Wi-Fi mode (802.11b, 802.11g, etc.)
            - bw (str): Bandwidth mode
            - txrate (int): Transmit rate
            - rssi (int): Signal strength
            - time (int): Connection time
    """
    try:
        wifi_clients = []
        wlan_clients = _cs_client.get('status/wlan/clients') or []
        leases = _cs_client.get('status/dhcpd/leases') or []
        bw_modes = {0: "20 MHz", 1: "40 MHz", 2: "80 MHz", 3: "80+80 MHz", 4: "160 MHz"}
        wlan_modes = {0: "802.11b", 1: "802.11g", 2: "802.11n", 3: "802.11n-only", 4: "802.11ac", 5: "802.11ax"}
        wlan_band = {0: "2.4", 1: "5"}

        for wlan_client in wlan_clients:
            radio = wlan_client.get("radio")
            bss = wlan_client.get("bss")
            ssid = _cs_client.get(f'config/wlan/radio/{radio}/bss/{bss}/ssid')

            mac_upper = wlan_client.get("mac", "").upper()
            
            # Get DHCP lease information
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else wlan_client.get("hostname")
            network = lease.get("network") if lease else None

            # Set hostname to None if it matches the MAC address with hyphens or is "*"
            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wifi_clients.append({
                "mac": wlan_client.get("mac"),
                "hostname": hostname,
                "ip_address": lease.get("ip_address"),
                "radio": radio,
                "bss": bss,
                "ssid": ssid,
                "network": network,
                "band": wlan_band.get(radio, "Unknown"),
                "mode": wlan_modes.get(wlan_client.get("mode"), "Unknown"),
                "bw": bw_modes.get(wlan_client.get("bw"), "Unknown"),
                "txrate": wlan_client.get("txrate"),
                "rssi": wlan_client.get("rssi0"),
                "time": wlan_client.get("time", 0)
            })
        return wifi_clients
    except Exception as e:
        _cs_client.log(f"Error getting IPv4 WiFi clients: {e}")
        return []

def get_ipv4_lan_clients() -> Dict[str, List[Dict[str, Any]]]:
    """Return a dictionary containing all IPv4 clients, both wired and Wi-Fi.
    
    Returns:
        dict: Dictionary containing two lists:
            - wired_clients (list): List of wired client information
            - wifi_clients (list): List of Wi-Fi client information
    """
    try:
        wired_clients = get_ipv4_wired_clients()
        wifi_clients = get_ipv4_wifi_clients()

        # Ensure both keys are present in the final dictionary
        lan_clients = {
            "wired_clients": wired_clients,
            "wifi_clients": wifi_clients
        }

        return lan_clients
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving clients: {e}")
        return {"wired_clients": [], "wifi_clients": []}

def dec(deg: float, min: float = 0.0, sec: float = 0.0) -> float:
    """Return decimal version of latitude or longitude from degrees, minutes, seconds.
    
    Args:
        deg (float): Degrees component of the coordinate.
        min (float): Minutes component of the coordinate. Defaults to 0.0.
        sec (float): Seconds component of the coordinate. Defaults to 0.0.
    
    Returns:
        float: Decimal representation of the coordinate, rounded to 6 decimal places.
    """
    try:
        if str(deg)[0] == '-':
            dec_val = deg - (min / 60) - (sec / 3600)
        else:
            dec_val = deg + (min / 60) + (sec / 3600)
        return round(dec_val, 6)
    except Exception as e:
        _cs_client.log(f"Error converting coordinates to decimal: {e}")
        return 0.0

def get_lat_long(max_retries: int = 5, retry_delay: float = 0.1) -> Tuple[Optional[float], Optional[float]]:
    """Return latitude and longitude as floats.
    
    Args:
        max_retries (int): Maximum number of retries to get GPS fix. Defaults to 5.
        retry_delay (float): Delay between retries in seconds. Defaults to 0.1.
    
    Returns:
        Tuple[float, float] or Tuple[None, None]: A tuple containing (latitude, longitude)
        in decimal degrees, or (None, None) if GPS fix is not available.
    """
    try:
        fix = _cs_client.get('status/gps/fix')
        retries = 0
        while not fix and retries < max_retries:
            time.sleep(retry_delay)
            fix = _cs_client.get('status/gps/fix')
            retries += 1

        if not fix:
            return None, None

        try:
            lat_deg = fix['latitude']['degree']
            lat_min = fix['latitude']['minute']
            lat_sec = fix['latitude']['second']
            long_deg = fix['longitude']['degree']
            long_min = fix['longitude']['minute']
            long_sec = fix['longitude']['second']
            lat = dec(lat_deg, lat_min, lat_sec)
            long = dec(long_deg, long_min, long_sec)
            lat = float(f"{float(lat):.6f}")
            long = float(f"{float(long):.6f}")
            return lat, long
        except:
            return None, None
    except Exception as e:
        _cs_client.log(f"Error getting latitude and longitude: {e}")
        return None, None

def get_connected_wans(max_retries: int = 10) -> List[str]:
    """Return list of connected WAN UIDs.
    
    Args:
        max_retries (int): Maximum number of retries to get WAN devices. Defaults to 10.
    
    Returns:
        list: List of WAN device UIDs that are currently connected.
    """
    try:
        wans = []
        retries = 0
        while not wans and retries < max_retries:
            wans = _cs_client.get('status/wan/devices')
            retries += 1
            if not wans:
                time.sleep(0.1)
        # get the wans that are connected
        wans = [k for k, v in wans.items() if v['status']['connection_state'] == 'connected']
        if not wans:
            _cs_client.log('No WANs connected!')
        return wans
    except Exception as e:
        _cs_client.log(f"Error getting connected WANs: {e}")
        return []

def get_sims(max_retries: int = 10) -> List[str]:
    """Return list of modem UIDs with SIMs.
    
    Args:
        max_retries (int): Maximum number of retries to get WAN devices. Defaults to 10.
    
    Returns:
        list: List of modem UIDs that have SIMs installed (excluding those with NOSIM errors).
    """
    try:
        SIMs = []
        devices = None
        retries = 0
        while not devices and retries < max_retries:
            devices = _cs_client.get('status/wan/devices')
            retries += 1
            if not devices:
                time.sleep(0.1)
        for uid, status in devices.items():
            if uid.startswith('mdm-'):
                error_text = status.get('status', {}).get('error_text', '')
                if error_text:
                    if 'NOSIM' in error_text:
                        continue
                SIMs.append(uid)
        return SIMs
    except Exception as e:
        _cs_client.log(f"Error getting SIMs: {e}")
        return []

def get_device_mac(format_with_colons: bool = False) -> Optional[str]:
    """Return the device MAC address.
    
    Args:
        format_with_colons (bool): Whether to return MAC address with colons. Defaults to False.
    
    Returns:
        str or None: The device MAC address, or None if not available or an error occurs.
    """
    try:
        mac = _cs_client.get('status/product_info/mac0')
        if not mac:
            return None
        return mac if format_with_colons else mac.replace(':', '')
    except Exception as e:
        _cs_client.log(f"Error getting device MAC: {e}")
        return None

def get_device_serial_num() -> Optional[str]:
    """Return the device serial number.
    
    Returns:
        str or None: The device serial number, or None if not available or an error occurs.
    """
    try:
        return _cs_client.get('status/product_info/manufacturing/serial_num')
    except Exception as e:
        _cs_client.log(f"Error getting device serial number: {e}")
        return None

def get_device_product_type() -> Optional[str]:
    """Return the device product type.
    
    Returns:
        str or None: The device product type, or None if not available or an error occurs.
    """
    try:
        return _cs_client.get('status/product_info/product_name')
    except Exception as e:
        _cs_client.log(f"Error getting device product type: {e}")
        return None

def get_device_name() -> Optional[str]:
    """Return the device name.
    
    Returns:
        str or None: The device name, or None if not available or an error occurs.
    """
    try:
        return _cs_client.get('config/system/system_id')
    except Exception as e:
        _cs_client.log(f"Error getting device name: {e}")
        return None

def get_device_firmware(include_build_info: bool = False) -> str:
    """Return the device firmware information.
    
    Args:
        include_build_info (bool): Whether to include build information. Defaults to False.
    
    Returns:
        str: The device firmware version string, or "Unknown" if an error occurs.
    """
    try:
        fw_info = _cs_client.get('status/fw_info')
        firmware = f"{fw_info.get('major_version')}.{fw_info.get('minor_version')}.{fw_info.get('patch_version')}-{fw_info.get('fw_release_tag')}"
        
        if include_build_info:
            build_info = fw_info.get('build_info', '')
            if build_info:
                firmware += f" ({build_info})"
        
        return firmware
    except Exception as e:
        _cs_client.log(f"Error getting device firmware: {e}")
        return "Unknown"

def get_system_resources(cpu: bool = True, memory: bool = True, storage: bool = False) -> Dict[str, str]:
    """Return a dictionary containing the system resources.
    
    Args:
        cpu (bool): Whether to include CPU information. Defaults to True.
        memory (bool): Whether to include memory information. Defaults to True.
        storage (bool): Whether to include storage information. Defaults to False.
    
    Returns:
        dict: Dictionary containing system resource information with descriptive strings including:
            - cpu (str): CPU usage percentage (e.g., "CPU Usage: 25%") - only if cpu=True
            - avail_mem (str): Available memory in MB (e.g., "Available Memory: 512 MB") - only if memory=True
            - total_mem (str): Total memory in MB (e.g., "Total Memory: 1024 MB") - only if memory=True
            - free_mem (str): Free memory in MB (e.g., "Free Memory: 256 MB") - only if memory=True
            - storage_health (str): Storage health status (e.g., "Storage Health: Good") - only if storage=True
    """
    try:
        system_resources = {}
        
        if cpu:
            cpu = _cs_client.get('status/system/cpu')
            system_resources['cpu'] = f"CPU Usage: {round(float(cpu['nice']) + float(cpu['system']) + float(cpu['user']) * 100)}%"
        if memory:
            memory = _cs_client.get('status/system/memory')
            system_resources['avail_mem'] = f"Available Memory: {memory['memavailable'] / float(1 << 20):,.0f} MB"
            system_resources['total_mem'] = f"Total Memory: {memory['memtotal'] / float(1 << 20):,.0f} MB"
            system_resources['free_mem'] = f"Free Memory: {memory['memfree'] / float(1 << 20):,.0f} MB"
        
        if storage:
            storage_info = _cs_client.get('status/system/storage')
            if storage_info:
                system_resources['storage_health'] = f"Storage Health: {storage_info.get('health', 'Unknown')}"

        return system_resources
    except Exception as e:
        _cs_client.log(f"Error getting system resources: {e}")
        return {}


# ============================================================================
# GPIO FUNCTIONS
# ============================================================================

# Type alias for GPIO names that can be used in function parameters
GPIOType = Literal[
    "power_input", "power_output", "sata_1", "sata_2", "sata_3", "sata_4",
    "sata_ignition_sense", "expander_1", "expander_2", "expander_3", "accessory_1"
]

# GPIO mapping for different router models
GPIO_MAP = {
    'IBR200': {
        'power_input': '/status/gpio/CGPIO_CONNECTOR_INPUT',
        'power_output': '/status/gpio/CGPIO_CONNECTOR_OUTPUT'
    },
    'IBR600': {
        'power_input': '/status/gpio/CONNECTOR_INPUT',
        'power_output': '/status/gpio/CONNECTOR_OUTPUT'
    },
    'IBR900': {
        'power_input': '/status/gpio/CONNECTOR_INPUT',
        'power_output': '/status/gpio/CONNECTOR_OUTPUT',
        'sata_1': '/status/gpio/SATA_GPIO_1',
        'sata_2': '/status/gpio/SATA_GPIO_2',
        'sata_3': '/status/gpio/SATA_GPIO_3',
        'sata_4': '/status/gpio/SATA_GPIO_4',
        'sata_ignition_sense': '/status/gpio/SATA_IGNITION_SENSE'
    },
    'IBR1100': {
        'power_input': '/status/gpio/CGPIO_CONNECTOR_INPUT',
        'power_output': '/status/gpio/CGPIO_CONNECTOR_OUTPUT',
        'expander_1': '/status/gpio/CGPIO_SERIAL_INPUT_1',
        'expander_2': '/status/gpio/CGPIO_SERIAL_INPUT_2',
        'expander_3': '/status/gpio/CGPIO_SERIAL_INPUT_3'
    },
    'R920': {
        'power_input': '/status/gpio/CONNECTOR_GPIO_1',
        'power_output': '/status/gpio/CONNECTOR_GPIO_2'
    },
    'R980': {
        'power_input': '/status/gpio/CONNECTOR_GPIO_1',
        'power_output': '/status/gpio/CONNECTOR_GPIO_2'
    },
    'R1900': {
        'power_input': '/status/gpio/CONNECTOR_GPIO_2',  # UI shows input on power 2
        'power_output': '/status/gpio/CONNECTOR_GPIO_1',  # UI shows output on power 1
        'expander_1': '/status/gpio/EXPANDER_GPIO_1',
        'expander_2': '/status/gpio/EXPANDER_GPIO_2',
        'expander_3': '/status/gpio/EXPANDER_GPIO_3',
        'accessory_1': '/status/gpio/ACCESSORY_GPIO_1'
    }
}


def get_router_model() -> Optional[str]:
    """Extract the router model from the product name.
    
    Returns the part of the product name before the first dash (-) character.
    This is used to determine which GPIO mapping to use for the current router.
    
    Returns:
        str or None: The router model (e.g., 'IBR200', 'R1900'), or None if an error occurs.
    """
    try:
        product_name = get_device_product_type()
        if product_name:
            # Extract everything before the first dash
            model = product_name.split('-')[0]
            return model
        return None
    except Exception as e:
        _cs_client.log(f"Error getting router model: {e}")
        return None


def get_gpio(
    gpio_name: GPIOType, 
    router_model: Optional[str] = None, 
    return_path: bool = False
) -> Optional[Union[Any, str]]:
    """Get the current value or path of a specific GPIO.
    
    Args:
        gpio_name (GPIOType): The name of the GPIO (e.g., 'power_input', 'sata_1').
        router_model (str, optional): The router model. If None, will be determined automatically.
        return_path (bool): If True, returns the GPIO path instead of the value. Defaults to False.
    
    Returns:
        Any, str, or None: The current GPIO value, GPIO path, or None if not found or an error occurs.
    """
    try:
        if router_model is None:
            router_model = get_router_model()
        
        if not router_model:
            _cs_client.log("Unable to determine router model")
            return None
        
        if router_model not in GPIO_MAP:
            _cs_client.log(f"Router model '{router_model}' not found in GPIO mapping")
            return None
        
        if gpio_name not in GPIO_MAP[router_model]:
            _cs_client.log(f"GPIO '{gpio_name}' not found for router model '{router_model}'")
            return None
        
        gpio_path = GPIO_MAP[router_model][gpio_name]
        
        if return_path:
            return gpio_path
        
        # Get the GPIO value
        response = _cs_client.get(gpio_path)
        return response if response is not None else None
    except Exception as e:
        _cs_client.log(f"Error getting GPIO {'path' if return_path else 'value'} for '{gpio_name}': {e}")
        return None


def get_all_gpios(router_model: Optional[str] = None) -> Dict[str, Any]:
    """Get all available GPIO values for the current router model.
    
    Args:
        router_model (str, optional): The router model. If None, will be determined automatically.
    
    Returns:
        dict: Dictionary containing GPIO names as keys and their current values as values.
              Returns empty dict if an error occurs.
    """
    try:
        if router_model is None:
            router_model = get_router_model()
        
        if not router_model or router_model not in GPIO_MAP:
            _cs_client.log(f"Router model '{router_model}' not found in GPIO mapping")
            return {}
        
        gpio_values = {}
        for gpio_name in GPIO_MAP[router_model]:
            value = get_gpio(gpio_name, router_model)
            if value is not None:
                gpio_values[gpio_name] = value
        
        return gpio_values
    except Exception as e:
        _cs_client.log(f"Error getting all GPIO values: {e}")
        return {}


def get_available_gpios(router_model: Optional[str] = None) -> List[str]:
    """Get a list of available GPIO names for the current router model.
    
    Args:
        router_model (str, optional): The router model. If None, will be determined automatically.
    
    Returns:
        list: List of available GPIO names for the current router model.
              Returns empty list if an error occurs.
    """
    try:
        if router_model is None:
            router_model = get_router_model()
        
        if not router_model or router_model not in GPIO_MAP:
            _cs_client.log(f"Router model '{router_model}' not found in GPIO mapping")
            return []
        
        return list(GPIO_MAP[router_model].keys())
    except Exception as e:
        _cs_client.log(f"Error getting available GPIOs: {e}")
        return []


def get_raw_gpios() -> Optional[Dict[str, Any]]:
    """Get all GPIO values directly from the router's /status/gpio endpoint.
    
    This function returns the raw GPIO data from the router, which includes all
    available GPIO pins and their current values, regardless of the router model.
    This is different from get_all_gpios() which only returns GPIOs that
    are mapped for the specific router model.
    
    Returns:
        dict or None: Dictionary containing all GPIO data from the router, or None if an error occurs.
                     The structure depends on the router model and may include:
                     - digital: Dictionary of digital GPIO values
                     - analog: Dictionary of analog GPIO values (if available)
                     - Other GPIO-related data specific to the router model
    """
    try:
        response = _cs_client.get('/status/gpio')
        return response if response is not None else None
    except Exception as e:
        _cs_client.log(f"Error getting raw GPIOs from /status/gpio: {e}")
        return None


def get_ncm_status(include_details: bool = False) -> Optional[str]:
    """Return the NCM status.
    
    Args:
        include_details (bool): Whether to include detailed information. Defaults to False.
    
    Returns:
        str or None: The NCM status, or None if not available or an error occurs.
    """
    try:
        return _cs_client.get('status/ecm/state')
    except Exception as e:
        _cs_client.log(f"Error getting NCM status: {e}")
        return None

def reboot_device(force: bool = False) -> None:
    """Reboot the device.
    
    Args:
        force (bool): Whether to force the reboot. Defaults to False.
    """
    try:
        _cs_client.put('control/system/reboot', 'reboot hypmgr')
    except Exception as e:
        _cs_client.log(f"Error rebooting device: {e}")
    
# Direct access to the underlying EventingCSClient methods
def get(base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying get method.
    
    Args:
        base (str): The base path for the request.
        query (str): Optional query string. Defaults to empty string.
        tree (int): Optional tree identifier. Defaults to 0.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.get(base, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in get request for {base}: {e}")
        return None

def post(base: str, value: Any = '', query: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying post method.
    
    Args:
        base (str): The base path for the request.
        value (Any): The value to post. Defaults to empty string.
        query (str): Optional query string. Defaults to empty string.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.post(base, value, query)
    except Exception as e:
        _cs_client.log(f"Error in post request for {base}: {e}")
        return None

def put(base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying put method.
    
    Args:
        base (str): The base path for the request.
        value (Any): The value to put. Defaults to empty string.
        query (str): Optional query string. Defaults to empty string.
        tree (int): Optional tree identifier. Defaults to 0.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.put(base, value, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in put request for {base}: {e}")
        return None

def delete(base: str, query: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying delete method.
    
    Args:
        base (str): The base path for the request.
        query (str): Optional query string. Defaults to empty string.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.delete(base, query)
    except Exception as e:
        _cs_client.log(f"Error in delete request for {base}: {e}")
        return None

def decrypt(base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying decrypt method.
    
    Args:
        base (str): The base path for the request.
        query (str): Optional query string. Defaults to empty string.
        tree (int): Optional tree identifier. Defaults to 0.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.decrypt(base, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in decrypt request for {base}: {e}")
        return None

def log(value: Union[str, Dict[str, Any]] = '') -> None:
    """Direct access to the underlying log method.
    
    Args:
        value (Union[str, Dict[str, Any]]): The message to log. If a dictionary is provided,
            it will be formatted as JSON with indentation. Defaults to empty string.
    """
    try:
        if _cs_client.enable_logging:
            return _cs_client.log(value)
        else:
            print(value + '\n')
    except Exception as e:
        print(f"Error in log request: {e}")

def alert(value: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying alert method.
    
    Args:
        value (str): The alert message. Defaults to empty string.
    
    Returns:
        dict or None: The response data, or None if an error occurs.
    """
    try:
        return _cs_client.alert(value)
    except Exception as e:
        _cs_client.log(f"Error in alert request: {e}")
        return None

def register(action: str = 'set', path: str = '', callback: Callable = None, *args: Any) -> Dict[str, Any]:
    """Register a callback for a config store event.
    
    Args:
        action (str): The action to listen for (e.g., 'set', 'get'). Defaults to 'set'.
        path (str): The config store path to monitor. Defaults to empty string.
        callback (callable): The function to call when the event occurs. Defaults to None.
        *args: Additional arguments to pass to the callback.
    
    Returns:
        dict: The result of the registration command.
    """
    try:
        return _cs_client.register(action, path, callback, *args)
    except Exception as e:
        _cs_client.log(f"Error in register request for {path}: {e}")
        return {}

# Alias for register function
on = register

def unregister(eid: int = 0) -> Dict[str, Any]:
    """Unregister a callback by its event ID.
    
    Args:
        eid (int): The event ID returned by register. Defaults to 0.
    
    Returns:
        dict: The result of the unregistration command.
    """
    try:
        return _cs_client.unregister(eid)
    except Exception as e:
        _cs_client.log(f"Error in unregister request for eid {eid}: {e}")
        return {}

# Expose the logger for advanced logging control
def get_logger() -> Any:
    """Get the logger instance for advanced logging control.
    
    Returns:
        logging.Logger or None: The logger instance, or None if an error occurs.
    """
    try:
        return _cs_client.logger
    except Exception as e:
        print(f"Error getting logger: {e}")
        return None

# Monkey patch for cp.uptime()
def uptime() -> float:
    """Return the current time in seconds since the epoch.
    
    Returns:
        float: The current time in seconds since the epoch, or 0.0 if an error occurs.
    """
    try:
        return time.time()
    except Exception as e:
        print(f"Error getting uptime: {e}")
        return 0.0
    
def clean_up_reg(signal: Any, frame: Any) -> None:
    """Clean up registrations when receiving SIGTERM signal.
    
    When 'cppython remote_port_forward.py' gets a SIGTERM, config_store_receiver.py doesn't
    clean up registrations. Even if it did, the comm module can't rely on an external service
    to clean up.
    
    Args:
        signal (Any): The signal received.
        frame (Any): The current stack frame.
    """
    try:
        _cs_client.stop()
        sys.exit(0)
    except Exception as e:
        print(f"Error during cleanup: {e}")
        sys.exit(1)


signal.signal(signal.SIGTERM, clean_up_reg)

# ============================================================================
# STATUS MONITORING FUNCTIONS
# ============================================================================

# ============================================================================
# GRANULAR STATUS GET CONVENIENCE FUNCTIONS
# ============================================================================

def get_gps_status() -> Dict[str, Any]:
    """Get GPS status and return detailed information.
    
    Returns:
        dict: Dictionary containing GPS status information including:
            - gps_lock (bool): Whether GPS has a lock
            - satellites (int): Number of satellites in view
            - location (dict): GPS coordinates in degrees/minutes/seconds format
            - latitude (float): GPS latitude in decimal format
            - longitude (float): GPS longitude in decimal format
            - altitude (float): Altitude in meters
            - speed (float): Ground speed in knots
            - heading (float): Heading in degrees
            - accuracy (float): GPS accuracy in meters
            - last_fix_age (int): Age of last GPS fix
    """
    return _cs_client.get_gps_status()

def get_system_status() -> Dict[str, Any]:
    """Get system status and return detailed information.
    
    Returns:
        dict: Dictionary containing system status information including:
            - uptime (int): System uptime in seconds
            - temperature (float): System temperature
            - cpu_usage (dict): CPU usage statistics
            - memory_usage (dict): Memory usage statistics
            - services_running (int): Number of running services
            - services_disabled (int): Number of disabled services
            - internal_apps_running (int): Number of running internal applications
            - external_apps_running (int): Number of running external applications
    """
    return _cs_client.get_system_status()

def get_wlan_status() -> Dict[str, Any]:
    """Get WLAN status and return detailed information.
    
    Returns:
        dict: Dictionary containing WLAN status information including:
            - wlan_state (str): WLAN operational state
            - radios (list): List of radio information
            - clients_connected (int): Number of connected clients
            - interfaces (list): List of interface information
    """
    return _cs_client.get_wlan_status()

def get_wan_status() -> Dict[str, Any]:
    """Get WAN status and return detailed information.
    
    Returns:
        dict: Dictionary containing WAN status information including:
            - primary_device (str): Primary WAN device identifier
            - connection_state (str): Overall connection state
            - cellular_health_score (str): Overall cellular health score
            - devices (list): List of WAN device information including:
                - uid (str): Device unique identifier
                - connection_state (str): Device connection state
                - signal_strength (str): Signal strength indicator
                - cellular_health (str): Cellular health category
                - ip_address (str): Device IP address
                - uptime (int): Device uptime in seconds
                - For modem devices (uid starts with "mdm"), additional fields:
                    - active_apn (str): Active APN name
                    - carrier_id (str): Carrier identifier
                    - cell_id (str): Cell tower identifier
                    - cur_plmn (str): Current PLMN code
                    - dbm (str): Signal strength in dBm
                    - imei (str): Device IMEI
                    - lte_bandwidth (str): LTE bandwidth
                    - model (str): Device model
                    - mdn (str): Mobile directory number
                    - home_carrier (str): Home carrier
                    - phy_cell_id (str): Physical cell ID
                    - rf_band (str): Radio frequency band
                    - rf_channel (str): Radio frequency channel
                    - rsrp (str): Reference signal received power
                    - rsrq (str): Reference signal received quality
                    - service_discovery (str): Service discovery info
                    - sim_number (str): SIM slot number
                    - sinr (str): Signal to interference plus noise ratio
                    - service_type (str): Service type (4G/5G)
                    - service_type_details (str): Detailed service information
                    - tac (str): Tracking area code
                    - dl_frequency (str): Downlink frequency
                    - ul_frequency (str): Uplink frequency
                    - rsrp_5g (str): 5G RSRP value
                    - rsrq_5g (str): 5G RSRQ value
                    - sinr_5g (str): 5G SINR value
                    - stats (dict): Device statistics including:
                        - collisions (int): Collision count
                        - idrops (int): Input drop count
                        - ierrors (int): Input error count
                        - in_bytes (int): Input bytes
                        - ipackets (int): Input packet count
                        - multicast (int): Multicast count
                        - odrops (int): Output drop count
                        - oerrors (int): Output error count
                        - opackets (int): Output packet count
                        - out_bytes (int): Output bytes
                - For ethernet devices (uid starts with "ethernet"), additional fields:
                    - capabilities (str): Device capabilities
                    - config_id (str): Configuration identifier
                    - interface (str): Interface name
                    - mac_address (str): MAC address
                    - mtu (int): Maximum transmission unit
                    - port (str): Port number
                    - port_name (dict): Port name mapping
                    - type (str): Device type
    """
    return _cs_client.get_wan_status()

def get_wan_devices() -> Dict[str, Any]:
    """Get WAN device information only.
    
    Returns:
        dict: Dictionary containing WAN device information including:
            - primary_device (str): Primary WAN device identifier
            - devices (list): List of WAN device information including:
                - uid (str): Device unique identifier
                - connection_state (str): Device connection state
                - signal_strength (str): Signal strength indicator
                - cellular_health (str): Cellular health category
                - ip_address (str): Device IP address
                - uptime (int): Device uptime in seconds
    """
    return _cs_client.get_wan_devices()

def get_wan_modem_diagnostics(device_id: str) -> Dict[str, Any]:
    """Get modem diagnostics for a specific WAN device.
    
    Args:
        device_id (str): WAN device identifier to get diagnostics for
        
    Returns:
        dict: Dictionary containing modem diagnostics including:
            - device_id (str): Device identifier
            - diagnostics (dict): Modem diagnostics including:
                - active_apn (str): Active APN name
                - carrier_id (str): Carrier identifier
                - cell_id (str): Cell tower identifier
                - cur_plmn (str): Current PLMN code
                - dbm (str): Signal strength in dBm
                - imei (str): Device IMEI
                - lte_bandwidth (str): LTE bandwidth
                - model (str): Device model
                - mdn (str): Mobile directory number
                - home_carrier (str): Home carrier
                - phy_cell_id (str): Physical cell ID
                - rf_band (str): Radio frequency band
                - rf_channel (str): Radio frequency channel
                - rsrp (str): Reference signal received power
                - rsrq (str): Reference signal received quality
                - service_discovery (str): Service discovery info
                - sim_number (str): SIM slot number
                - sinr (str): Signal to interference plus noise ratio
                - service_type (str): Service type (4G/5G)
                - service_type_details (str): Detailed service information
                - tac (str): Tracking area code
                - dl_frequency (str): Downlink frequency
                - ul_frequency (str): Uplink frequency
                - rsrp_5g (str): 5G RSRP value
                - rsrq_5g (str): 5G RSRQ value
                - sinr_5g (str): 5G SINR value
    """
    return _cs_client.get_wan_modem_diagnostics(device_id)

def get_wan_modem_stats(device_id: str) -> Dict[str, Any]:
    """Get modem statistics for a specific WAN device.
    
    Args:
        device_id (str): WAN device identifier to get statistics for
        
    Returns:
        dict: Dictionary containing modem statistics including:
            - device_id (str): Device identifier
            - stats (dict): Modem statistics including:
                - collisions (int): Collision count
                - idrops (int): Input drop count
                - ierrors (int): Input error count
                - in_bytes (int): Input bytes
                - ipackets (int): Input packet count
                - multicast (int): Multicast count
                - odrops (int): Output drop count
                - oerrors (int): Output error count
                - opackets (int): Output packet count
                - out_bytes (int): Output bytes
    """
    return _cs_client.get_wan_modem_stats(device_id)

def get_wan_ethernet_info(device_id: str) -> Dict[str, Any]:
    """Get ethernet device information for a specific WAN device.
    
    Args:
        device_id (str): WAN device identifier to get information for
        
    Returns:
        dict: Dictionary containing ethernet device information including:
            - device_id (str): Device identifier
            - info (dict): Ethernet device information including:
                - capabilities (str): Device capabilities
                - config_id (str): Configuration identifier
                - interface (str): Interface name
                - mac_address (str): MAC address
                - mtu (int): Maximum transmission unit
                - port (str): Port number
                - port_name (dict): Port name mapping
                - type (str): Device type
    """
    return _cs_client.get_wan_ethernet_info(device_id)

def get_lan_status() -> Dict[str, Any]:
    """Get LAN status and return detailed information.
    
    Returns:
        dict: Dictionary containing LAN status information including:
            - total_ipv4_clients (int): Number of connected IPv4 clients
            - total_ipv6_clients (int): Number of connected IPv6 clients
            - lan_stats (dict): Overall LAN statistics including:
                - bps (int): Total bits per second
                - collisions (int): Collision count
                - ibps (int): Input bits per second
                - idrops (int): Input drop count
                - ierrors (int): Input error count
                - imcasts (int): Input multicast count
                - in_bytes (int): Input bytes
                - ipackets (int): Input packet count
                - noproto (int): No protocol count
                - obps (int): Output bits per second
                - oerrors (int): Output error count
                - omcasts (int): Output multicast count
                - opackets (int): Output packet count
                - out_bytes (int): Output bytes
                - timestamp (float): Statistics timestamp
            - ipv4_clients (list): List of connected IPv4 clients including:
                - ip_address (str): Client IP address
                - mac (str): Client MAC address
            - ipv6_clients (list): List of connected IPv6 clients including:
                - ip_address (str): Client IP address
                - mac (str): Client MAC address
            - networks (list): List of network information including:
                - name (str): Network identifier
                - display_name (str): Human-readable network name
                - ip_address (str): Network IP address
                - netmask (str): Network netmask
                - broadcast (str): Network broadcast address
                - hostname (str): Network hostname
                - type (str): Network type
                - devices (list): Network devices including:
                    - interface (str): Device interface name
                    - state (str): Device state
                    - type (str): Device type
                    - uid (str): Device unique identifier
            - devices (list): List of device information with statistics including:
                - name (str): Device name
                - interface (str): Device interface
                - link_state (str): Device link state
                - type (str): Device type
                - stats (dict): Device statistics including:
                    - collisions (int): Collision count
                    - idrops (int): Input drop count
                    - ierrors (int): Input error count
                    - in_bytes (int): Input bytes
                    - ipackets (int): Input packet count
                    - multicast (int): Multicast count
                    - odrops (int): Output drop count
                    - oerrors (int): Output error count
                    - opackets (int): Output packet count
                    - out_bytes (int): Output bytes
    """
    return _cs_client.get_lan_status()

def get_lan_clients() -> Dict[str, Any]:
    """Get LAN client information only.
    
    Returns:
        dict: Dictionary containing LAN client information including:
            - total_ipv4_clients (int): Number of connected IPv4 clients
            - total_ipv6_clients (int): Number of connected IPv6 clients
            - ipv4_clients (list): List of connected IPv4 clients including:
                - ip_address (str): Client IP address
                - mac (str): Client MAC address
            - ipv6_clients (list): List of connected IPv6 clients including:
                - ip_address (str): Client IP address
                - mac (str): Client MAC address
    """
    return _cs_client.get_lan_clients()

def get_lan_networks() -> Dict[str, Any]:
    """Get LAN network information only.
    
    Returns:
        dict: Dictionary containing LAN network information including:
            - networks (list): List of network information including:
                - name (str): Network identifier
                - display_name (str): Human-readable network name
                - ip_address (str): Network IP address
                - netmask (str): Network netmask
                - broadcast (str): Network broadcast address
                - hostname (str): Network hostname
                - type (str): Network type
                - devices (list): Network devices including:
                    - interface (str): Device interface name
                    - state (str): Device state
                    - type (str): Device type
                    - uid (str): Device unique identifier
    """
    return _cs_client.get_lan_networks()

def get_lan_devices() -> Dict[str, Any]:
    """Get LAN device information only.
    
    Returns:
        dict: Dictionary containing LAN device information including:
            - devices (list): List of device information including:
                - name (str): Device name
                - interface (str): Device interface
                - link_state (str): Device link state
                - type (str): Device type
    """
    return _cs_client.get_lan_devices()

def get_lan_statistics() -> Dict[str, Any]:
    """Get overall LAN statistics only.
    
    Returns:
        dict: Dictionary containing LAN statistics including:
            - lan_stats (dict): Overall LAN statistics including:
                - bps (int): Total bits per second
                - collisions (int): Collision count
                - ibps (int): Input bits per second
                - idrops (int): Input drop count
                - ierrors (int): Input error count
                - imcasts (int): Input multicast count
                - in_bytes (int): Input bytes
                - ipackets (int): Input packet count
                - noproto (int): No protocol count
                - obps (int): Output bits per second
                - oerrors (int): Output error count
                - omcasts (int): Output multicast count
                - opackets (int): Output packet count
                - out_bytes (int): Output bytes
                - timestamp (float): Statistics timestamp
    """
    return _cs_client.get_lan_statistics()

def get_lan_device_stats(device_name: str) -> Dict[str, Any]:
    """Get statistics for a specific LAN device.
    
    Args:
        device_name (str): Name of the LAN device to get statistics for
        
    Returns:
        dict: Dictionary containing device statistics including:
            - device_name (str): Name of the device
            - stats (dict): Device statistics including:
                - collisions (int): Collision count
                - idrops (int): Input drop count
                - ierrors (int): Input error count
                - in_bytes (int): Input bytes
                - ipackets (int): Input packet count
                - multicast (int): Multicast count
                - odrops (int): Output drop count
                - oerrors (int): Output error count
                - opackets (int): Output packet count
                - out_bytes (int): Output bytes
    """
    return _cs_client.get_lan_device_stats(device_name)

def get_openvpn_status() -> Dict[str, Any]:
    """Get OpenVPN status and return detailed information.
    
    Returns:
        dict: Dictionary containing OpenVPN status information including:
            - tunnels_configured (int): Number of configured tunnels
            - tunnels_active (int): Number of active tunnels
            - stats_available (bool): Whether statistics are available
    """
    return _cs_client.get_openvpn_status()

def get_hotspot_status() -> Dict[str, Any]:
    """Get hotspot status and return detailed information.
    
    Returns:
        dict: Dictionary containing hotspot status information including:
            - clients_connected (int): Number of connected clients
            - sessions_active (int): Number of active sessions
            - domains_allowed (int): Number of allowed domains
            - hosts_allowed (int): Number of allowed hosts
            - rate_limit_triggered (bool): Whether rate limiting is triggered
    """
    return _cs_client.get_hotspot_status()

def get_obd_status() -> Dict[str, Any]:
    """Get OBD status and return detailed information.
    
    Returns:
        dict: Dictionary containing OBD status information including:
            - adapter_configured (bool): Whether OBD adapter is configured
            - adapter_connected (bool): Whether OBD adapter is connected
            - vehicle_connected (bool): Whether vehicle is connected
            - pids_supported (int): Number of supported PIDs
            - pids_enabled (int): Number of enabled PIDs
            - ignition_status (str): Vehicle ignition status
            - pids (list): List of PID information including:
                - config_name (str): PID configuration name
                - enabled (bool): Whether PID is enabled
                - last_value (str): Last value received for this PID
                - name (str): PID name
                - pid (int): PID identifier
                - supported (bool): Whether PID is supported by vehicle
                - units (str): Units for PID values
                - update_interval (int): Update interval in milliseconds
                - values (list): Historical values for this PID
    """
    return _cs_client.get_obd_status()

def get_qos_status() -> Dict[str, Any]:
    """Get QoS status and return detailed information.
    
    Returns:
        dict: Dictionary containing QoS status information including:
            - qos_enabled (bool): Whether QoS is enabled
            - queues_configured (int): Number of configured queues
            - queues_active (int): Number of active queues
            - total_packets (int): Total packets processed
    """
    return _cs_client.get_qos_status()

def get_firewall_status() -> Dict[str, Any]:
    """Get firewall status and return detailed information.
    
    Returns:
        dict: Dictionary containing firewall status information including:
            - connections_tracked (int): Number of tracked connections
            - state_timeouts (dict): State timeout configurations
            - hitcounters (list): List of firewall rule hit counters
    """
    return _cs_client.get_firewall_status()

def get_dns_status() -> Dict[str, Any]:
    """Get DNS status and return detailed information.
    
    Returns:
        dict: Dictionary containing DNS status information including:
            - cache_entries (int): Number of cache entries
            - cache_size (int): Cache size
            - servers_configured (int): Number of configured DNS servers
            - queries_forwarded (int): Number of forwarded queries
    """
    return _cs_client.get_dns_status()

def get_dhcp_status() -> Dict[str, Any]:
    """Get DHCP status and return detailed information.
    
    Returns:
        dict: Dictionary containing DHCP status information including:
            - total_leases (int): Total number of DHCP leases
            - active_leases (int): Number of active leases
            - leases_by_interface (dict): Leases grouped by interface
            - leases_by_network (dict): Leases grouped by network
            - leases (list): List of all DHCP leases including:
                - client_id (str): Client identifier
                - expire (int): Lease expiration time
                - hostname (str): Client hostname
                - iface (str): Interface name
                - iface_type (str): Interface type (ethernet, wireless, etc.)
                - ip_address (str): Assigned IP address
                - mac (str): Client MAC address
                - network (str): Network name
                - ssid (str): SSID for wireless clients
    """
    return _cs_client.get_dhcp_status()

# ============================================================================
# STATUS MONITORING FUNCTIONS
# ============================================================================

def get_wan_devices_status() -> Optional[Dict[str, Any]]:
    """Return detailed status information for all WAN devices.
    
    Returns:
        dict or None: Dictionary containing all WAN devices with keys like 'mdm-{id}', 'eth-{id}', etc.
              Each device contains:
              - config (dict): Device configuration
              - diagnostics (dict): Detailed diagnostic information
              - info (dict): Device information (model, carrier, firmware, etc.)
              - ob_upgrade (dict): Over-the-air upgrade information
              - remote_upgrade (dict): Remote upgrade status
              - stats (dict): Device statistics
              - status (dict): Connection status with GPS and signal information
    """
    try:
        wan_devices = _cs_client.get('status/wan/devices')
        return wan_devices
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WAN devices status: {e}")
        return None

def get_modem_status() -> Optional[Dict[str, Any]]:
    """Return detailed status information for cellular modem devices only.
    
    Returns:
        dict or None: Dictionary containing only modem devices with keys like 'mdm-{id}'.
              Each modem contains:
              - config (dict): Modem configuration
              - diagnostics (dict): Detailed diagnostic information including:
                  - CARRIER_ID (str): Carrier name
                  - CELL_ID (str): Cell tower ID
                  - DBM (str): Signal strength in dBm
                  - RSRP (str): Reference signal received power
                  - RSRQ (str): Reference signal received quality
                  - SINR (str): Signal to interference plus noise ratio
                  - SRVC_TYPE (str): Service type (5G, LTE, etc.)
                  - MODEMTEMP (str): Modem temperature
                  - APN information and band details
              - info (dict): Modem information (model, carrier, firmware, etc.)
              - ob_upgrade (dict): Over-the-air upgrade information
              - remote_upgrade (dict): Remote upgrade status
              - stats (dict): Modem statistics
              - status (dict): Connection status with GPS and signal information
    """
    try:
        all_devices = _cs_client.get('status/wan/devices')
        modem_devices = {}
        
        if all_devices:
            for device_id, device_data in all_devices.items():
                if device_id.startswith('mdm-'):
                    modem_devices[device_id] = device_data
        
        return modem_devices
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving modem status: {e}")
        return None

def get_signal_strength() -> Optional[Dict[str, Any]]:
    """Return signal strength information for all cellular modems.
    
    Returns:
        dict or None: Dictionary with modem IDs as keys, containing:
            - signal_strength (str): Signal strength percentage
            - signal_backlog (list): Historical signal data with timestamps
            - cellular_health_score (float): Health score (0-100)
            - cellular_health_category (str): Health category (excellent, good, etc.)
            - connection_state (str): Connection status (connected, disconnected, etc.)
            - diagnostics (dict): Detailed diagnostic information including:
                - DBM (str): Signal strength in dBm
                - RSRP (str): Reference signal received power
                - RSRQ (str): Reference signal received quality
                - SINR (str): Signal to interference plus noise ratio
                - SRVC_TYPE (str): Service type (5G, LTE, etc.)
                - CARRIER_ID (str): Carrier name
                - CELL_ID (str): Cell tower ID
    """
    try:
        # Get only modem devices and extract signal strength info
        modem_devices = get_modem_status()
        signal_info = {}
        
        if modem_devices:
            for device_id, device_data in modem_devices.items():
                status = device_data.get('status', {})
                diagnostics = device_data.get('diagnostics', {})
                signal_info[device_id] = {
                    'signal_strength': status.get('signal_strength'),
                    'signal_backlog': status.get('signal_backlog', []),
                    'cellular_health_score': status.get('cellular_health_score'),
                    'cellular_health_category': status.get('cellular_health_category'),
                    'connection_state': status.get('connection_state'),
                    'diagnostics': {
                        'dbm': diagnostics.get('DBM'),
                        'rsrp': diagnostics.get('RSRP'),
                        'rsrq': diagnostics.get('RSRQ'),
                        'sinr': diagnostics.get('SINR'),
                        'service_type': diagnostics.get('SRVC_TYPE'),
                        'carrier_id': diagnostics.get('CARRID'),
                        'cell_id': diagnostics.get('CELL_ID'),
                        'modem_temp': diagnostics.get('MODEMTEMP')
                    }
                }
        
        return signal_info
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving signal strength: {e}")
        return None

def get_temperature(unit: str = 'fahrenheit') -> Optional[float]:
    """Return device temperature information.
    
    Args:
        unit (str): Temperature unit ('celsius' or 'fahrenheit'). Defaults to 'fahrenheit'.
    
    Returns:
        float or None: Device temperature in the specified unit, or None if not available.
    """
    try:
        # Temperature is a direct value, not a directory
        temp = _cs_client.get('status/system/temperature')
        if temp is None:
            return None
        
        # Convert to Fahrenheit if requested (default), otherwise return Celsius
        if unit.lower() == 'fahrenheit':
            return (temp * 9/5) + 32
        return temp
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving temperature: {e}")
        return None

def get_power_usage(include_components: bool = True) -> Optional[Dict[str, Any]]:
    """Return power usage information.
    
    Args:
        include_components (bool): Whether to include individual component power usage.
                                  Defaults to True.
    
    Returns:
        dict or None: Dictionary containing power usage information including:
            - total (float): Total power usage
            - system_power (float): System power usage
            - cpu_power (float): CPU power usage
            - modem_power (float): Modem power usage
            - wifi_power (float): WiFi power usage
            - poe_pse_power (float): PoE PSE power usage
            - ethernet_ports_power (float): Ethernet ports power usage
            - bluetooth_power (float): Bluetooth power usage
            - usb_power (float): USB power usage
            - gps_power (float): GPS power usage
            - led_power (float): LED power usage
    """
    try:
        power_components = {}
        
        if include_components:
            components = ['system_power', 'cpu_power', 'modem_power', 'wifi_power', 
                         'poe_pse_power', 'ethernet_ports_power', 'bluetooth_power', 
                         'usb_power', 'gps_power', 'led_power']
            
            for component in components:
                try:
                    value = _cs_client.get(f'status/power_usage/{component}')
                    power_components[component] = value
                except:
                    power_components[component] = None
        
        # Always include total
        try:
            total_power = _cs_client.get('status/power_usage/total')
            power_components['total'] = total_power
        except:
            power_components['total'] = None
        
        return power_components
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving power usage: {e}")
        return None

def get_wlan_status() -> Optional[Dict[str, Any]]:
    """Return comprehensive wireless LAN status and configuration information.
    
    Returns:
        dict or None: Dictionary containing all WLAN status information including
              clients, radio details, events, region settings, and trace data.
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN status: {e}")
        return None

def get_wlan_clients() -> List[Dict[str, Any]]:
    """Return connected wireless clients information.
    
    Returns:
        list: List of connected wireless clients with their details including:
            - mac (str): MAC address of the client
            - hostname (str): Hostname of the client
            - ip_address (str): IP address of the client
            - radio (int): Radio ID the client is connected to
            - bss (int): BSS ID the client is connected to
            - ssid (str): SSID the client is connected to
            - mode (int): Wi-Fi mode
            - bw (int): Bandwidth mode
            - txrate (int): Transmit rate
            - rssi (int): Signal strength
            - time (int): Connection time
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('clients', []) if wlan_status else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN clients: {e}")
        return []

def get_wlan_radio_status() -> List[Dict[str, Any]]:
    """Return wireless radio status and configuration for all bands.
    
    Returns:
        list: List of radio configurations for each band (2.4 GHz, 5 GHz) containing:
            - band (str): Frequency band (2.4 GHz, 5 GHz)
            - bss (list): Basic Service Set information with BSSIDs
            - channel (int): Current channel number
            - channel_contention (int): Channel contention value
            - channel_list (list): Available channels
            - channel_locked (bool): Whether channel is locked
            - clients (list): Clients connected to this radio
            - reconnecting (bool): Reconnection status
            - region_code (int): Regional code
            - survey (list): Channel survey data
            - txpower (int): Transmit power in percentage
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('radio', []) if wlan_status else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN radio status: {e}")
        return []

def get_wlan_radio_by_band(band: str = '2.4 GHz') -> Optional[Dict[str, Any]]:
    """Return wireless radio status for a specific frequency band.
    
    Args:
        band (str): Frequency band ('2.4 GHz' or '5 GHz'). Defaults to '2.4 GHz'.
    
    Returns:
        dict or None: Radio configuration for the specified band, or None if not found.
    """
    try:
        radio_status = get_wlan_radio_status()
        for radio in radio_status:
            if radio.get('band') == band:
                return radio
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN radio for band {band}: {e}")
        return None

def get_wlan_events() -> Dict[str, Any]:
    """Return wireless LAN events and monitoring data.
    
    Returns:
        dict: Dictionary containing WiFi events:
            - associate (list): Association events
            - deauthenticated (list): Deauthentication events
            - disassociate (list): Disassociation events
            - mac_filter_allow (list): MAC filter allow events
            - mac_filter_deny (list): MAC filter deny events
            - timeout (list): Timeout events
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('events', {}) if wlan_status else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN events: {e}")
        return {}

def get_wlan_region_config() -> Dict[str, Any]:
    """Return wireless LAN regional configuration settings.
    
    Returns:
        dict: Dictionary containing regional settings:
            - country_code (str): Country code
            - global_wifi (bool): Global WiFi enabled
            - mobile (bool): Mobile mode enabled
            - override (bool): Override settings
            - reboot_needed (bool): Reboot required
            - regions_supported (list): Supported regions
            - safe_mode (bool): Safe mode enabled
            - version (int): Version number
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('region', {}) if wlan_status else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN region config: {e}")
        return {}

def get_wlan_remote_status() -> Dict[str, Any]:
    """Return remote WiFi controller status and configuration.
    
    Returns:
        dict: Dictionary containing remote WiFi information:
            - radio (list): Remote radio information
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('remote', {}) if wlan_status else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN remote status: {e}")
        return {}

def get_wlan_state() -> str:
    """Return wireless LAN operational state.
    
    Returns:
        str: WiFi state ('On', 'Off', or 'Unknown' if an error occurs).
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('state', 'Unknown') if wlan_status else 'Unknown'
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN state: {e}")
        return 'Unknown'

def get_wlan_trace() -> List[Dict[str, Any]]:
    """Return wireless LAN initialization trace data.
    
    Returns:
        list: List of trace events with:
            - timestamp (float): Event timestamp
            - thread_id (str): Thread identifier
            - event_id (int): Event ID
            - event_data (str): Event details
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('trace', []) if wlan_status else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN trace: {e}")
        return []

def get_wlan_debug() -> Dict[str, Any]:
    """Return wireless LAN debug information.
    
    Returns:
        dict: Dictionary containing debug information:
            - state (int): Debug state
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('debug', {}) if wlan_status else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN debug: {e}")
        return {}

def get_wlan_channel_info(band: Optional[str] = None, include_survey: bool = False) -> Dict[str, Any]:
    """Return wireless LAN channel information for specified band or all bands.
    
    Args:
        band (str, optional): Frequency band ('2.4 GHz' or '5 GHz'). If None, returns all bands.
                              Defaults to None.
        include_survey (bool, optional): Include channel survey data. Defaults to False.
    
    Returns:
        dict: Dictionary containing channel information:
            - current_channel (int): Current channel number
            - available_channels (list): List of available channels
            - channel_locked (bool): Whether channel is locked
            - channel_contention (int): Channel contention value
            - txpower (int): Transmit power in percentage
            - survey_data (list, optional): Channel survey data if include_survey is True
    """
    try:
        if band:
            radio = get_wlan_radio_by_band(band)
            if radio:
                channel_info = {
                    'current_channel': radio.get('channel'),
                    'available_channels': radio.get('channel_list', []),
                    'channel_locked': radio.get('channel_locked', False),
                    'channel_contention': radio.get('channel_contention', 0),
                    'txpower': radio.get('txpower', 0)
                }
                if include_survey:
                    channel_info['survey_data'] = radio.get('survey', [])
                return channel_info
            return {}
        else:
            # Return channel info for all bands
            radio_status = get_wlan_radio_status()
            channel_info = {}
            for radio in radio_status:
                band_name = radio.get('band', 'Unknown')
                channel_info[band_name] = {
                    'current_channel': radio.get('channel'),
                    'available_channels': radio.get('channel_list', []),
                    'channel_locked': radio.get('channel_locked', False),
                    'channel_contention': radio.get('channel_contention', 0),
                    'txpower': radio.get('txpower', 0)
                }
                if include_survey:
                    channel_info[band_name]['survey_data'] = radio.get('survey', [])
            return channel_info
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN channel info: {e}")
        return {}

def get_wlan_client_count() -> int:
    """Return the count of connected wireless clients.
    
    Returns:
        int: Number of connected wireless clients, or 0 if an error occurs.
    """
    try:
        clients = get_wlan_clients()
        return len(clients)
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN client count: {e}")
        return 0

def get_wlan_client_count_by_band() -> Dict[str, int]:
    """Return the count of connected wireless clients per frequency band.
    
    Returns:
        dict: Dictionary with band names as keys and client counts as values.
    """
    try:
        radio_status = get_wlan_radio_status()
        client_counts = {}
        for radio in radio_status:
            band_name = radio.get('band', 'Unknown')
            clients = radio.get('clients', [])
            client_counts[band_name] = len(clients)
        return client_counts
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN client count by band: {e}")
        return {}

def get_dhcp_leases() -> Optional[List[Dict[str, Any]]]:
    """Return DHCP lease information.
    
    Returns:
        list or None: List of DHCP leases with client information including:
            - mac (str): MAC address of the client
            - hostname (str): Hostname of the client
            - ip_address (str): IP address of the client
            - network (str): Network the client is connected to
            - iface (str): Interface name
            - lease_time (int): Lease time in seconds
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        return leases
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP leases: {e}")
        return None

def get_routing_table() -> Optional[Dict[str, Any]]:
    """Return routing table information.
    
    Returns:
        dict or None: Dictionary containing routing table information including:
            - static routes
            - dynamic routes
            - routing policies
            - BGP and OSPF information
    """
    try:
        routes = _cs_client.get('status/routing')
        return routes
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving routing table: {e}")
        return None

def get_certificate_status() -> Optional[Dict[str, Any]]:
    """Return certificate management status.
    
    Returns:
        dict or None: Dictionary containing certificate management information including:
            - installed certificates
            - certificate details
            - CA fingerprints
            - certificate status
    """
    try:
        cert_status = _cs_client.get('status/certmgmt')
        return cert_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate status: {e}")
        return None

def get_storage_status(include_detailed: bool = False) -> Optional[Dict[str, Any]]:
    """Return storage device status.
    
    Args:
        include_detailed (bool): Whether to include detailed storage information. Defaults to False.
    
    Returns:
        dict or None: Dictionary containing storage status information including:
            - health (str): Storage health status
            - slc_health (str): SLC health status
            - detailed information if include_detailed is True
    """
    try:
        storage_status = {
            'health': _cs_client.get('status/system/storage/health'),
            'slc_health': _cs_client.get('status/system/storage/slc_health')
        }
        
        if include_detailed:
            # Add more detailed storage information if available
            try:
                storage_info = _cs_client.get('status/system/storage')
                if storage_info:
                    storage_status.update(storage_info)
            except:
                pass
        
        return storage_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving storage status: {e}")
        return None

def get_usb_status(include_all_ports: bool = False) -> Optional[Dict[str, Any]]:
    """Return USB device status.
    
    Args:
        include_all_ports (bool): Whether to include all USB ports. Defaults to False.
    
    Returns:
        dict or None: Dictionary containing USB status information including:
            - connection (dict): USB connection status
            - int1 (dict): USB interface 1 information
            - additional port information if include_all_ports is True
    """
    try:
        usb_status = {
            'connection': _cs_client.get('status/usb/connection'),
            'int1': _cs_client.get('status/usb/int1')
        }
        
        if include_all_ports:
            # Add all USB ports if available
            try:
                usb_info = _cs_client.get('status/usb')
                if usb_info:
                    usb_status.update(usb_info)
            except:
                pass
        
        return usb_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving USB status: {e}")
        return None

def get_poe_status() -> Optional[Dict[str, Any]]:
    """Return Power over Ethernet status.
    
    Returns:
        dict or None: Dictionary containing PoE status information including:
            - PoE PSE (Power Sourcing Equipment) status
            - Power delivery information
            - Connected device power requirements
    """
    try:
        # PoE directory appears to be empty on this router
        poe_status = _cs_client.get('status/system/poe_pse')
        return poe_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving PoE status: {e}")
        return None

def get_sensors_status() -> Optional[Dict[str, Any]]:
    """Return sensor status information.
    
    Returns:
        dict or None: Dictionary containing sensor status information including:
            - level (dict): Level sensor information
            - day (dict): Day sensor information
    """
    try:
        sensors_status = {
            'level': _cs_client.get('status/system/sensors/level'),
            'day': _cs_client.get('status/system/sensors/day')
        }
        return sensors_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving sensors status: {e}")
        return None

def get_services_status() -> Optional[Dict[str, Any]]:
    """Return system services status.
    
    Returns:
        dict or None: Dictionary containing system services status including:
            - service names as keys
            - service state information (started, stopped, disabled, etc.)
            - service configuration details
    """
    try:
        services_status = _cs_client.get('status/system/services')
        return services_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving services status: {e}")
        return None

def get_apps_status() -> Optional[Dict[str, Any]]:
    """Return both internal system applications and external SDK applications status.
    
    Returns:
        dict or None: Dictionary containing application status information including:
            - internal_apps (list): List of internal system applications including:
            - app name and identifier
            - app state (started, stopped, etc.)
            - app configuration and runtime information
            - external_apps (list): List of external SDK applications including:
                - app name and identifier
                - app state (started, stopped, etc.)
                - app configuration and runtime information
            - total_apps (int): Total number of applications
            - running_apps (int): Total number of running applications
    """
    try:
        # Get internal system apps
        internal_apps = _cs_client.get('status/system/apps') or []
        
        # Get external SDK apps
        sdk_data = _cs_client.get('status/system/sdk') or {}
        external_apps = sdk_data.get('apps', [])
        
        # Calculate totals
        total_apps = len(internal_apps) + len(external_apps)
        running_apps = (
            len([app for app in internal_apps if app.get('state') == 'started']) +
            len([app for app in external_apps if app.get('state') == 'started'])
        )
        
        return {
            'internal_apps': internal_apps,
            'external_apps': external_apps,
            'total_apps': total_apps,
            'running_apps': running_apps
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving apps status: {e}")
        return None



def get_event_status() -> Optional[Dict[str, Any]]:
    """Return system events status.
    
    Returns:
        dict or None: Dictionary containing system events status including:
            - event configuration
            - event history
            - event processing status
    """
    try:
        event_status = _cs_client.get('status/event')
        return event_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving event status: {e}")
        return None



def get_flow_statistics() -> Optional[Dict[str, Any]]:
    """Return flow statistics with destination-based flow information.
    
    Returns:
        dict or None: Dictionary containing flow statistics including:
            - total_destinations (int): Total number of destination flows
            - total_packets (int): Total packets across all flows
            - destinations (list): List of destination flow information including:
                - appid (int): Application identifier
                - bytesin (int): Bytes received from destination
                - bytesout (int): Bytes sent to destination
                - catid (int): Category identifier
                - conns (int): Number of connections
                - destination (str): Destination IP address
                - iface (str): Interface name
                - latency (int): Connection latency
                - pktin (int): Packets received from destination
                - pktout (int): Packets sent to destination
                - samples (int): Number of latency samples
                - sumsquare (int): Sum of squared latency values
                - tcppkts (int): TCP packet count
                - udppkts (int): UDP packet count
    """
    try:
        flow_stats = _cs_client.get('status/flowstats')
        if not flow_stats:
            return {}
        
        ipdst_data = flow_stats.get("ipdst", {})
        destinations = ipdst_data.get("destinations", [])
        
        return {
            "total_destinations": ipdst_data.get("totaldsts", 0),
            "total_packets": ipdst_data.get("totalpkts", 0),
            "destinations": destinations
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving flow statistics: {e}")
        return None

def get_client_usage() -> Optional[Dict[str, Any]]:
    """Return detailed client usage statistics with bandwidth and connection information.
    
    Returns:
        dict or None: Dictionary containing client usage statistics including:
            - enabled (bool): Whether client usage tracking is enabled
            - total_clients (int): Total number of clients with usage data
            - total_traffic (dict): Summary of total traffic across all clients
            - stats (list): List of client usage statistics including:
                - app_list (list): List of applications used by client
                - connect_time (int): Current connection time in seconds
                - down_bytes (int): Total download bytes
                - down_delta (int): Download bytes since last reset
                - down_packets (int): Total download packets
                - first_time (int): First connection timestamp
                - ip (str): Client IP address
                - last_time (int): Last activity timestamp
                - mac (str): Client MAC address
                - name (str): Client hostname or identifier
                - network (str): Network name client is connected to
                - ssid (str): SSID for wireless clients
                - type (str): Client connection type (wireless, ethernet, etc.)
                - up_bytes (int): Total upload bytes
                - up_delta (int): Upload bytes since last reset
                - up_packets (int): Total upload packets
    """
    try:
        client_usage = _cs_client.get('status/client_usage')
        if not client_usage:
            return {}
        
        stats = client_usage.get("stats", [])
        
        # Calculate total traffic across all clients
        total_down_bytes = sum(client.get("down_bytes", 0) for client in stats)
        total_up_bytes = sum(client.get("up_bytes", 0) for client in stats)
        total_down_packets = sum(client.get("down_packets", 0) for client in stats)
        total_up_packets = sum(client.get("up_packets", 0) for client in stats)
        
        return {
            "enabled": client_usage.get("enabled", False),
            "total_clients": len(stats),
            "total_traffic": {
                "down_bytes": total_down_bytes,
                "up_bytes": total_up_bytes,
                "down_packets": total_down_packets,
                "up_packets": total_up_packets,
                "total_bytes": total_down_bytes + total_up_bytes,
                "total_packets": total_down_packets + total_up_packets
            },
            "stats": stats
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving client usage: {e}")
        return None



def get_vpn_status() -> Optional[Dict[str, Any]]:
    """Return VPN status (OpenVPN, L2TP, etc.).
    
    Returns:
        dict or None: Dictionary containing VPN status information including:
            - openvpn (dict): OpenVPN status and configuration
            - l2tp (dict): L2TP status and configuration
            - gre (dict): GRE tunnel status
            - vxlan (dict): VXLAN tunnel status
    """
    try:
        vpn_status = {
            'openvpn': get_openvpn_status(),
            'l2tp': _cs_client.get('status/l2tp'),
            'gre': _cs_client.get('status/gre'),
            'vxlan': _cs_client.get('status/vxlan')
        }
        return vpn_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving VPN status: {e}")
        return None

def get_security_status() -> Optional[Dict[str, Any]]:
    """Return security-related status.
    
    Returns:
        dict or None: Dictionary containing security status information including:
            - firewall (dict): Firewall status and configuration
            - security (dict): General security settings and status
            - certificates (dict): Certificate management status
    """
    try:
        security_status = {
            'firewall': get_firewall_status(),
            'security': _cs_client.get('status/security'),
            'certificates': get_certificate_status()
        }
        return security_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving security status: {e}")
        return None

def get_iot_status() -> Optional[Dict[str, Any]]:
    """Return IoT-related status.
    
    Returns:
        dict or None: Dictionary containing IoT status information including:
            - IoT device information
            - IoT protocol status
            - IoT configuration
    """
    try:
        iot_status = _cs_client.get('status/iot')
        return iot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving IoT status: {e}")
        return None



def get_hotspot_status() -> Optional[Dict[str, Any]]:
    """Return hotspot status.
    
    Returns:
        dict or None: Dictionary containing hotspot status information including:
            - connected clients
            - active sessions
            - allowed domains and hosts
            - rate limiting status
    """
    try:
        hotspot_status = _cs_client.get('status/hotspot')
        return hotspot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving hotspot status: {e}")
        return None

def get_sdwan_status() -> Optional[Dict[str, Any]]:
    """Return SD-WAN status with advanced features and monitoring information.
    
    Returns:
        dict or None: Dictionary containing SD-WAN status information including:
            - forward_error_correction (dict): FEC statistics and configuration
            - link_monitoring (dict): Link monitoring status and configuration
            - quality_of_experience (dict): QoE metrics and monitoring
            - user_mode_driver (dict): UMD status and configuration including:
                - status (str): UMD operational status (enabled/disabled)
            - wan_bonding (dict): WAN bonding configuration and status
    """
    try:
        sdwan_status = _cs_client.get('status/sdwan_adv')
        if not sdwan_status:
            return {}
        
        return {
            "forward_error_correction": sdwan_status.get("forward_error_correction", {}),
            "link_monitoring": sdwan_status.get("link_mon", {}),
            "quality_of_experience": sdwan_status.get("qoe", {}),
            "user_mode_driver": sdwan_status.get("user_mode_driver", {}),
            "wan_bonding": sdwan_status.get("wan_bonding", {})
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving SD-WAN status: {e}")
        return None

# ============================================================================
# WAN PROFILE MANAGEMENT FUNCTIONS
# ============================================================================

def get_wan_profiles() -> Dict[str, Any]:
    """Get all WAN profile rules and their configurations.
    
    Returns:
        dict: Dictionary containing WAN profile information including:
            - profiles (list): List of WAN profile rules with:
                - _id_ (str): Unique identifier for the profile
                - priority (float): Priority value (lower = higher priority)
                - trigger_name (str): Human-readable profile name
                - trigger_string (str): Matching string for device detection
                - disabled (bool): Whether profile is disabled
                - def_conn_state (str): Default connection state
                - bandwidth_ingress (int): Download bandwidth in kbps
                - bandwidth_egress (int): Upload bandwidth in kbps
    """
    try:
        wan_rules = _cs_client.get('config/wan/rules2')
        if not wan_rules:
            return {"profiles": []}
        
        profiles = []
        for rule in wan_rules:
            profile_info = {
                "_id_": rule.get("_id_"),
                "priority": rule.get("priority", 999),
                "trigger_name": rule.get("trigger_name", ""),
                "trigger_string": rule.get("trigger_string", ""),
                "disabled": rule.get("disabled", False),
                "def_conn_state": rule.get("def_conn_state", "auto"),
                "bandwidth_ingress": rule.get("bandwidth_ingress", 1300),
                "bandwidth_egress": rule.get("bandwidth_egress", 1300)
            }
            profiles.append(profile_info)
        
        # Sort by priority (lower values first)
        profiles.sort(key=lambda x: x["priority"])
        
        return {
            "profiles": profiles,
            "total_profiles": len(profiles),
            "enabled_profiles": len([p for p in profiles if not p["disabled"]]),
            "disabled_profiles": len([p for p in profiles if p["disabled"]])
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WAN profiles: {e}")
        return {"error": str(e)}

def get_wan_device_profile(device_id: str) -> Optional[Dict[str, Any]]:
    """Get the WAN profile configuration currently applied to a specific device.
    
    Args:
        device_id (str): WAN device identifier (e.g., "mdm-123456", "ethernet-1")
        
    Returns:
        dict or None: Device profile information including:
            - device_id (str): Device identifier
            - profile_id (str): ID of the matched profile
            - profile_name (str): Name of the matched profile
            - priority (float): Profile priority
            - disabled (bool): Whether profile is disabled
            - def_conn_state (str): Default connection state
            - bandwidth (dict): Bandwidth configuration
    """
    try:
        # Get device info to find the config_id
        device_info = _cs_client.get(f'status/wan/devices/{device_id}/info')
        if not device_info:
            return None
        
        profile_id = device_info.get("config_id")
        if not profile_id:
            return None
        
        # Get the profile details
        profile = _cs_client.get(f'config/wan/rules2/{profile_id}')
        if not profile:
            return None
        
        return {
            "device_id": device_id,
            "profile_id": profile_id,
            "profile_name": profile.get("trigger_name", ""),
            "priority": profile.get("priority", 999),
            "disabled": profile.get("disabled", False),
            "def_conn_state": profile.get("def_conn_state", "auto"),
            "bandwidth": {
                "ingress": profile.get("bandwidth_ingress", 1300),
                "egress": profile.get("bandwidth_egress", 1300)
            }
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving device profile for {device_id}: {e}")
        return None

def set_wan_device_priority(device_id: str, new_priority: float) -> bool:
    """Set a WAN device to a specific priority by adjusting its profile priority.
    
    Args:
        device_id (str): WAN device identifier
        new_priority (float): New priority value (lower = higher priority)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get current device profile
        device_profile = get_wan_device_profile(device_id)
        if not device_profile:
            return False
        
        profile_id = device_profile["profile_id"]
        
        # Update the profile priority
        result = _cs_client.put(f'config/wan/rules2/{profile_id}/priority', new_priority)
        return result is not None
    except Exception as e:
        _cs_client.logger.exception(f"Error setting device priority for {device_id}: {e}")
        return False

def make_wan_device_highest_priority(device_id: str) -> bool:
    """Make a WAN device the highest priority by setting its profile to the lowest priority value.
    
    Args:
        device_id (str): WAN device identifier
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get all profiles to find the lowest priority
        profiles = get_wan_profiles()
        if "error" in profiles:
            return False
        
        if not profiles["profiles"]:
            return False
        
        # Find the lowest priority value
        lowest_priority = min(p["priority"] for p in profiles["profiles"])
        
        # Set the device to an even lower priority (higher priority)
        new_priority = lowest_priority - 1.0
        
        return set_wan_device_priority(device_id, new_priority)
    except Exception as e:
        _cs_client.logger.exception(f"Error making device highest priority for {device_id}: {e}")
        return False

def enable_wan_device(device_id: str) -> bool:
    """Enable a WAN device by setting its profile to enabled.
    
    Args:
        device_id (str): WAN device identifier
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        device_profile = get_wan_device_profile(device_id)
        if not device_profile:
            return False
        
        profile_id = device_profile["profile_id"]
        
        # Set disabled to false
        result = _cs_client.put(f'config/wan/rules2/{profile_id}/disabled', False)
        return result is not None
    except Exception as e:
        _cs_client.logger.exception(f"Error enabling device {device_id}: {e}")
        return False

def disable_wan_device(device_id: str) -> bool:
    """Disable a WAN device by setting its profile to disabled.
    
    Args:
        device_id (str): WAN device identifier
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        device_profile = get_wan_device_profile(device_id)
        if not device_profile:
            return False
        
        profile_id = device_profile["profile_id"]
        
        # Set disabled to true
        result = _cs_client.put(f'config/wan/rules2/{profile_id}/disabled', True)
        return result is not None
    except Exception as e:
        _cs_client.logger.exception(f"Error disabling device {device_id}: {e}")
        return False

def set_wan_device_default_connection_state(device_id: str, connection_state: str) -> bool:
    """Set the default connection state for a WAN device.
    
    Args:
        device_id (str): WAN device identifier
        connection_state (str): Connection state ("alwayson", "auto", "ondemand", "disabled")
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        device_profile = get_wan_device_profile(device_id)
        if not device_profile:
            return False
        
        profile_id = device_profile["profile_id"]
        
        # Update the def_conn_state
        result = _cs_client.put(f'config/wan/rules2/{profile_id}/def_conn_state', connection_state)
        return result is not None
    except Exception as e:
        _cs_client.logger.exception(f"Error setting connection state for {device_id}: {e}")
        return False

def set_wan_device_bandwidth(device_id: str, ingress_kbps: int = None, egress_kbps: int = None) -> bool:
    """Set bandwidth limits for a WAN device.
    
    Args:
        device_id (str): WAN device identifier
        ingress_kbps (int): Download bandwidth in kbps (optional)
        egress_kbps (int): Upload bandwidth in kbps (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        device_profile = get_wan_device_profile(device_id)
        if not device_profile:
            return False
        
        profile_id = device_profile["profile_id"]
        
        success = True
        
        # Update ingress bandwidth if specified
        if ingress_kbps is not None:
            result = _cs_client.put(f'config/wan/rules2/{profile_id}/bandwidth_ingress', ingress_kbps)
            if not result:
                success = False
        
        # Update egress bandwidth if specified
        if egress_kbps is not None:
            result = _cs_client.put(f'config/wan/rules2/{profile_id}/bandwidth_egress', egress_kbps)
            if not result:
                success = False
        
        return success
    except Exception as e:
        _cs_client.logger.exception(f"Error setting bandwidth for {device_id}: {e}")
        return False

def set_manual_apn(device_or_id: str, new_apn: str) -> Optional[Dict[str, Any]]:
    """Set manual APN for a modem device or WAN rule.
    
    Args:
        device_or_id (str): Either a modem device name (starts with 'mdm') or a WAN rule _id_
        new_apn (str): The new APN to set
        
    Returns:
        dict: Result with operation details including:
            - device_id (str): The device identifier used
            - rule_id (str): The WAN rule _id_ that was modified
            - new_apn (str): The APN that was set
            - success (bool): Whether the operation was successful
    """
    try:
        return _cs_client.set_manual_apn(device_or_id, new_apn)
    except Exception as e:
        _cs_client.logger.exception(f"Error setting manual APN for {device_or_id}: {e}")
        return {
            'device_id': device_or_id if device_or_id.startswith('mdm') else None,
            'error': str(e),
            'success': False
        }

def remove_manual_apn(device_or_id: str) -> Optional[Dict[str, Any]]:
    """Remove manual APN configuration for a modem device or WAN rule.
    
    Args:
        device_or_id (str): Either a modem device name (starts with 'mdm') or a WAN rule _id_
        
    Returns:
        dict: Result with operation details including:
            - device_id (str): The device identifier used
            - rule_id (str): The WAN rule _id_ that was modified
            - success (bool): Whether the operation was successful
    """
    try:
        return _cs_client.remove_manual_apn(device_or_id)
    except Exception as e:
        _cs_client.logger.exception(f"Error removing manual APN for {device_or_id}: {e}")
        return {
            'device_id': device_or_id if device_or_id.startswith('mdm') else None,
            'error': str(e),
            'success': False
        }

def add_advanced_apn(carrier: str, apn: str) -> Optional[Dict[str, Any]]:
    """Add an advanced APN configuration to the custom APNs list.
    
    Args:
        carrier (str): Carrier name or PLMN identifier
        apn (str): APN name to configure
        
    Returns:
        dict: Result with operation details including:
            - carrier (str): The carrier that was added
            - apn (str): The APN that was added
            - success (bool): Whether the operation was successful
    """
    try:
        return _cs_client.add_advanced_apn(carrier, apn)
    except Exception as e:
        _cs_client.logger.exception(f"Error adding advanced APN for carrier {carrier} and APN {apn}: {e}")
        return {
            'carrier': carrier,
            'apn': apn,
            'error': str(e),
            'success': False
        }

def delete_advanced_apn(carrier_or_apn: str) -> Optional[Dict[str, Any]]:
    """Delete an advanced APN configuration from the custom APNs list.
    
    Args:
        carrier_or_apn (str): Carrier name, PLMN identifier, or APN name to match and delete
        
    Returns:
        dict: Result with operation details including:
            - matched_entries (list): List of entries that were matched and deleted
            - success (bool): Whether the operation was successful
            - deleted_count (int): Number of entries deleted
    """
    try:
        return _cs_client.delete_advanced_apn(carrier_or_apn)
    except Exception as e:
        _cs_client.logger.exception(f"Error deleting advanced APN matching {carrier_or_apn}: {e}")
        return {
            'matched_entries': [],
            'deleted_count': 0,
            'error': str(e),
            'success': False
        }

def reorder_wan_profiles(device_priorities: Dict[str, float]) -> bool:
    """Reorder WAN profiles based on desired device priorities.
    
    Args:
        device_priorities (dict): Dictionary mapping device IDs to desired priority values
                                 Lower values = higher priority
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        success = True
        
        for device_id, priority in device_priorities.items():
            result = set_wan_device_priority(device_id, priority)
            if not result:
                success = False
                _cs_client.logger.error(f"Failed to set priority for device {device_id}")
        
        return success
    except Exception as e:
        _cs_client.logger.exception(f"Error reordering WAN profiles: {e}")
        return False

def get_wan_profile_by_trigger_string(trigger_string: str) -> Optional[Dict[str, Any]]:
    """Find a WAN profile by its trigger string.
    
    Args:
        trigger_string (str): Trigger string to search for
        
    Returns:
        dict or None: Profile information if found
    """
    try:
        profiles = get_wan_profiles()
        if "error" in profiles:
            return None
        
        for profile in profiles["profiles"]:
            if profile["trigger_string"] == trigger_string:
                return profile
        
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error finding profile by trigger string: {e}")
        return None

def get_wan_profile_by_name(profile_name: str) -> Optional[Dict[str, Any]]:
    """Find a WAN profile by its trigger name.
    
    Args:
        profile_name (str): Profile name to search for
        
    Returns:
        dict or None: Profile information if found
    """
    try:
        profiles = get_wan_profiles()
        if "error" in profiles:
            return None
        
        for profile in profiles["profiles"]:
            if profile["trigger_name"] == profile_name:
                return profile
        
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error finding profile by name: {e}")
        return None

def get_wan_device_summary() -> Dict[str, Any]:
    """Get a summary of all WAN devices and their profile configurations.
    
    Returns:
        dict: Summary of WAN devices including:
            - devices (list): List of device information
            - profiles (list): List of profile information
            - priority_order (list): Devices ordered by priority (highest first)
            - enabled_devices (int): Count of enabled devices
            - disabled_devices (int): Count of disabled devices
    """
    try:
        # Get WAN devices
        wan_devices = _cs_client.get('status/wan/devices')
        if not wan_devices:
            return {"devices": [], "profiles": [], "priority_order": [], "enabled_devices": 0, "disabled_devices": 0}
        
        # Get all profiles
        profiles = get_wan_profiles()
        if "error" in profiles:
            return {"error": "Failed to retrieve profiles"}
        
        devices_info = []
        priority_order = []
        
        for device_id, device_data in wan_devices.items():
            device_profile = get_wan_device_profile(device_id)
            if device_profile:
                device_info = {
                    "device_id": device_id,
                    "device_type": device_data.get("type", "unknown"),
                    "connection_state": device_data.get("status", {}).get("connection_state", "unknown"),
                    "profile_id": device_profile["profile_id"],
                    "profile_name": device_profile["profile_name"],
                    "priority": device_profile["priority"],
                    "disabled": device_profile["disabled"],
                    "def_conn_state": device_profile["def_conn_state"],
                    "bandwidth": device_profile["bandwidth"]
                }
                devices_info.append(device_info)
                priority_order.append(device_info)
        
        # Sort by priority (lowest value first = highest priority)
        priority_order.sort(key=lambda x: x["priority"])
        
        enabled_count = len([d for d in devices_info if not d["disabled"]])
        disabled_count = len([d for d in devices_info if d["disabled"]])
        
        return {
            "devices": devices_info,
            "profiles": profiles["profiles"],
            "priority_order": priority_order,
            "enabled_devices": enabled_count,
            "disabled_devices": disabled_count,
            "total_devices": len(devices_info)
        }
    except Exception as e:
        _cs_client.logger.exception(f"Error getting WAN device summary: {e}")
        return {"error": str(e)}


def get_wan_primary_device() -> Optional[str]:
    """Get the WAN primary device identifier.
    
    Returns:
        str: Primary WAN device identifier, or None if not available
    """
    try:
        return _cs_client.get_wan_primary_device()
    except Exception as e:
        print(f"Error retrieving WAN primary device: {e}")
        return None


def get_wan_connection_state() -> Optional[Dict[str, Any]]:
    """Get WAN connection state status.
    
    Returns:
        dict or None: Dictionary containing WAN connection state information including:
            - connection_state (str): Overall WAN connection state
            - timestamp (str): Timestamp when the state was retrieved
    """
    try:
        return _cs_client.get_wan_connection_state()
    except Exception as e:
        print(f"Error retrieving WAN connection state: {e}")
        return None


# ============================================================================
# COMPREHENSIVE STATUS FUNCTION
# ============================================================================

def get_comprehensive_status(include_detailed: bool = True, include_clients: bool = True) -> Optional[Dict[str, Any]]:
    """Return a comprehensive status report of the router.
    
    Args:
        include_detailed (bool): Whether to include detailed information. Defaults to True.
        include_clients (bool): Whether to include client information. Defaults to True.
    
    Returns:
        dict or None: Comprehensive status report containing:
            - system (dict): System status and information
            - network (dict): Network status and configuration
            - modem (dict): Modem status and signal information
            - gps (dict): GPS status and location information
            - power (dict): Power usage information
            - storage (dict): Storage status
            - usb (dict): USB device status
            - poe (dict): PoE status
            - certificates (dict): Certificate status
            - openvpn (dict): OpenVPN status
            - firewall (dict): Firewall status
            - qos (dict): QoS status
            - dhcp (dict): DHCP status
            - ncm (dict): NCM status
            - clients (dict): Client information if include_clients is True
            - detailed (dict): Detailed information if include_detailed is True
    """
    try:
        status_report = {
            'system': {
                'uptime': get_uptime(),
                'cpu': _cs_client.get('status/system/cpu'),
                'memory': _cs_client.get('status/system/memory'),
                'temperature': get_temperature(),
                'firmware': get_device_firmware(),
                'product_info': _cs_client.get('status/product_info')
            },
            'network': {
                'wan': _cs_client.get('status/wan'),
                'lan': _cs_client.get('status/lan'),
                'wlan': get_wlan_status(),
                'routing': get_routing_table(),
                'dns': get_dns_status()
            },
            'modem': {
                'status': get_modem_status(),
                'signal_strength': get_signal_strength(),
                'sims': get_sims()
            },
            'gps': get_gps_status(),
            'power': get_power_usage(),
            'storage': get_storage_status(),
            'usb': get_usb_status(),
            'poe': get_poe_status(),
            'certificates': get_certificate_status(),
            'openvpn': get_openvpn_status(),
            'firewall': get_firewall_status(),
            'qos': get_qos_status(),
            'dhcp': get_dhcp_leases(),
            'ncm': get_ncm_status()
        }
        
        if include_clients:
            status_report['clients'] = get_ipv4_lan_clients()
        
        if include_detailed:
            # Add more detailed information
            status_report['detailed'] = {

                'flow_statistics': get_flow_statistics(),
                'client_usage': get_client_usage(),
                'vpn': get_vpn_status(),
                'security': get_security_status(),
                'iot': get_iot_status(),
                'sdwan': get_sdwan_status()
            }
        return status_report
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving comprehensive status: {e}")
        return None

def wait_for_modem_connection(timeout: int = 300, check_interval: float = 1.0) -> bool:
    """Wait for modem to establish a connection.
    
    Args:
        timeout (int): Maximum time to wait in seconds. Defaults to 300.
        check_interval (float): Time between checks in seconds. Defaults to 1.0.
    
    Returns:
        bool: True if modem connection is established within timeout, False otherwise.
    """
    try:
        _cs_client.log("Waiting for modem connection...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            modem_status = get_modem_status()
            if modem_status:
                for device_id, device_data in modem_status.items():
                    if device_id.startswith('mdm-'):
                        status = device_data.get('status', {})
                        if status.get('connection_state') == 'connected':
                            _cs_client.log("Modem is connected.")
                            return True
            time.sleep(check_interval)
        _cs_client.log(f"Timeout waiting for modem connection after {timeout} seconds.")
        return False
    except Exception as e:
        _cs_client.log(f"Error waiting for modem connection: {e}")
        return False

def wait_for_gps_fix(timeout: int = 300, check_interval: float = 1.0) -> bool:
    """Wait for GPS to acquire a fix.
    
    Args:
        timeout (int): Maximum time to wait in seconds. Defaults to 300.
        check_interval (float): Time between checks in seconds. Defaults to 1.0.
    
    Returns:
        bool: True if GPS fix is acquired within timeout, False otherwise.
    """
    try:
        _cs_client.log("Waiting for GPS fix...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            gps_status = get_gps_status()
            if gps_status and gps_status.get('gps_lock'):
                _cs_client.log("GPS fix acquired.")
                return True
            time.sleep(check_interval)
        _cs_client.log(f"Timeout waiting for GPS fix after {timeout} seconds.")
        return False
    except Exception as e:
        _cs_client.log(f"Error waiting for GPS fix: {e}")
        return False

# ============================================================================
# CONTROL FUNCTIONS
# ============================================================================

def reset_modem(modem_id: Optional[str] = None, force: bool = False) -> bool:
    """Reset a specific modem or all modems.
    
    Args:
        modem_id (str, optional): Specific modem ID to reset. If None, resets all modems.
                                  Defaults to None.
        force (bool, optional): Force reset even if modem is connected. Defaults to False.
    
    Returns:
        bool: True if reset command was sent successfully, False otherwise.
    """
    try:
        if modem_id:
            _cs_client.put(f'control/modem/{modem_id}/reset', 'reset')
            _cs_client.log(f"Reset command sent to modem {modem_id}")
        else:
            _cs_client.put('control/modem/reset', 'reset')
            _cs_client.log("Reset command sent to all modems")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error resetting modem: {e}")
        return False

def reset_wlan(force: bool = False) -> bool:
    """Reset wireless LAN configuration and connections.
    
    Args:
        force (bool): Force reset even if WLAN is active. Defaults to False.
    
    Returns:
        bool: True if reset command was sent successfully, False otherwise.
    """
    try:
        _cs_client.put('control/wlan/reset', 'reset')
        _cs_client.log("Reset command sent to WLAN")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error resetting WLAN: {e}")
        return False

def clear_logs() -> bool:
    """Clear system logs.
    
    Returns:
        bool: True if logs were cleared successfully, False otherwise.
    """
    try:
        _cs_client.put('control/log/clear', 'clear')
        _cs_client.log("Logs cleared")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error clearing logs: {e}")
        return False

def factory_reset() -> bool:
    """Perform factory reset of the router.
    
    WARNING: This will erase all configuration and return the router to factory defaults.
    Use with extreme caution.
    
    Returns:
        bool: True if factory reset was initiated successfully, False otherwise.
    """
    try:
        _cs_client.put('control/system/factory_reset', 'factory_reset')
        _cs_client.log("Factory reset initiated")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error performing factory reset: {e}")
        return False

def restart_service(service_name: str, force: bool = False) -> bool:
    """Restart a specific system service.
    
    Args:
        service_name (str): Name of the service to restart.
        force (bool, optional): Force restart even if service is critical. Defaults to False.
    
    Returns:
        bool: True if service restart was initiated successfully, False otherwise.
    """
    try:
        _cs_client.put(f'control/system/services/{service_name}/restart', 'restart')
        _cs_client.log(f"Service {service_name} restart initiated")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error restarting service {service_name}: {e}")
        return False

def set_log_level(level: str = 'info') -> bool:
    """Set system logging level.
    
    Args:
        level (str): Log level ('debug', 'info', 'warning', 'error'). Defaults to 'info'.
    
    Returns:
        bool: True if log level was set successfully, False otherwise.
    """
    try:
        _cs_client.put('config/system/logging/level', level)
        _cs_client.log(f"Log level set to {level}")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error setting log level: {e}")
        return False

# ============================================================================
# GRANULAR HELPER FUNCTIONS - QoS
# ============================================================================

def get_qos_queues() -> List[Dict[str, Any]]:
    """Return detailed QoS queue information.
    
    Returns:
        list: List of QoS queues with detailed statistics including:
            - queue name and configuration
            - packet counts and statistics
            - bandwidth usage
            - queue status
    """
    try:
        qos_data = _cs_client.get('status/qos')
        return qos_data.get('queues', []) if qos_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS queues: {e}")
        return []

def get_qos_queue_by_name(queue_name: str = '') -> Optional[Dict[str, Any]]:
    """Return QoS queue information for a specific queue by name.
    
    Args:
        queue_name (str): Name of the QoS queue to retrieve. Defaults to empty string.
    
    Returns:
        dict or None: QoS queue information for the specified queue, or None if not found.
    """

    try:
        qos_data = _cs_client.get('status/qos')
        if qos_data and 'queues' in qos_data:
            for queue in qos_data['queues']:
                if queue.get('name') == queue_name:
                    return queue
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS queue {queue_name}: {e}")
        return None

def get_qos_traffic_stats() -> Dict[str, Any]:
    """Return aggregated QoS traffic statistics.
    
    Returns:
        dict: Aggregated traffic statistics across all queues including:
            - total_ibytes (int): Total incoming bytes
            - total_obytes (int): Total outgoing bytes
            - total_ipkts (int): Total incoming packets
            - total_opkts (int): Total outgoing packets
            - total_idrop_pkts (int): Total incoming dropped packets
            - total_odrop_pkts (int): Total outgoing dropped packets
            - queue_count (int): Number of queues
    """
    try:
        qos_data = _cs_client.get('status/qos')
        if not qos_data or 'queues' not in qos_data:
            return {}
        
        total_stats = {
            'total_ibytes': 0,
            'total_obytes': 0,
            'total_ipkts': 0,
            'total_opkts': 0,
            'total_idrop_pkts': 0,
            'total_odrop_pkts': 0,
            'queue_count': len(qos_data['queues'])
        }
        
        for queue in qos_data['queues']:
            total_stats['total_ibytes'] += queue.get('ibytes', 0)
            total_stats['total_obytes'] += queue.get('obytes', 0)
            total_stats['total_ipkts'] += queue.get('ipkts', 0)
            total_stats['total_opkts'] += queue.get('opkts', 0)
            total_stats['total_idrop_pkts'] += queue.get('idrop_pkts', 0)
            total_stats['total_odrop_pkts'] += queue.get('odrop_pkts', 0)
        
        return total_stats
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS traffic stats: {e}")
        return {}


# ============================================================================
# GRANULAR HELPER FUNCTIONS - DHCP
# ============================================================================

def get_dhcp_clients_by_interface(interface_name: str = '') -> List[Dict[str, Any]]:
    """Return DHCP leases for a specific interface.
    
    Args:
        interface_name (str): Interface name to filter by. Defaults to empty string.
        
    Returns:
        list: DHCP leases for the specified interface.
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        if leases:
            return [lease for lease in leases if lease.get('iface') == interface_name]
        return []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP clients for interface {interface_name}: {e}")
        return []

def get_dhcp_clients_by_network(network_name: str = '') -> List[Dict[str, Any]]:
    """Return DHCP leases for a specific network.
    
    Args:
        network_name (str): Network name to filter by. Defaults to empty string.
        
    Returns:
        list: DHCP leases for the specified network.
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        if leases:
            return [lease for lease in leases if lease.get('network') == network_name]
        return []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP clients for network {network_name}: {e}")
        return []

def get_dhcp_client_by_mac(mac_address: str = '') -> Optional[Dict[str, Any]]:
    """Return DHCP lease for a specific MAC address.
    
    Args:
        mac_address (str): MAC address to search for. Defaults to empty string.
        
    Returns:
        dict or None: DHCP lease information or None if not found.
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        if leases:
            for lease in leases:
                if lease.get('mac') == mac_address:
                    return lease
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP client for MAC {mac_address}: {e}")
        return None

def get_dhcp_client_by_ip(ip_address: str = '') -> Optional[Dict[str, Any]]:
    """Return DHCP lease for a specific IP address.
    
    Args:
        ip_address (str): IP address to search for. Defaults to empty string.
        
    Returns:
        dict or None: DHCP lease information or None if not found.
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        if leases:
            for lease in leases:
                if lease.get('ip_address') == ip_address:
                    return lease
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP client for IP {ip_address}: {e}")
        return None

def get_dhcp_interface_summary() -> Dict[str, Any]:
    """Return summary of DHCP leases by interface.
    
    Returns:
        dict: Summary of DHCP leases organized by interface including:
            - count (int): Number of leases on the interface
            - networks (list): List of networks on the interface
            - interface_type (str): Type of interface
    """
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        if not leases:
            return {}
        
        summary = {}
        for lease in leases:
            iface = lease.get('iface', 'unknown')
            if iface not in summary:
                summary[iface] = {
                    'count': 0,
                    'networks': set(),
                    'interface_type': lease.get('iface_type', 'unknown')
                }
            summary[iface]['count'] += 1
            summary[iface]['networks'].add(lease.get('network', 'unknown'))
        
        # Convert sets to lists for JSON serialization
        for iface in summary:
            summary[iface]['networks'] = list(summary[iface]['networks'])
        
        return summary
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP interface summary: {e}")
        return {}


# ============================================================================
# GRANULAR HELPER FUNCTIONS - ROUTING
# ============================================================================

def get_bgp_status() -> Dict[str, Any]:
    """Return BGP routing protocol status and neighbor information.
    
    Returns:
        dict: BGP status containing:
            - show_ip_bgp (str): BGP route table
            - show_ip_bgp_ipv6 (str): IPv6 BGP route table
            - show_ip_bgp_neighbor (str): BGP neighbor status
            - show_ip_bgp_summary (str): BGP summary information
    """
    try:
        routing_data = _cs_client.get('status/routing')
        return routing_data.get('bgp', {}) if routing_data else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving BGP status: {e}")
        return {}

def get_ospf_status() -> Dict[str, Any]:
    """Return OSPF routing protocol status and neighbor information.
    
    Returns:
        dict: OSPF status containing:
            - show_ip_ospf_database (str): OSPF link state database
            - show_ip_ospf_interface (str): OSPF interface status
            - show_ip_ospf_neighbor (str): OSPF neighbor status
            - show_ip_ospf_neighbor_detail (str): Detailed OSPF neighbor info
            - show_ip_ospf_route (str): OSPF route table
    """
    try:
        routing_data = _cs_client.get('status/routing')
        return routing_data.get('ospf', {}) if routing_data else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving OSPF status: {e}")
        return {}

def get_static_routes() -> List[Dict[str, Any]]:
    """Return configured static routes.
    
    Returns:
        list: List of static routes with:
            - dev (str): Device/interface name
            - gateway (str): Gateway IP address
            - ip_address (str): Destination IP address
            - metric (int): Route metric
            - netmask (str): Subnet mask
            - proto (str): Protocol (static)
    """
    try:
        routing_data = _cs_client.get('status/routing')
        return routing_data.get('static', []) if routing_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving static routes: {e}")
        return []

def get_routing_policies() -> List[Dict[str, Any]]:
    """Return routing policy configuration.
    
    Returns:
        list: List of routing policies with:
            - action (str): Policy action
            - priority (int): Policy priority
            - src (str): Source address
            - dst (str): Destination address
            - mark (int): Traffic mark
            - mask (int): Mark mask
            - table (str): Routing table
    """
    try:
        routing_data = _cs_client.get('status/routing')
        return routing_data.get('policy', []) if routing_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving routing policies: {e}")
        return []

def get_routing_table_by_name(table_name: str) -> List[Dict[str, Any]]:
    """Return routes from a specific routing table.
    
    Args:
        table_name (str): Name of the routing table.
        
    Returns:
        list: Routes in the specified table.
    """
    try:
        routing_data = _cs_client.get('status/routing')
        if routing_data and 'table' in routing_data:
            return routing_data['table'].get(table_name, [])
        return []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving routing table {table_name}: {e}")
        return []

def get_arp_table() -> str:
    """Return ARP table information.
    
    Returns:
        str: ARP table dump showing MAC to IP mappings.
    """
    try:
        routing_data = _cs_client.get('status/routing')
        if routing_data and 'cli' in routing_data:
            return routing_data['cli'].get('arpdump', '')
        return ''
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving ARP table: {e}")
        return ''

def get_route_summary() -> Dict[str, Any]:
    """Return summary of routing information.
    
    Returns:
        dict: Summary of routing information including:
            - total_static_routes (int): Number of static routes
            - total_policies (int): Number of routing policies
            - routing_tables (list): List of available routing tables
            - bgp_neighbors (int): Number of BGP neighbors
            - ospf_neighbors (int): Number of OSPF neighbors
    """
    try:
        routing_data = _cs_client.get('status/routing')
        if not routing_data:
            return {}
        
        summary = {
            'total_static_routes': len(routing_data.get('static', [])),
            'total_policies': len(routing_data.get('policy', [])),
            'routing_tables': list(routing_data.get('table', {}).keys()),
            'bgp_neighbors': 0,
            'ospf_neighbors': 0
        }
        
        # Count BGP neighbors from the summary output
        bgp_summary = routing_data.get('bgp', {}).get('show_ip_bgp_summary', '')
        if 'Total number of neighbors' in bgp_summary:
            try:
                summary['bgp_neighbors'] = int(bgp_summary.split('Total number of neighbors')[-1].split('\n')[0].strip())
            except:
                pass
        
        # Count OSPF neighbors from the neighbor output
        ospf_neighbors = routing_data.get('ospf', {}).get('show_ip_ospf_neighbor', '')
        if ospf_neighbors:
            summary['ospf_neighbors'] = len([line for line in ospf_neighbors.split('\n') if line.strip() and not line.startswith('Neighbor ID')])
        
        return summary
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving route summary: {e}")
        return {}


# ============================================================================
# GRANULAR HELPER FUNCTIONS - CERTIFICATES
# ============================================================================

def get_certificates() -> List[Dict[str, Any]]:
    """Return list of installed certificates.
    
    Returns:
        list: List of certificates with:
            - CN (str): Common Name
            - name (str): Certificate name
            - not_before (str): Valid from date
            - not_after (str): Valid until date
            - has_key (bool): Whether private key is present
            - uuid (str): Certificate UUID
    """
    try:
        cert_data = _cs_client.get('status/certmgmt')
        return cert_data.get('view', []) if cert_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificates: {e}")
        return []

def get_certificate_by_name(cert_name: str) -> Optional[Dict[str, Any]]:
    """Return specific certificate information by name.
    
    Args:
        cert_name (str): Name of the certificate to retrieve.
        
    Returns:
        dict or None: Certificate information or None if not found.
    """
    try:
        cert_data = _cs_client.get('status/certmgmt')
        if cert_data and 'view' in cert_data:
            for cert in cert_data['view']:
                if cert.get('name') == cert_name:
                    return cert
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate {cert_name}: {e}")
        return None

def get_certificate_by_uuid(cert_uuid: str) -> Optional[Dict[str, Any]]:
    """Return specific certificate information by UUID.
    
    Args:
        cert_uuid (str): UUID of the certificate to retrieve.
        
    Returns:
        dict or None: Certificate information or None if not found.
    """
    try:
        cert_data = _cs_client.get('status/certmgmt')
        if cert_data and 'view' in cert_data:
            for cert in cert_data['view']:
                if cert.get('uuid') == cert_uuid:
                    return cert
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate with UUID {cert_uuid}: {e}")
        return None

def get_expiring_certificates(days_threshold: int = 30) -> List[Dict[str, Any]]:
    """Return certificates that are expiring within the specified number of days.
    
    Args:
        days_threshold (int): Number of days to check for expiration. Defaults to 30.
        
    Returns:
        list: List of certificates expiring within the threshold period.
    """

    try:
        cert_data = _cs_client.get('status/certmgmt')
        if not cert_data or 'view' not in cert_data:
            return []
        
        expiring_certs = []
        threshold_date = datetime.now() + timedelta(days=days_threshold)
        
        for cert in cert_data['view']:
            not_after_str = cert.get('not_after', '')
            if not_after_str:
                try:
                    # Parse date format like "7-1-2026"
                    exp_date = datetime.strptime(not_after_str, '%m-%d-%Y')
                    if exp_date <= threshold_date:
                        expiring_certs.append(cert)
                except ValueError:
                    # Skip certificates with unparseable dates
                    continue
        
        return expiring_certs
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving expiring certificates: {e}")
        return []

def get_certificate_summary() -> Dict[str, Any]:
    """Return summary of certificate information.
    
    Returns:
        dict: Summary of certificate information including:
            - total_certificates (int): Total number of certificates
            - certificates_with_keys (int): Number of certificates with private keys
            - ca_fingerprints (int): Number of CA fingerprints
            - expiring_soon (int): Number of certificates expiring in 30 days
    """
    try:
        cert_data = _cs_client.get('status/certmgmt')
        if not cert_data:
            return {}
        
        summary = {
            'total_certificates': len(cert_data.get('view', [])),
            'certificates_with_keys': 0,
            'ca_fingerprints': len(cert_data.get('ca_fingerprints', [])),
            'expiring_soon': 0
        }
        
        # Count certificates with keys
        for cert in cert_data.get('view', []):
            if cert.get('has_key', False):
                summary['certificates_with_keys'] += 1
        
        # Count expiring certificates
        expiring_certs = get_expiring_certificates(30)
        summary['expiring_soon'] = len(expiring_certs)
        
        return summary
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate summary: {e}")
        return {}


# ============================================================================
# GRANULAR HELPER FUNCTIONS - FIREWALL
# ============================================================================

def get_firewall_connections() -> List[Dict[str, Any]]:
    """Return active firewall connections and connection tracking information.
    
    Returns:
        list: List of active connections with:
            - id (int): Connection ID
            - orig_src (str): Original source IP
            - orig_dst (str): Original destination IP
            - orig_src_port (int): Original source port
            - orig_dst_port (int): Original destination port
            - proto (int): Protocol number
            - status (str): Connection status
            - tcp_state (str): TCP state (if applicable)
            - timeout (int): Connection timeout
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        return firewall_data.get('connections', []) if firewall_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall connections: {e}")
        return []

def get_firewall_hitcounters() -> List[Dict[str, Any]]:
    """Return firewall rule hit counters and statistics.
    
    Returns:
        list: List of hit counters with:
            - _id_ (str): Rule ID
            - name (str): Rule name
            - default_action (str): Default action (allow/deny)
            - bytes_count (int): Total bytes processed
            - packet_count (int): Total packets processed
            - rules (list): List of sub-rules
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        return firewall_data.get('hitcounter', []) if firewall_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall hit counters: {e}")
        return []

def get_firewall_marks() -> Dict[str, Any]:
    """Return firewall traffic marks and their values.
    
    Returns:
        dict: Dictionary of traffic marks and their hex values.
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        return firewall_data.get('marks', {}) if firewall_data else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall marks: {e}")
        return {}

def get_firewall_state_timeouts() -> Dict[str, Any]:
    """Return firewall state timeout configurations.
    
    Returns:
        dict: State timeout configurations including:
            - tcp_timeout_established (int): TCP established timeout
            - tcp_timeout_close (int): TCP close timeout
            - udp_timeout (int): UDP timeout
            - icmp_timeout (int): ICMP timeout
            - state_entry_limit (int): Maximum state entries
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        return firewall_data.get('state_timeouts', {}) if firewall_data else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall state timeouts: {e}")
        return {}

def get_firewall_connections_by_protocol(protocol: int = 6) -> List[Dict[str, Any]]:
    """Return firewall connections filtered by protocol.
    
    Args:
        protocol (int): Protocol number (6=TCP, 17=UDP, etc.). Defaults to 6.
        
    Returns:
        list: Connections for the specified protocol.
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        if firewall_data and 'connections' in firewall_data:
            return [conn for conn in firewall_data['connections'] if conn.get('proto') == protocol]
        return []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall connections for protocol {protocol}: {e}")
        return []

def get_firewall_connections_by_ip(ip_address: str = '') -> List[Dict[str, Any]]:
    """Return firewall connections involving a specific IP address.
    
    Args:
        ip_address (str): IP address to search for. Defaults to empty string.
        
    Returns:
        list: Connections involving the specified IP.
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        if firewall_data and 'connections' in firewall_data:
            matching_connections = []
            for conn in firewall_data['connections']:
                if (conn.get('orig_src') == ip_address or 
                    conn.get('orig_dst') == ip_address or
                    conn.get('reply_src') == ip_address or
                    conn.get('reply_dst') == ip_address):
                    matching_connections.append(conn)
            return matching_connections
        return []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall connections for IP {ip_address}: {e}")
        return []

def get_firewall_summary() -> Dict[str, Any]:
    """Return summary of firewall information.
    
    Returns:
        dict: Summary of firewall information including:
            - total_connections (int): Number of active connections
            - tcp_connections (int): Number of TCP connections
            - udp_connections (int): Number of UDP connections
            - established_connections (int): Number of established connections
            - total_rules (int): Number of firewall rules
            - total_bytes_processed (int): Total bytes processed by firewall
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        if not firewall_data:
            return {}
        
        connections = firewall_data.get('connections', [])
        hitcounters = firewall_data.get('hitcounter', [])
        
        summary = {
            'total_connections': len(connections),
            'tcp_connections': len([c for c in connections if c.get('proto') == 6]),
            'udp_connections': len([c for c in connections if c.get('proto') == 17]),
            'established_connections': len([c for c in connections if 'ESTABLISHED' in c.get('tcp_state', '')]),
            'total_rules': len(hitcounters),
            'total_bytes_processed': sum(counter.get('bytes_count', 0) for counter in hitcounters)
        }
        
        return summary
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall summary: {e}")
        return {}


# ============================================================================
# NETWORK DIAGNOSTIC CONVENIENCE FUNCTIONS
# ============================================================================

def ping_host(host: str, count: int = 4, timeout: float = 15.0, 
              interval: float = 0.5, packet_size: int = 56, 
              interface: str = None, bind_ip: bool = False) -> Optional[Dict[str, Any]]:
    """Ping a host using the router's diagnostic tools.
    
    Args:
        host: Target hostname or IP address
        count: Number of ping packets to send (default: 4)
        timeout: Timeout in seconds (default: 15.0)
        interval: Interval between packets in seconds (default: 0.5)
        packet_size: Size of ping packets in bytes (default: 56)
        interface: Network interface to use (default: None - uses WAN primary device)
        bind_ip: Whether to bind to specific IP (default: False)
        
    Returns:
        dict: Ping results including statistics with keys:
            - tx: number of pings transmitted
            - rx: number of pings received  
            - loss: percentage of lost pings
            - min: minimum round trip time in milliseconds
            - max: maximum round trip time in milliseconds
            - avg: average round trip time in milliseconds
            - error: error message if not successful
    """
    try:
        return _cs_client.ping_host(host, count, timeout, interval, packet_size, interface, bind_ip)
    except Exception as e:
        print(f"Error pinging host {host}: {e}")
        return None


def traceroute_host(host: str, max_hops: int = 30, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Perform traceroute to a host using the router's diagnostic tools.
    
    Args:
        host: Target hostname or IP address
        max_hops: Maximum number of hops (default: 30)
        timeout: Timeout per hop in seconds (default: 5.0)
        
    Returns:
        dict: Traceroute results including hop information
    """
    try:
        return _cs_client.traceroute_host(host, max_hops, timeout)
    except Exception as e:
        print(f"Error performing traceroute to {host}: {e}")
        return None


def speed_test(host: str = "", interface: str = "", duration: int = 5, 
               packet_size: int = 0, port: int = None, protocol: str = "tcp",
               direction: str = "both") -> Optional[Dict[str, Any]]:
    """Perform comprehensive network speed test using netperf with both upload and download.
    
    Args:
        host: Target host for speed test (empty for auto-detect)
        interface: Network interface to use (empty for auto-detect)
        duration: Test duration in seconds (default: 5)
        packet_size: Packet size in bytes (0 for default)
        port: Port number (None for default)
        protocol: Protocol to use - "tcp" or "udp" (default: "tcp")
        direction: Test direction - "recv", "send", "both", or "rr" (default: "both")
        
    Returns:
        dict: Speed test results with download_bps, upload_bps, and latency in simple bps
    """
    try:
        return _cs_client.speed_test(host, interface, duration, packet_size, port, protocol, direction)
    except Exception as e:
        print(f"Error performing speed test: {e}")
        return None


def start_packet_capture(interface: str = "any", filter: str = "", 
                        count: int = 20, timeout: int = 600,
                        wifichannel: str = "", wifichannelwidth: str = "", 
                        wifiextrachannel: str = "", url: str = "") -> Optional[Dict[str, Any]]:
    """Start packet capture using tcpdump API.
    
    Args:
        interface: Network interface to capture on (e.g., "mdm-9a724d09", "mon0", "any")
        filter: BPF filter expression (e.g., "net 192.168.0.0/24 and tcp and not port 80")
        count: Number of packets to capture (default: 20, 0 = unlimited)
        timeout: Capture timeout in seconds (default: 600, 0 = unlimited)
        wifichannel: WiFi channel for wireless captures (default: "")
        wifichannelwidth: WiFi channel width (default: "")
        wifiextrachannel: WiFi extra channel (default: "")
        url: Capture URL endpoint (default: "http://127.0.0.1:8000/capture")
        
    Note:
        If both count=0 and timeout=0, the capture will stream forever until interrupted.
        This is useful for continuous monitoring or thread-based captures.
        Use at least one limit (count > 0 or timeout > 0) for finite captures.
        
    Returns:
        dict: Packet capture start result with download URL
    """
    try:
        return _cs_client.start_packet_capture(interface, filter, count, timeout, wifichannel, wifichannelwidth, wifiextrachannel, url)
    except Exception as e:
        print(f"Error starting packet capture: {e}")
        return None


def stop_packet_capture() -> Optional[Dict[str, Any]]:
    """Stop running packet capture.
    
    Note: The tcpdump API doesn't have a specific stop endpoint.
    Captures are typically stopped by timeout or packet count limits.
    
    Returns:
        dict: Stop result (informational)
    """
    try:
        return _cs_client.stop_packet_capture()
    except Exception as e:
        print(f"Error stopping packet capture: {e}")
        return None


def get_available_interfaces() -> Optional[Dict[str, Any]]:
    """Get available network interfaces for packet capture.
    
    Returns:
        dict: Available interfaces with their types and status
    """
    try:
        return _cs_client.get_available_interfaces()
    except Exception as e:
        print(f"Error getting available interfaces: {e}")
        return None


def download_packet_capture(filename: str, local_path: str = None, capture_params: dict = None) -> Optional[Dict[str, Any]]:
    """Download a packet capture file.
    
    Args:
        filename: Name of the pcap file to download
        local_path: Local path to save the file (default: current directory)
        capture_params: Parameters used in the original capture (optional)
        
    Returns:
        dict: Download result with file path
    """
    try:
        return _cs_client.download_packet_capture(filename, local_path, capture_params)
    except Exception as e:
        print(f"Error downloading packet capture: {e}")
        return None


def start_streaming_capture(interface: str = "any", filter: str = "", 
                           wifichannel: str = "", wifichannelwidth: str = "", 
                           wifiextrachannel: str = "", url: str = "") -> Optional[Dict[str, Any]]:
    """Start a streaming packet capture that runs forever until interrupted.
    
    This is a convenience method for continuous monitoring or thread-based captures.
    
    Args:
        interface: Network interface to capture on (e.g., "mdm-9a724d09", "mon0", "any")
        filter: BPF filter expression (e.g., "net 192.168.0.0/24 and tcp and not port 80")
        wifichannel: WiFi channel for wireless captures (default: "")
        wifichannelwidth: WiFi channel width (default: "")
        wifiextrachannel: WiFi extra channel (default: "")
        url: Capture URL endpoint (default: "http://127.0.0.1:8000/capture")
        
    Returns:
        dict: Streaming capture start result with download URL
    """
    try:
        return _cs_client.start_streaming_capture(interface, filter, wifichannel, wifichannelwidth, wifiextrachannel, url)
    except Exception as e:
        print(f"Error starting streaming capture: {e}")
        return None


def get_packet_capture_status() -> Optional[Dict[str, Any]]:
    """Get packet capture status.
    
    Returns:
        dict: Current capture status
    """
    try:
        return _cs_client.get_packet_capture_status()
    except Exception as e:
        print(f"Error getting packet capture status: {e}")
        return None


def dns_lookup(hostname: str, record_type: str = "A") -> Optional[Dict[str, Any]]:
    """Perform DNS lookup using the router's DNS tools.
    
    Args:
        hostname: Hostname to resolve
        record_type: DNS record type (A, AAAA, MX, etc.)
        
    Returns:
        dict: DNS lookup results
    """
    try:
        return _cs_client.dns_lookup(hostname, record_type)
    except Exception as e:
        print(f"Error performing DNS lookup for {hostname}: {e}")
        return None


def clear_dns_cache() -> Optional[Dict[str, Any]]:
    """Clear the router's DNS cache.
    
    Returns:
        dict: Cache clear result
    """
    try:
        return _cs_client.clear_dns_cache()
    except Exception as e:
        print(f"Error clearing DNS cache: {e}")
        return None


def network_connectivity_test(host: str = "8.8.8.8", port: int = 53, 
                             timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Test network connectivity to a host and port.
    
    Args:
        host: Target host (default: "8.8.8.8")
        port: Target port (default: 53)
        timeout: Timeout in seconds (default: 5.0)
        
    Returns:
        dict: Connectivity test results
    """
    try:
        return _cs_client.network_connectivity_test(host, port, timeout)
    except Exception as e:
        print(f"Error testing connectivity to {host}:{port}: {e}")
        return None


def stop_ping() -> Optional[Dict[str, Any]]:
    """Stop any running ping process.
    
    Returns:
        dict: Stop result
    """
    try:
        return _cs_client.stop_ping()
    except Exception as e:
        print(f"Error stopping ping: {e}")
        return None


def speed_test(host: str = "", interface: str = "", duration: int = 5, 
               packet_size: int = 0, port: int = None, protocol: str = "tcp",
               direction: str = "both") -> Optional[Dict[str, Any]]:
    """Perform comprehensive network speed test using netperf with both upload and download.
    
    Args:
        host: Target host for speed test (empty for auto-detect)
        interface: Network interface to use (empty for auto-detect)
        duration: Test duration in seconds (default: 5)
        packet_size: Packet size in bytes (0 for default)
        port: Port number (None for default)
        protocol: Protocol to use - "tcp" or "udp" (default: "tcp")
        direction: Test direction - "recv", "send", "both", or "rr" (default: "both")
        
    Returns:
        dict: Speed test results with download_bps, upload_bps, and latency in simple bps
    """
    try:
        return _cs_client.speed_test(host, interface, duration, packet_size, port, protocol, direction)
    except Exception as e:
        print(f"Error performing speed test: {e}")
        return None


def stop_speed_test() -> Optional[Dict[str, Any]]:
    """Stop any running speed test.
    
    Returns:
        dict: Stop result
    """
    try:
        return _cs_client.stop_speed_test()
    except Exception as e:
        print(f"Error stopping speed test: {e}")
        return None


def start_file_server(folder_path: str = "files", port: int = 8000, 
                     host: str = "0.0.0.0", title: str = "File Download") -> Optional[Dict[str, Any]]:
    """Start a modern web file server for downloading files from a folder.
    
    Args:
        folder_path: Path to the folder to serve files from (default: "files")
                    Always uses subdirectories from current working directory
        port: Port to run the server on (default: 8000)
        host: Host to bind to (default: "0.0.0.0" - all interfaces)
        title: Title for the web page (default: "File Download")
        
    Returns:
        dict: Server start result with URL and status
    """
    try:
        return _cs_client.start_file_server(folder_path, port, host, title)
    except Exception as e:
        print(f"Error starting file server: {e}")
        return None


def create_user(username: str, password: str, group: str = "admin") -> Optional[Dict[str, Any]]:
    """Create a new user on the router.
    
    Args:
        username (str): The username for the new user
        password (str): The password for the new user
        group (str): The group for the user (default: "admin")
        
    Returns:
        dict: Result of the user creation operation
    """
    try:
        return _cs_client.create_user(username, password, group)
    except Exception as e:
        print(f"Error creating user: {e}")
        return None


def get_users() -> Optional[Dict[str, Any]]:
    """Get list of all users on the router.
    
    Returns:
        dict: List of users and their information
    """
    try:
        return _cs_client.get_users()
    except Exception as e:
        print(f"Error getting users: {e}")
        return None


def delete_user(username: str) -> Optional[Dict[str, Any]]:
    """Delete a user from the router.
    
    Args:
        username (str): The username to delete
        
    Returns:
        dict: Result of the user deletion operation
    """
    try:
        return _cs_client.delete_user(username)
    except Exception as e:
        print(f"Error deleting user: {e}")
        return None


def ensure_user_exists(username: str, password: str, group: str = "admin") -> Optional[Dict[str, Any]]:
    """Ensure a user exists, creating it if it doesn't.
    
    Args:
        username (str): The username to ensure exists
        password (str): The password for the user (used if creating)
        group (str): The group for the user (default: "admin")
        
    Returns:
        dict: Result of the operation
    """
    try:
        return _cs_client.ensure_user_exists(username, password, group)
    except Exception as e:
        print(f"Error ensuring user exists: {e}")
        return None


def ensure_fresh_user(username: str, group: str = "admin") -> Optional[Dict[str, Any]]:
    """Ensure a user exists with a fresh random password, deleting existing user first.
    
    Args:
        username (str): The username to ensure exists
        group (str): The group for the user (default: "admin")
        
    Returns:
        dict: Result of the operation with the generated password
    """
    try:
        return _cs_client.ensure_fresh_user(username, group)
    except Exception as e:
        print(f"Error ensuring fresh user exists: {e}")
        return None


def packet_capture(iface: str = None,
                  filter: str = "",
                  count: int = 10,
                  timeout: int = 10,
                  save_directory: str = "captures",
                  capture_user: str = "SDKTCPDUMP") -> Optional[Dict[str, Any]]:
    """Packet capture that handles everything in one call.
    
    This convenience function:
    1. Creates/ensures a dedicated user exists
    2. Captures packets on specified interface
    3. Downloads the pcap file to local directory
    4. Deletes the temporary user after successful completion
    
    Args:
        iface: Network interface to capture on (default: cp.get('config/lan/0/_id_'))
        filter: BPF filter expression (default: "" for all traffic)
        count: Number of packets to capture (default: 10)
        timeout: Capture timeout in seconds (default: 10)
        save_directory: Directory to save captured files (default: "captures")
        capture_user: Username for packet capture operations (default: "SDKTCPDUMP")
        
    Returns:
        dict: Result with all operation details
    """
    try:
        return _cs_client.packet_capture(
            iface=iface,
            filter=filter,
            count=count,
            timeout=timeout,
            save_directory=save_directory,
            capture_user=capture_user
        )
    except Exception as e:
        print(f"Error in packet capture: {e}")
        return None


def monitor_log(pattern: str = None,
                callback: callable = None,
                follow: bool = True,
                max_lines: int = 0,
                timeout: int = 0) -> Optional[Dict[str, Any]]:
    """Monitor /var/log/messages and optionally match lines against a pattern, sending matches to a callback.
    
    This convenience function provides real-time log monitoring with pattern matching and callback handling.
    It runs in a separate thread to avoid blocking the main application.
    
    Args:
        pattern: Regex pattern to match against log lines (default: None for all lines)
        callback: Function to call with matching lines (default: None for no callback)
        follow: Whether to follow the file (like tail -f) (default: True)
        max_lines: Maximum number of lines to process (0 = unlimited) (default: 0)
        timeout: Timeout in seconds (0 = no timeout) (default: 0)
        
    Returns:
        dict: Result with thread information and status
        
    Example:
        # Simple monitoring with callback
        def log_handler(line):
            print(f"Log line: {line}")
        
        result = cp.monitor_log(pattern="ERROR", callback=log_handler)
        
        # Monitor with timeout and max lines
        result = cp.monitor_log(
            pattern="WARNING|ERROR",
            max_lines=100,
            timeout=30
        )
        
        # Stop the monitor operation
        cp.stop_monitor_log(result)
    """
    try:
        return _cs_client.monitor_log(
            pattern=pattern,
            callback=callback,
            follow=follow,
            max_lines=max_lines,
            timeout=timeout
        )
    except Exception as e:
        print(f"Error in monitor_log: {e}")
        return None


def stop_monitor_log(monitor_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Stop a running monitor_log operation.
    
    Args:
        monitor_result: The result dictionary returned by monitor_log()
        
    Returns:
        dict: Result of the stop operation
        
    Example:
        result = cp.monitor_log(pattern="ERROR", callback=my_handler)
        # ... later ...
        stop_result = cp.stop_monitor_log(result)
    """
    try:
        return _cs_client.stop_monitor_log(monitor_result)
    except Exception as e:
        print(f"Error stopping monitor_log: {e}")
        return None


def execute_cli(commands: Union[str, List[str]],
                timeout: int = 10,
                soft_timeout: int = 5,
                clean: bool = True) -> Optional[str]:
    """Execute CLI commands and return the output.
    
    This convenience function provides a simplified interface to execute CLI commands
    using the config store terminal interface. It handles command execution, output
    capture, and cleanup automatically.
    
    Args:
        commands: Single command string or list of commands to execute
        timeout: Absolute maximum number of seconds to wait for output (default: 10)
        soft_timeout: Number of seconds to wait before sending interrupt (default: 5)
        clean: Whether to remove terminal escape sequences from output (default: True)
        
    Returns:
        str: Command output, or None if an error occurred
        
    Example:
        # Single command
        output = cp.execute_cli("show version")
        if output:
            print(output)
        
        # Multiple commands
        output = cp.execute_cli(["show version", "show interfaces"])
        
        # With custom timeout
        output = cp.execute_cli("show config", timeout=30)
        
        # Raw output (with escape sequences)
        output = cp.execute_cli("show status", clean=False)
    """
    try:
        return _cs_client.execute_cli(
            commands=commands,
            timeout=timeout,
            soft_timeout=soft_timeout,
            clean=clean
        )
    except Exception as e:
        print(f"Error executing CLI commands: {e}")
        return None


def monitor_sms(callback: callable,
                timeout: int = 0) -> Optional[Dict[str, Any]]:
    """Monitor SMS messages and send parsed data to a callback function.
    
    This convenience function monitors /var/log/messages for SMS received messages and 
    automatically parses the phone number and message content, sending structured data 
    to the callback.
    
    Args:
        callback: Function to call with SMS data (phone_number, message, raw_line)
        timeout: Timeout in seconds (0 = no timeout) (default: 0)
        
    Returns:
        dict: Result with thread information and status
        
    Example:
        def sms_handler(phone_number, message, raw_line):
            print(f"SMS from {phone_number}: {message}")
            # Auto-reply
            output = cp.execute_cli(f'sms {phone_number} Thanks for your message!')
            if output:
                print(f"Auto-reply sent to {phone_number}")
        
        result = cp.monitor_sms(callback=sms_handler)
        
        # Stop monitoring
        cp.stop_monitor_sms(result)
    """
    try:
        return _cs_client.monitor_sms(callback=callback, timeout=timeout)
    except Exception as e:
        print(f"Error in monitor_sms: {e}")
        return None


def stop_monitor_sms(monitor_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Stop a running monitor_sms operation.
    
    Args:
        monitor_result: The result dictionary returned by monitor_sms()
        
    Returns:
        dict: Result of the stop operation
        
    Example:
        result = cp.monitor_sms(callback=my_handler)
        # ... later ...
        stop_result = cp.stop_monitor_sms(result)
    """
    try:
        return _cs_client.stop_monitor_sms(monitor_result)
    except Exception as e:
        print(f"Error stopping monitor_sms: {e}")
        return None


def send_sms(phone_number: str = None,
             message: str = None,
             port: str = None) -> Optional[str]:
    """Send an SMS message using the CLI.
    
    This convenience function sends an SMS message using the CLI command with automatic 
    port detection if no port is specified. It finds the first connected modem and uses its port.
    
    Args:
        phone_number: The phone number to send the SMS to
        message: The message content to send
        port: The modem port to use (default: None for auto-detection)
        
    Returns:
        str: CLI command output, or None if an error occurred
        
    Example:
        # Send SMS with auto-detected port
        output = cp.send_sms(phone_number="+1234567890", message="Hello from the router!")
        if output:
            print("SMS sent successfully")
        
        # Send SMS with specific port
        output = cp.send_sms(phone_number="+1234567890", message="Hello!", port="ttyUSB0")
        
        # Use in SMS auto-reply
        def sms_handler(phone_number, message, raw_line):
            response = f"Thanks for your message: {message}"
            output = cp.send_sms(phone_number=phone_number, message=response)
            if output:
                print(f"Auto-reply sent to {phone_number}")
    """
    try:
        return _cs_client.send_sms(
            phone_number=phone_number,
            message=message,
            port=port
        )
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return None
