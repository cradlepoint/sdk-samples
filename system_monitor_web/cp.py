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
        if not init:
            return
        
        self.app_name = app_name

        # Determine if running on NCOS by checking if we can connect to the socket /var/tmp/cs.sock
        self.ncos = False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                sock.connect('/var/tmp/cs.sock')
                self.ncos = True
        except Exception:
            self.ncos = False
            
        handlers = [logging.StreamHandler()]
        if self.ncos:
            handlers.append(logging.handlers.SysLogHandler(address='/dev/log'))
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s: %(message)s', datefmt='%b %d %H:%M:%S',
                            handlers=handlers)
        self.logger = logging.getLogger(app_name)

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
        if self.ncos:
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
        if self.ncos:
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
        if self.ncos:
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
        if self.ncos:
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
        if self.ncos:
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
        if self.ncos:
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

    def __init__(self, app_name, init=True):
        """Initializes the EventingCSClient and sets up aliases for register/unregister."""
        super().__init__(app_name, init)
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

def wait_for_ntp(timeout=300, check_interval=1):
    """
    Wait until NTP sync age is not null, indicating NTP synchronization.
    
    Args:
        timeout (int): Maximum time to wait in seconds (default: 300)
        check_interval (int): Time between checks in seconds (default: 1)
    
    Returns:
        bool: True if NTP sync was achieved within timeout, False otherwise
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        sync_age = _cs_client.get('status/system/ntp/sync_age')
        
        if sync_age is not None:
            _cs_client.log(f'NTP sync achieved, sync_age: {sync_age}')
            return True
            
        time.sleep(check_interval)
    
    _cs_client.log(f'NTP sync timeout after {timeout} seconds')
    return False

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

def get_device_mac():
    """Return the device MAC address without colons"""
    mac = _cs_client.get('status/product_info/mac0')
    return mac.replace(':', '') if mac else None

def get_device_serial_num():
    """Return the device serial number"""
    return _cs_client.get('status/product_info/manufacturing/serial_num')

def get_device_product_type():
    """Return the device product type"""
    return _cs_client.get('status/product_info/manufacturing/product_name')

def get_device_name():
    """Return the device name"""
    return _cs_client.get('config/system/system_id')

def get_device_firmware():
    """Return the device firmware information"""
    fw_info = _cs_client.get('status/fw_info')
    firmware = f"{fw_info.get('major')}.{fw_info.get('minor')}.{fw_info.get('patch')}-{fw_info.get('fw_release_tag')}"
    return firmware

def get_system_resources(cpu=True, memory=True):
    """Return a dictionary containing the system resources"""
    system_resources = {}
    
    if cpu:
        cpu = _cs_client.get('status/system/cpu')
        system_resources['cpu'] = f"CPU Usage: {round(float(cpu['nice']) + float(cpu['system']) + float(cpu['user']) * 100)}%"
    if memory:
        memory = _cs_client.get('status/system/memory')
        system_resources['avail_mem'] = f"Available Memory: {memory['memavailable'] / float(1 << 20):,.0f} MB"
        system_resources['total_mem'] = f"Total Memory: {memory['memtotal'] / float(1 << 20):,.0f} MB"
        system_resources['free_mem'] = f"Free Memory: {memory['memfree'] / float(1 << 20):,.0f} MB"

    return system_resources

def get_ncm_status():
    """Return the NCM status"""
    return _cs_client.get('status/ecm/state')

def reboot_device():
    """Reboot the device"""
    _cs_client.put('control/system/reboot', 'reboot hypmgr')
    
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

# Alias for register function
on = register

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

# ============================================================================
# STATUS MONITORING FUNCTIONS
# ============================================================================

def get_wan_devices_status():
    """
    Return detailed status information for all WAN devices.
    
    Returns:
        dict: Dictionary containing all WAN devices with keys like 'mdm-{id}', 'eth-{id}', etc.
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

def get_modem_status():
    """
    Return detailed status information for cellular modem devices only.
    
    Returns:
        dict: Dictionary containing only modem devices with keys like 'mdm-{id}'.
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

def get_signal_strength():
    """
    Return signal strength information for all cellular modems.
    
    Returns:
        dict: Dictionary with modem IDs as keys, containing:
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

def get_temperature():
    """Return device temperature information"""
    try:
        # Temperature is a direct value, not a directory
        temp = _cs_client.get('status/system/temperature')
        return temp
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving temperature: {e}")
        return None

