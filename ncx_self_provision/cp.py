"""
NCOS communication module for SDK applications.

Copyright (c) 2022 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.

This file contains confidential information of CradlePoint, Inc. and your use of
this file is subject to the CradlePoint Software License Agreement distributed with
this file. Unauthorized reproduction or distribution of this file is subject to civil and
criminal penalties.
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

try:
    import traceback
except ImportError:
    traceback = None


class SdkCSException(Exception):
    pass


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
        """Checks if the singleton instance has been created."""
        return cls in cls._instances

    def __new__(cls, *na, **kwna):
        """Singleton factory (with subclassing support)."""
        if not cls.is_initialized():
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, app_name, init=False):
        """
        Initializes the CSClient.

        Args:
            app_name (str): The name of the application.
            init (bool): Flag to perform full initialization.
        """
        self.app_name = app_name
        self.ncos = '/var/mnt/sdk' in os.getcwd()  # Running in NCOS
        handlers = [logging.StreamHandler()]
        if 'linux' in sys.platform:
            handlers.append(logging.handlers.SysLogHandler(address='/dev/log'))
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s: %(message)s', datefmt='%b %d %H:%M:%S',
                            handlers=handlers)
        self.logger = logging.getLogger(app_name)
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
            value: Not required.
            query: Not required.
            tree: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}

        """
        if 'linux' in sys.platform:
            cmd = "get\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd).get('data')
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

            return json.loads(response.text).get('data')

    def decrypt(self, base, query='', tree=0):
        """
        Constructs and sends a decrypt/get request to retrieve specified data from a device.

        The behavior of this method is contextual:
            - If the app is installed on (and executed from) a device, it directly queries the router tree to retrieve the
              specified data.
            - If the app running remotely from a computer it calls the HTTP GET method to retrieve the specified data.

        Args:
            base: String representing a path to a resource on a router tree,
                  (i.e. '/config/system/logging/level').
            value: Not required.
            query: Not required.
            tree: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}

        """
        if 'linux' in sys.platform:
            cmd = "decrypt\n{}\n{}\n{}\n".format(base, query, tree)
            return self._dispatch(cmd).get('data')
        else:
            # Running in a computer and can't actually send the alert.
            print('Decrypt is only available when running the app in NCOS.')

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
        value = json.dumps(value)
        if 'linux' in sys.platform:
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

    def post(self, base, value='', query=''):
        """
        Constructs and sends a post request to update or add specified data to the device router tree.

        The behavior of this method is contextual:
            - If the app is installed on(and executed from) a device, it directly updates or adds the specified data to
              the router tree.
            - If the app running remotely from a computer it calls the HTTP POST method to update or add the specified
              data.


        Args:
            base: String representing a path to a resource on a router tree,
                  (i.e. '/config/system/logging/level').
            value: Not required.
            query: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}
        """
        value = json.dumps(value)
        if 'linux' in sys.platform:
            cmd = f"post\n{base}\n{query}\n{value}\n"
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the post to the device.
            import requests
            device_ip, username, password = self._get_device_access_info()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.post(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_auth(device_ip, username, password),
                                        data={"data": '{}'.format(value)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def patch(self, value):
        """
        Constructs and sends a patch request to update or add specified data to the device router tree.

        The behavior of this method is contextual:
            - If the app is installed on(and executed from) a device, it directly updates or adds the specified data to
              the router tree.
            - If the app running remotely from a computer it calls the HTTP PUT method to update or add the specified
              data.

        Args:
            value: list containing dict of add/changes, and list of removals:  [{add},[remove]]

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}
        """

        if 'linux' in sys.platform:
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
            import requests
            device_ip, username, password = self._get_device_access_info()
            device_api = 'http://{}/api/'.format(device_ip)

            try:
                response = requests.patch(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_auth(device_ip, username, password),
                                        data={"data": '{}'.format(json.dumps(value))})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def delete(self, base, query=''):
        """
        Constructs and sends a delete request to delete specified data to the device router tree.

        The behavior of this method is contextual:
            - If the app is installed on(and executed from) a device, it directly deletes the specified data to
              the router tree.
            - If the app running remotely from a computer it calls the HTTP DELETE method to update or add the specified
              data.


        Args:
            base: String representing a path to a resource on a router tree,
                  (i.e. '/config/system/logging/level').
            query: Not required.

        Returns:
            A dictionary containing the response (i.e. {"success": True, "data:": {}}
        """
        if 'linux' in sys.platform:
            cmd = "delete\n{}\n{}\n".format(base, query)
            return self._dispatch(cmd)
        else:
            # Running in a computer so use http to send the delete to the device.
            import requests
            device_ip, username, password = self._get_device_access_info()
            device_api = 'http://{}/api/{}/{}'.format(device_ip, base, query)

            try:
                response = requests.delete(device_api,
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        auth=self._get_auth(device_ip, username, password),
                                        data={"data": '{}'.format(base)})
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError):
                print("Timeout: device at {} did not respond.".format(device_ip))
                return None

            return json.loads(response.text)

    def alert(self, value=''):
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
        if 'linux' in sys.platform:
            cmd = "alert\n{}\n{}\n".format(self.app_name, value)
            return self._dispatch(cmd)
        else:
            # Running in a computer and can't actually send the alert.
            print('Alert is only available when running the app in NCOS.')
            print('Alert Text: {}'.format(value))

    def log(self, value=''):
        """
        Adds an INFO log to the device SYSLOG.

        Args:
        value: String text for the log.

        Returns:
        None
        """
        if self.ncos:
            # Running in NCOS so write to the logger
            self.logger.info(value)
        elif 'linux' in sys.platform:
            # Running in Linux (container?) so write to stdout
            with open('/dev/stdout', 'w') as log:
                log.write(f'{self.app_name}: {value}\n')
        else:
            # Running in a computer so just use print for the log.
            print(value)


    def _get_auth(self, device_ip, username, password):
        """
        Returns the proper HTTP Auth for the NCOS version.
        
        This is only needed when the app is running in a computer.
        Digest Auth is used for NCOS 6.4 and below while Basic Auth is
        used for NCOS 6.5 and up.
        """
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
        """
        Returns device access info from the sdk_settings.ini file.
        
        This should only be called when running on a computer.
        """
        device_ip = ''
        device_username = ''
        device_password = ''

        if 'linux' not in sys.platform:
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
        """Safely dispatches a command to the router."""
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

    def _safe_receive(self, sock):
        """Safely receives data from a socket."""
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
        """Receives data from a socket with error handling."""
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
    running = False
    registry = {}
    eids = 1

    def __init__(self, *args, **kwargs):
        """Initializes the EventingCSClient and sets up aliases for register/unregister."""
        super().__init__(*args, **kwargs)
        self.on = self.register
        self.un = self.unregister

    def start(self):
        """Starts the event handling loop in a separate thread."""
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

    def stop(self):
        """Stops the event handling loop and cleans up resources."""
        if not self.running:
            return
        self.log(f"Stopping")
        for k in list(self.registry.keys()):
            self.unregister(k)
        self.event_sock.close()
        os.unlink(self.f)
        self.running = False

    def _handle_events(self):
        """The main event loop for handling config store events."""
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

    def register(self, action: object, path: object, callback: object, *args: object) -> object:
        """
        Registers a callback for a config store event.

        Args:
            action (str): The action to listen for (e.g., 'set', 'get').
            path (str): The config store path to monitor.
            callback (callable): The function to call when the event occurs.
            *args: Additional arguments to pass to the callback.

        Returns:
            The result of the registration command.
        """
        if not self.running:
            self.start()
        # what about multiple registration?
        eid = self.eids
        self.eids += 1
        self.registry[eid] = {'cb': callback, 'action': action, 'path': path, 'args': args}
        cmd = "register\n{}\n{}\n{}\n{}\n".format(self.pid, eid, action, path)
        return self._dispatch(cmd)

    def unregister(self, eid):
        """
        Unregisters a callback by its event ID.

        Args:
            eid (int): The event ID returned by register.

        Returns:
            The result of the unregistration command.
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

def _get_app_name():
    """Get the app name from the first section of package.ini"""
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
    except Exception:
        return 'SDK'

# Create a single EventingCSClient instance with name from package.ini
_cs_client = EventingCSClient(_get_app_name())

def get_uptime():
    """Return the router uptime in seconds."""
    uptime = int(_cs_client.get('status/system/uptime'))
    return uptime

def wait_for_uptime(min_uptime_seconds):
    """Wait for the device uptime to be greater than the specified uptime and sleep if it is less than the specified uptime."""
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

def wait_for_wan_connection(timeout=300):
    """Waits for at least one WAN connection to be 'connected'.
    Returns True if a connection is established within the timeout, otherwise False."""
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

def get_appdata(name):
    """Get value of appdata from NCOS Config by name."""
    appdata = _cs_client.get('config/system/sdk/appdata')
    return next(iter(x["value"] for x in appdata if x["name"] == name), None)

def post_appdata(name, value):
    """Create appdata in NCOS Config by name."""
    _cs_client.post('config/system/sdk/appdata', {"name": name, "value": value})

def put_appdata(name, value):
    """Set value of appdata in NCOS Config by name."""
    appdata = _cs_client.get('config/system/sdk/appdata')
    for item in appdata:
        if item["name"] == name:
            _cs_client.put(f'config/system/sdk/appdata/{item["_id_"]}/value', value)

def delete_appdata(name):
    """Delete appdata in NCOS Config by name."""
    appdata = _cs_client.get('config/system/sdk/appdata')
    for item in appdata:
        if item["name"] == name:
            _cs_client.delete(f'config/system/sdk/appdata/{item["_id_"]}')

def get_ncm_api_keys():
    """Get NCM API keys from the router's certificate management configuration.
    Returns:
        dict: Dictionary containing all API keys, with None for any missing keys
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

def extract_cert_and_key(cert_name_or_uuid):
    """Extract and save the certificate and key to the local filesystem. Returns the filenames of the certificate and key files."""
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

def get_ipv4_wired_clients():
    """Return a list of IPv4 wired clients and their details."""
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

def get_ipv4_wifi_clients():
    """Return a list of IPv4 Wi-Fi clients and their details."""
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

def get_ipv4_lan_clients():
    """Return a dictionary containing all IPv4 clients, both wired and Wi-Fi."""
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

def dec(deg, min, sec):
    """Return decimal version of lat or long from deg, min, sec"""
    if str(deg)[0] == '-':
        dec_val = deg - (min / 60) - (sec / 3600)
    else:
        dec_val = deg + (min / 60) + (sec / 3600)
    return round(dec_val, 6)

def get_lat_long():
    """Return latitude and longitude as floats"""
    fix = _cs_client.get('status/gps/fix')
    retries = 0
    while not fix and retries < 5:
        time.sleep(0.1)
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

def get_connected_wans():
    """Return list of connected WAN UIDs"""
    wans = []
    while not wans:
        wans = _cs_client.get('status/wan/devices')
    # get the wans that are connected
    wans = [k for k, v in wans.items() if v['status']['connection_state'] == 'connected']
    if not wans:
        _cs_client.log('No WANs connected!')
    return wans

def get_sims():
    """Return list of modem UIDs with SIMs"""
    SIMs = []
    devices = None
    while not devices:
        devices = _cs_client.get('status/wan/devices')
    for uid, status in devices.items():
        if uid.startswith('mdm-'):
            error_text = status.get('status', {}).get('error_text', '')
            if error_text:
                if 'NOSIM' in error_text:
                    continue
            SIMs.append(uid)
    return SIMs

# Direct access to the underlying EventingCSClient methods
def get(base, query='', tree=0):
    """Direct access to the underlying get method."""
    return _cs_client.get(base, query, tree)

def post(base, value='', query=''):
    """Direct access to the underlying post method."""
    return _cs_client.post(base, value, query)

def put(base, value='', query='', tree=0):
    """Direct access to the underlying put method."""
    return _cs_client.put(base, value, query, tree)

def delete(base, query=''):
    """Direct access to the underlying delete method."""
    return _cs_client.delete(base, query)

def decrypt(base, query='', tree=0):
    """Direct access to the underlying decrypt method."""
    return _cs_client.decrypt(base, query, tree)

def log(value=''):
    """Direct access to the underlying log method."""
    return _cs_client.log(value)

def alert(value=''):
    """Direct access to the underlying alert method."""
    return _cs_client.alert(value)

def register(action, path, callback, *args):
    """Registers a callback for a config store event."""
    return _cs_client.register(action, path, callback, *args)

def unregister(eid):
    """Unregisters a callback by its event ID."""
    return _cs_client.unregister(eid)

# Expose the logger for advanced logging control
def get_logger():
    """Get the logger instance for advanced logging control."""
    return _cs_client.logger

# Monkay patch for cp.uptime()
def uptime():
    return time.time()
    
def clean_up_reg(signal, frame):
    """
    When 'cppython remote_port_forward.py' gets a SIGTERM, config_store_receiver.py doesn't
    clean up registrations. Even if it did, the comm module can't rely on an external service
    to clean up.
    """
    _cs_client.stop()
    sys.exit(0)


signal.signal(signal.SIGTERM, clean_up_reg)