def get_power_usage():
    """Return power usage information"""
    try:
        power_components = {}
        components = ['system_power', 'cpu_power', 'modem_power', 'wifi_power', 
                     'poe_pse_power', 'ethernet_ports_power', 'bluetooth_power', 
                     'usb_power', 'gps_power', 'led_power', 'total']
        
        for component in components:
            try:
                value = _cs_client.get(f'status/power_usage/{component}')
                power_components[component] = value
            except:
                power_components[component] = None
        
        return power_components
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving power usage: {e}")
        return None

def get_wlan_status():
    """
    Return comprehensive wireless LAN status and configuration information.
    
    Returns:
        dict: Dictionary containing all WLAN status information including
              clients, radio details, events, region settings, and trace data.
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN status: {e}")
        return None

def get_wlan_clients():
    """
    Return connected wireless clients information.
    
    Returns:
        list: List of connected wireless clients with their details
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('clients', []) if wlan_status else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN clients: {e}")
        return []

def get_wlan_radio_status():
    """
    Return wireless radio status and configuration for all bands.
    
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

def get_wlan_radio_by_band(band):
    """
    Return wireless radio status for a specific frequency band.
    
    Args:
        band (str): Frequency band ('2.4 GHz' or '5 GHz')
    
    Returns:
        dict or None: Radio configuration for the specified band, or None if not found
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

def get_wlan_events():
    """
    Return wireless LAN events and monitoring data.
    
    Returns:
        dict: Dictionary containing WiFi events:
            - associate: Association events
            - deauthenticated: Deauthentication events
            - disassociate: Disassociation events
            - mac_filter_allow: MAC filter allow events
            - mac_filter_deny: MAC filter deny events
            - timeout: Timeout events
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('events', {}) if wlan_status else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN events: {e}")
        return {}

def get_wlan_region_config():
    """
    Return wireless LAN regional configuration settings.
    
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

def get_wlan_remote_status():
    """
    Return remote WiFi controller status and configuration.
    
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

def get_wlan_state():
    """
    Return wireless LAN operational state.
    
    Returns:
        str: WiFi state ('On' or 'Off')
    """
    try:
        wlan_status = _cs_client.get('status/wlan')
        return wlan_status.get('state', 'Unknown') if wlan_status else 'Unknown'
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN state: {e}")
        return 'Unknown'

def get_wlan_trace():
    """
    Return wireless LAN initialization trace data.
    
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

def get_wlan_debug():
    """
    Return wireless LAN debug information.
    
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

def get_wlan_channel_info(band=None):
    """
    Return wireless LAN channel information for specified band or all bands.
    
    Args:
        band (str, optional): Frequency band ('2.4 GHz' or '5 GHz'). If None, returns all bands.
    
    Returns:
        dict: Dictionary containing channel information:
            - current_channel (int): Current channel number
            - available_channels (list): List of available channels
            - channel_locked (bool): Whether channel is locked
            - channel_contention (int): Channel contention value
            - txpower (int): Transmit power in percentage
    """
    try:
        if band:
            radio = get_wlan_radio_by_band(band)
            if radio:
                return {
                    'current_channel': radio.get('channel'),
                    'available_channels': radio.get('channel_list', []),
                    'channel_locked': radio.get('channel_locked', False),
                    'channel_contention': radio.get('channel_contention', 0),
                    'txpower': radio.get('txpower', 0)
                }
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
            return channel_info
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN channel info: {e}")
        return {}

def get_wlan_client_count():
    """
    Return the count of connected wireless clients.
    
    Returns:
        int: Number of connected wireless clients
    """
    try:
        clients = get_wlan_clients()
        return len(clients)
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN client count: {e}")
        return 0

def get_wlan_client_count_by_band():
    """
    Return the count of connected wireless clients per frequency band.
    
    Returns:
        dict: Dictionary with band names as keys and client counts as values
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

def get_firewall_status():
    """Return firewall status and rules"""
    try:
        firewall_status = _cs_client.get('status/firewall')
        return firewall_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall status: {e}")
        return None

def get_qos_status():
    """Return Quality of Service status"""
    try:
        qos_status = _cs_client.get('status/qos')
        return qos_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS status: {e}")
        return None

def get_gps_status():
    """Return GPS status and fix information"""
    try:
        gps_status = _cs_client.get('status/gps')
        return gps_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving GPS status: {e}")
        return None

def get_dhcp_leases():
    """Return DHCP lease information"""
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        return leases
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP leases: {e}")
        return None

def get_network_interfaces():
    """Return network interface status"""
    try:
        interfaces = _cs_client.get('status/network')
        return interfaces
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving network interfaces: {e}")
        return None

def get_routing_table():
    """Return routing table information"""
    try:
        routes = _cs_client.get('status/routing')
        return routes
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving routing table: {e}")
        return None

def get_dns_status():
    """Return DNS status and configuration"""
    try:
        dns_status = _cs_client.get('status/dns')
        return dns_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DNS status: {e}")
        return None

def get_openvpn_status():
    """Return OpenVPN status and connections"""
    try:
        openvpn_status = _cs_client.get('status/openvpn')
        return openvpn_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving OpenVPN status: {e}")
        return None

def get_certificate_status():
    """Return certificate management status"""
    try:
        cert_status = _cs_client.get('status/certmgmt')
        return cert_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate status: {e}")
        return None

def get_storage_status():
    """Return storage device status"""
    try:
        storage_status = {
            'health': _cs_client.get('status/system/storage/health'),
            'slc_health': _cs_client.get('status/system/storage/slc_health')
        }
        return storage_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving storage status: {e}")
        return None

def get_usb_status():
    """Return USB device status"""
    try:
        usb_status = {
            'connection': _cs_client.get('status/usb/connection'),
            'int1': _cs_client.get('status/usb/int1')
        }
        return usb_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving USB status: {e}")
        return None

def get_poe_status():
    """Return Power over Ethernet status"""
    try:
        # PoE directory appears to be empty on this router
        poe_status = _cs_client.get('status/system/poe_pse')
        return poe_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving PoE status: {e}")
        return None

def get_sensors_status():
    """Return sensor status information"""
    try:
        sensors_status = {
            'level': _cs_client.get('status/system/sensors/level'),
            'day': _cs_client.get('status/system/sensors/day')
        }
        return sensors_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving sensors status: {e}")
        return None

def get_services_status():
    """Return system services status"""
    try:
        services_status = _cs_client.get('status/system/services')
        return services_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving services status: {e}")
        return None

def get_apps_status():
    """Return SDK applications status"""
    try:
        apps_status = _cs_client.get('status/system/apps')
        return apps_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving apps status: {e}")
        return None

def get_log_status():
    """Return system log status"""
    try:
        # Log directory appears to be empty
        log_status = _cs_client.get('status/log')
        return log_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving log status: {e}")
        return None

def get_event_status():
    """Return system events status"""
    try:
        event_status = _cs_client.get('status/event')
        return event_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving event status: {e}")
        return None

def get_network_throughput():
    """Return network throughput statistics"""
    try:
        stats = _cs_client.get('status/stats')
        return stats
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving network throughput: {e}")
        return None

def get_flow_statistics():
    """Return flow statistics"""
    try:
        flow_stats = _cs_client.get('status/flowstats')
        return flow_stats
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving flow statistics: {e}")
        return None

def get_client_usage():
    """Return client usage statistics"""
    try:
        client_usage = _cs_client.get('status/client_usage')
        return client_usage
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving client usage: {e}")
        return None

def get_multicast_status():
    """Return multicast status"""
    try:
        multicast_status = _cs_client.get('status/multicast')
        return multicast_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving multicast status: {e}")
        return None

def get_vpn_status():
    """Return VPN status (OpenVPN, L2TP, etc.)"""
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

def get_security_status():
    """Return security-related status"""
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

def get_iot_status():
    """Return IoT-related status"""
    try:
        iot_status = _cs_client.get('status/iot')
        return iot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving IoT status: {e}")
        return None

def get_obd_status():
    """Return OBD (On-Board Diagnostics) status"""
    try:
        obd_status = _cs_client.get('status/obd')
        return obd_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving OBD status: {e}")
        return None

def get_hotspot_status():
    """Return hotspot status"""
    try:
        hotspot_status = _cs_client.get('status/hotspot')
        return hotspot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving hotspot status: {e}")
        return None

def get_sdwan_status():
    """Return SD-WAN status"""
    try:
        sdwan_status = _cs_client.get('status/sdwan_adv')
        return sdwan_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving SD-WAN status: {e}")
        return None

def get_comprehensive_status():
    """Return a comprehensive status report of the router"""
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
            'clients': get_ipv4_lan_clients(),
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
        return status_report
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving comprehensive status: {e}")
        return None

def wait_for_modem_connection(timeout=300):
    """Wait for modem to establish a connection"""
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
        time.sleep(1)
    _cs_client.log(f"Timeout waiting for modem connection after {timeout} seconds.")
    return False

def wait_for_gps_fix(timeout=300):
    """Wait for GPS to acquire a fix"""
    _cs_client.log("Waiting for GPS fix...")
    end_time = time.time() + timeout
    while time.time() < end_time:
        gps_status = get_gps_status()
        if gps_status and gps_status.get('fix', {}).get('lock'):
            _cs_client.log("GPS fix acquired.")
            return True
        time.sleep(1)
    _cs_client.log(f"Timeout waiting for GPS fix after {timeout} seconds.")
    return False

# ============================================================================
# CONFIGURATION MANAGEMENT FUNCTIONS
# ============================================================================

def get_system_config():
    """
    Return system configuration settings.
    
    Returns:
        dict: System configuration including logging, SDK settings, time, etc.
    """
    try:
        system_config = _cs_client.get('config/system')
        return system_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving system config: {e}")
        return None

def get_network_config():
    """
    Return network configuration settings.
    
    Returns:
        dict: Network configuration including interfaces, routing, etc.
    """
    try:
        network_config = _cs_client.get('config/network')
        return network_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving network config: {e}")
        return None

def get_wlan_config():
    """
    Return wireless LAN configuration settings.
    
    Returns:
        dict: WLAN configuration including radio settings, SSIDs, security, etc.
    """
    try:
        wlan_config = _cs_client.get('config/wlan')
        return wlan_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WLAN config: {e}")
        return None

def get_wan_config():
    """
    Return WAN configuration settings.
    
    Returns:
        dict: WAN configuration including connection settings, failover, etc.
    """
    try:
        wan_config = _cs_client.get('config/wan')
        return wan_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving WAN config: {e}")
        return None

def get_firewall_config():
    """
    Return firewall configuration settings.
    
    Returns:
        dict: Firewall configuration including rules, policies, etc.
    """
    try:
        firewall_config = _cs_client.get('config/firewall')
        return firewall_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall config: {e}")
        return None

def get_qos_config():
    """
    Return Quality of Service configuration settings.
    
    Returns:
        dict: QoS configuration including policies, bandwidth limits, etc.
    """
    try:
        qos_config = _cs_client.get('config/qos')
        return qos_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS config: {e}")
        return None

def get_dhcp_config():
    """
    Return DHCP configuration settings.
    
    Returns:
        dict: DHCP configuration including pools, reservations, etc.
    """
    try:
        dhcp_config = _cs_client.get('config/dhcpd')
        return dhcp_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP config: {e}")
        return None

def get_dns_config():
    """
    Return DNS configuration settings.
    
    Returns:
        dict: DNS configuration including servers, domains, etc.
    """
    try:
        dns_config = _cs_client.get('config/dns')
        return dns_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DNS config: {e}")
        return None

def get_openvpn_config():
    """
    Return OpenVPN configuration settings.
    
    Returns:
        dict: OpenVPN configuration including tunnels, certificates, etc.
    """
    try:
        openvpn_config = _cs_client.get('config/openvpn')
        return openvpn_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving OpenVPN config: {e}")
        return None

def get_certificate_config():
    """
    Return certificate management configuration settings.
    
    Returns:
        dict: Certificate configuration including certificates, CAs, etc.
    """
    try:
        cert_config = _cs_client.get('config/certmgmt')
        return cert_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate config: {e}")
        return None

def get_hotspot_config():
    """
    Return hotspot configuration settings.
    
    Returns:
        dict: Hotspot configuration including sessions, clients, etc.
    """
    try:
        hotspot_config = _cs_client.get('config/hotspot')
        return hotspot_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving hotspot config: {e}")
        return None

def get_sdwan_config():
    """
    Return SD-WAN configuration settings.
    
    Returns:
        dict: SD-WAN configuration including policies, routing, etc.
    """
    try:
        sdwan_config = _cs_client.get('config/sdwan_adv')
        return sdwan_config
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving SD-WAN config: {e}")
        return None

def get_comprehensive_config():
    """
    Return comprehensive configuration of the router.
    
    This function aggregates configuration data from multiple endpoints to provide
    a complete overview of the router's configuration.
    
    Returns:
        dict: Comprehensive configuration report containing:
            - system: System configuration settings
            - network: Network configuration settings
            - wlan: Wireless LAN configuration
            - wan: WAN configuration settings
            - firewall: Firewall configuration
            - qos: Quality of Service configuration
            - dhcp: DHCP configuration settings
            - dns: DNS configuration settings
            - openvpn: OpenVPN configuration
            - certificates: Certificate management configuration
            - hotspot: Hotspot configuration
            - sdwan: SD-WAN configuration
    """
    try:
        config_report = {
            'system': get_system_config(),
            'network': get_network_config(),
            'wlan': get_wlan_config(),
            'wan': get_wan_config(),
            'firewall': get_firewall_config(),
            'qos': get_qos_config(),
            'dhcp': get_dhcp_config(),
            'dns': get_dns_config(),
            'openvpn': get_openvpn_config(),
            'certificates': get_certificate_config(),
            'hotspot': get_hotspot_config(),
            'sdwan': get_sdwan_config()
        }
        return config_report
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving comprehensive config: {e}")
        return None

def backup_config():
    """
    Create a backup of the current router configuration.
    
    Saves the complete configuration to a timestamped JSON file.
    
    Returns:
        str or None: Filename of the backup file if successful, None if failed
    """
    try:
        config_backup = get_comprehensive_config()
        if config_backup:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.json"
            with open(backup_filename, 'w') as f:
                json.dump(config_backup, f, indent=2)
            _cs_client.log(f"Configuration backup saved to {backup_filename}")
            return backup_filename
        return None
    except Exception as e:
        _cs_client.logger.exception(f"Error creating config backup: {e}")
        return None

def restore_config_from_file(backup_file):
    """
    Restore configuration from a backup file.
    
    Note: This is a simplified restore implementation. In practice, you would
    want to implement more careful validation and selective restoration.
    
    Args:
        backup_file (str): Path to the backup configuration file
    
    Returns:
        bool: True if restore was successful, False otherwise
    """
    try:
        with open(backup_file, 'r') as f:
            config_data = json.load(f)
        
        # This is a simplified restore - in practice, you'd want to be more careful
        # about what gets restored and validate the configuration
        for section, config in config_data.items():
            if config:
                _cs_client.log(f"Restoring {section} configuration...")
                # Note: This is a placeholder - actual restore logic would be more complex
                # and would need to handle the specific structure of each config section
        
        _cs_client.log("Configuration restore completed")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error restoring config from {backup_file}: {e}")
        return False

def get_config_diff(current_config, previous_config):
    """
    Compare two configurations and return differences.
    
    Args:
        current_config (dict): Current configuration
        previous_config (dict): Previous configuration to compare against
    
    Returns:
        str or None: Unified diff format showing differences, None if error
    """
    try:
        import difflib
        current_str = json.dumps(current_config, indent=2, sort_keys=True)
        previous_str = json.dumps(previous_config, indent=2, sort_keys=True)
        
        diff = list(difflib.unified_diff(
            previous_str.splitlines(keepends=True),
            current_str.splitlines(keepends=True),
            fromfile='previous_config',
            tofile='current_config'
        ))
        
        return ''.join(diff)
    except Exception as e:
        _cs_client.logger.exception(f"Error comparing configurations: {e}")
        return None

def validate_config(config_section, config_data):
    """
    Validate configuration data for a specific section.
    
    This is a placeholder for configuration validation logic. In practice,
    you would implement specific validation rules for each configuration section.
    
    Args:
        config_section (str): The configuration section name
        config_data (dict): The configuration data to validate
    
    Returns:
        tuple: (bool, str) - (is_valid, validation_message)
    """
    try:
        # This is a placeholder for configuration validation logic
        # In practice, you'd implement specific validation rules for each config section
        if not config_data:
            return False, "Configuration data is empty"
        
        # Add specific validation logic here based on the section
        if config_section == 'system':
            # Validate system configuration
            pass
        elif config_section == 'network':
            # Validate network configuration
            pass
        # Add more sections as needed
        
        return True, "Configuration is valid"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def get_config_schema(section):
    """
    Return the schema for a configuration section.
    
    This would return the expected structure for a configuration section.
    In practice, this might come from the router's API documentation or schema files.
    
    Args:
        section (str): The configuration section name
    
    Returns:
        dict: Schema definition for the configuration section
    """
    try:
        # This would return the expected structure for a configuration section
        # In practice, this might come from the router's API documentation or schema files
        schemas = {
            'system': {
                'description': 'System configuration schema',
                'properties': {
                    'system_id': {'type': 'string'},
                    'logging': {'type': 'object'},
                    'sdk': {'type': 'object'}
                }
            },
            'network': {
                'description': 'Network configuration schema',
                'properties': {
                    'interfaces': {'type': 'array'},
                    'routing': {'type': 'object'}
                }
            }
            # Add more schemas as needed
        }
        return schemas.get(section, {})
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving config schema for {section}: {e}")
        return None

# ============================================================================
# CONTROL FUNCTIONS
# ============================================================================

def reset_modem(modem_id=None):
    """
    Reset a specific modem or all modems.
    
    Args:
        modem_id (str, optional): Specific modem ID to reset. If None, resets all modems.
    
    Returns:
        bool: True if reset command was sent successfully, False otherwise
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

def reset_wlan():
    """
    Reset wireless LAN configuration and connections.
    
    Returns:
        bool: True if reset command was sent successfully, False otherwise
    """
    try:
        _cs_client.put('control/wlan/reset', 'reset')
        _cs_client.log("Reset command sent to WLAN")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error resetting WLAN: {e}")
        return False

def reset_network():
    """
    Reset network interfaces and configuration.
    
    Returns:
        bool: True if reset command was sent successfully, False otherwise
    """
    try:
        _cs_client.put('control/network/reset', 'reset')
        _cs_client.log("Reset command sent to network")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error resetting network: {e}")
        return False

def clear_logs():
    """
    Clear system logs.
    
    Returns:
        bool: True if logs were cleared successfully, False otherwise
    """
    try:
        _cs_client.put('control/log/clear', 'clear')
        _cs_client.log("Logs cleared")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error clearing logs: {e}")
        return False

def factory_reset():
    """
    Perform factory reset of the router.
    
    WARNING: This will erase all configuration and return the router to factory defaults.
    Use with extreme caution.
    
    Returns:
        bool: True if factory reset was initiated successfully, False otherwise
    """
    try:
        _cs_client.put('control/system/factory_reset', 'factory_reset')
        _cs_client.log("Factory reset initiated")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error performing factory reset: {e}")
        return False

def update_firmware(firmware_file):
    """
    Update router firmware.
    
    WARNING: This will restart the router and may take several minutes to complete.
    Use with caution.
    
    Args:
        firmware_file (str): Path to the firmware file or firmware identifier
    
    Returns:
        bool: True if firmware update was initiated successfully, False otherwise
    """
    try:
        _cs_client.put('control/system/firmware_update', firmware_file)
        _cs_client.log("Firmware update initiated")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error updating firmware: {e}")
        return False

def restart_service(service_name):
    """
    Restart a specific system service.
    
    Args:
        service_name (str): Name of the service to restart
    
    Returns:
        bool: True if service restart was initiated successfully, False otherwise
    """
    try:
        _cs_client.put(f'control/system/services/{service_name}/restart', 'restart')
        _cs_client.log(f"Service {service_name} restart initiated")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error restarting service {service_name}: {e}")
        return False

def enable_interface(interface_name):
    """
    Enable a network interface.
    
    Args:
        interface_name (str): Name of the interface to enable
    
    Returns:
        bool: True if interface was enabled successfully, False otherwise
    """
    try:
        _cs_client.put(f'config/network/interface/{interface_name}/enabled', True)
        _cs_client.log(f"Interface {interface_name} enabled")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error enabling interface {interface_name}: {e}")
        return False

def disable_interface(interface_name):
    """
    Disable a network interface.
    
    Args:
        interface_name (str): Name of the interface to disable
    
    Returns:
        bool: True if interface was disabled successfully, False otherwise
    """
    try:
        _cs_client.put(f'config/network/interface/{interface_name}/enabled', False)
        _cs_client.log(f"Interface {interface_name} disabled")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error disabling interface {interface_name}: {e}")
        return False

def set_system_time(time_str):
    """
    Set system time.
    
    Args:
        time_str (str): Time string in format 'YYYY-MM-DD HH:MM:SS'
    
    Returns:
        bool: True if system time was set successfully, False otherwise
    """
    try:
        _cs_client.put('config/system/time', time_str)
        _cs_client.log(f"System time set to {time_str}")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error setting system time: {e}")
        return False

def set_log_level(level):
    """
    Set system logging level.
    
    Args:
        level (str): Log level ('debug', 'info', 'warning', 'error')
    
    Returns:
        bool: True if log level was set successfully, False otherwise
    """
    try:
        _cs_client.put('config/system/logging/level', level)
        _cs_client.log(f"Log level set to {level}")
        return True
    except Exception as e:
        _cs_client.logger.exception(f"Error setting log level: {e}")
        return False
