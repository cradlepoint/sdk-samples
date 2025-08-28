"""
NCOS communication module for SDK applications.

Copyright (c) 2025 Ericsson Enterprise Wireless Solutions <www.cradlepoint.com>.  All rights reserved.

This file contains confidential information of Ericsson Enterprise Wireless Solutions and your use of
this file is subject to the Ericsson Enterprise Wireless Solutions Software License Agreement distributed with
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
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

try:
    import traceback
except ImportError:
    traceback = None


class SdkCSException(Exception):
    """Custom exception for SDK communication errors."""
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
    def is_initialized(cls) -> bool:
        """Checks if the singleton instance has been created."""
        return cls in cls._instances

    def __new__(cls, *na: Any, **kwna: Any) -> 'CSClient':
        """Singleton factory (with subclassing support)."""
        if not cls.is_initialized():
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def __init__(self, app_name: str, init: bool = False) -> None:
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

    def get(self, base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
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

    def decrypt(self, base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
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

    def put(self, base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
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

    def post(self, base: str, value: Any = '', query: str = '') -> Optional[Dict[str, Any]]:
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

    def patch(self, value: List[Any]) -> Optional[Dict[str, Any]]:
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

    def delete(self, base: str, query: str = '') -> Optional[Dict[str, Any]]:
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

    def alert(self, value: str = '') -> Optional[Dict[str, Any]]:
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

    def log(self, value: str = '') -> None:
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
        elif self.ncos:
            # Running in Linux (container?) so write to stdout
            with open('/dev/stdout', 'w') as log:
                log.write(f'{self.app_name}: {value}\n')
        else:
            # Running in a computer so just use print for the log.
            print(value)


    def _get_auth(self, device_ip: str, username: str, password: str) -> Any:
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
    def _get_device_access_info() -> Tuple[str, str, str]:
        """
        Returns device access info from the sdk_settings.ini file.
        
        This should only be called when running on a computer.
        """
        try:
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
        except Exception as e:
            print(f"Error getting device access info: {e}")
            return '', '', ''

    def _safe_dispatch(self, cmd: str) -> Dict[str, Any]:
        """Send the command and return the response."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect('/var/tmp/cs.sock')
                sock.sendall(bytes(cmd, 'ascii'))
                return self._receive(sock)
        except Exception as e:
            self.log(f"Error in safe dispatch: {e}")
            return {"status": "error", "data": str(e)}

    def _dispatch(self, cmd: str) -> Dict[str, Any]:
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

    def _safe_receive(self, sock: socket.socket) -> Dict[str, Any]:
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

    def _receive(self, sock: socket.socket) -> Dict[str, Any]:
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

    def __init__(self, app_name: str, init: bool = True) -> None:
        """Initializes the EventingCSClient and sets up aliases for register/unregister."""
        super().__init__(app_name, init)
        self.on = self.register
        self.un = self.unregister

    def start(self) -> None:
        """Starts the event handling loop in a separate thread."""
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
        """Stops the event handling loop and cleans up resources."""
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

    def register(self, action: str = 'set', path: str = '', callback: Callable = None, *args: Any) -> Dict[str, Any]:
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

    # ============================================================================
    # GRANULAR STATUS GET METHODS
    # ============================================================================
    
    def get_gps_status(self) -> Dict[str, Any]:
        """Get GPS status and return detailed information with decimal coordinates"""
        try:
            gps_data = self.get('status/gps')
            if not gps_data:
                return {"has_gps_data": False, "gps_lock": False, "satellites": 0}
            
            analysis = {
                "has_gps_data": True,
                "gps_lock": False,
                "satellites": 0,
                "location": None,
                "decimal_coordinates": None,
                "altitude": None,
                "speed": None,
                "heading": None,
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
                    "last_fix_age": fix.get("age")
                })
                
                if fix.get("latitude") and fix.get("longitude"):
                    analysis["location"] = {
                        "latitude": f"{fix['latitude']['degree']}°{fix['latitude']['minute']}'{fix['latitude']['second']}\"",
                        "longitude": f"{fix['longitude']['degree']}°{fix['longitude']['minute']}'{fix['longitude']['second']}\""
                    }
                    
                    # Add decimal coordinates using the dec function
                    try:
                        lat_deg = fix['latitude']['degree']
                        lat_min = fix['latitude']['minute']
                        lat_sec = fix['latitude']['second']
                        long_deg = fix['longitude']['degree']
                        long_min = fix['longitude']['minute']
                        long_sec = fix['longitude']['second']
                        
                        # Import dec function from the module level
                        from . import dec
                        
                        decimal_lat = dec(lat_deg, lat_min, lat_sec)
                        decimal_long = dec(long_deg, long_min, long_sec)
                        
                        analysis["decimal_coordinates"] = {
                            "latitude": decimal_lat,
                            "longitude": decimal_long
                        }
                    except Exception as coord_error:
                        self.log(f"Error converting coordinates to decimal: {coord_error}")
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing GPS status: {e}")
            return {"has_gps_data": False, "error": str(e)}

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and return detailed information"""
        try:
            system_data = self.get('status/system')
            if not system_data:
                return {"has_system_data": False}
            
            analysis = {
                "has_system_data": True,
                "uptime": system_data.get("uptime"),
                "temperature": system_data.get("temperature"),
                "storage_health": system_data.get("storage", {}).get("health"),
                "cpu_usage": system_data.get("cpu", {}),
                "memory_usage": system_data.get("memory", {}),
                "services_running": 0,
                "services_disabled": 0,
                "apps_running": 0
            }
            
            services = system_data.get("services", {})
            for service, info in services.items():
                if isinstance(info, dict) and info.get("state") == "started":
                    analysis["services_running"] += 1
                elif isinstance(info, dict) and info.get("state") == "disabled":
                    analysis["services_disabled"] += 1
            
            apps = system_data.get("apps", [])
            analysis["apps_running"] = len([app for app in apps if app.get("state") == "started"])
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing system status: {e}")
            return {"has_system_data": False, "error": str(e)}

    def get_wlan_status(self) -> Dict[str, Any]:
        """Get WLAN status and return detailed information"""
        try:
            wlan_data = self.get('status/wlan')
            if not wlan_data:
                return {"has_wlan_data": False}
            
            analysis = {
                "has_wlan_data": True,
                "wlan_state": wlan_data.get("state"),
                "radios": [],
                "clients_connected": 0,
                "interfaces": []
            }
            
            radios = wlan_data.get("radio", [])
            for i, radio in enumerate(radios):
                radio_info = {
                    "radio_id": i,
                    "survey_data": len(radio.get("survey", [])),
                    "has_survey": bool(radio.get("survey"))
                }
                analysis["radios"].append(radio_info)
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing WLAN status: {e}")
            return {"has_wlan_data": False, "error": str(e)}

    def get_wan_status(self) -> Dict[str, Any]:
        """Get WAN status and return detailed information"""
        try:
            wan_data = self.get('status/wan')
            if not wan_data:
                return {"has_wan_data": False}
            
            analysis = {
                "has_wan_data": True,
                "primary_device": wan_data.get("primary_device"),
                "connection_state": None,
                "devices": []
            }
            
            devices = wan_data.get("devices", {})
            for device_id, device_info in devices.items():
                device_analysis = {
                    "device_id": device_id,
                    "connection_state": device_info.get("status", {}).get("connection_state"),
                    "signal_strength": device_info.get("status", {}).get("signal_strength"),
                    "cellular_health": device_info.get("status", {}).get("cellular_health_category"),
                    "ip_address": device_info.get("status", {}).get("ipinfo", {}).get("ip_address")
                }
                analysis["devices"].append(device_analysis)
                
                # Set connection state from first device
                if analysis["connection_state"] is None:
                    analysis["connection_state"] = device_analysis["connection_state"]
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing WAN status: {e}")
            return {"has_wan_data": False, "error": str(e)}

    def get_lan_status(self) -> Dict[str, Any]:
        """Get LAN status and return detailed information"""
        try:
            lan_data = self.get('status/lan')
            if not lan_data:
                return {"has_lan_data": False}
            
            analysis = {
                "has_lan_data": True,
                "clients_connected": len(lan_data.get("clients", [])),
                "networks": [],
                "devices": []
            }
            
            networks = lan_data.get("networks", {})
            for network_name, network_info in networks.items():
                network_analysis = {
                    "name": network_name,
                    "ip_address": network_info.get("info", {}).get("ip_address"),
                    "netmask": network_info.get("info", {}).get("netmask"),
                    "device_count": len(network_info.get("devices", []))
                }
                analysis["networks"].append(network_analysis)
            
            devices = lan_data.get("devices", {})
            for device_name, device_info in devices.items():
                device_analysis = {
                    "name": device_name,
                    "interface": device_info.get("info", {}).get("iface"),
                    "link_state": device_info.get("status", {}).get("link_state"),
                    "type": device_info.get("info", {}).get("type")
                }
                analysis["devices"].append(device_analysis)
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing LAN status: {e}")
            return {"has_lan_data": False, "error": str(e)}

    def get_openvpn_status(self) -> Dict[str, Any]:
        """Get OpenVPN status and return detailed information"""
        try:
            openvpn_data = self.get('status/openvpn')
            if not openvpn_data:
                return {"has_openvpn_data": False}
            
            analysis = {
                "has_openvpn_data": True,
                "tunnels_configured": len(openvpn_data.get("tunnels", [])),
                "tunnels_active": len([t for t in openvpn_data.get("tunnels", []) if t.get("status") == "up"]),
                "stats_available": bool(openvpn_data.get("stats"))
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing OpenVPN status: {e}")
            return {"has_openvpn_data": False, "error": str(e)}

    def get_hotspot_status(self) -> Dict[str, Any]:
        """Get hotspot status and return detailed information"""
        try:
            hotspot_data = self.get('status/hotspot')
            if not hotspot_data:
                return {"has_hotspot_data": False}
            
            analysis = {
                "has_hotspot_data": True,
                "clients_connected": len(hotspot_data.get("clients", {})),
                "sessions_active": len(hotspot_data.get("sessions", {})),
                "domains_allowed": len(hotspot_data.get("allowed", {}).get("domains", [])),
                "hosts_allowed": len(hotspot_data.get("allowed", {}).get("hosts", {})),
                "rate_limit_triggered": hotspot_data.get("rateLimitTrigger", False)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing hotspot status: {e}")
            return {"has_hotspot_data": False, "error": str(e)}

    def get_obd_status(self) -> Dict[str, Any]:
        """Get OBD status and return detailed information"""
        try:
            obd_data = self.get('status/obd')
            if not obd_data:
                return {"has_obd_data": False}
            
            adapter = obd_data.get("adapter", {})
            vehicle = obd_data.get("vehicle", {})
            
            analysis = {
                "has_obd_data": True,
                "adapter_configured": adapter.get("configured", False),
                "adapter_connected": adapter.get("connected", False),
                "vehicle_connected": vehicle.get("ext_tool") != "Disconnected",
                "pids_supported": len([pid for pid in obd_data.get("pids", []) if pid.get("supported", False)]),
                "pids_enabled": len([pid for pid in obd_data.get("pids", []) if pid.get("enabled", False)]),
                "ignition_status": vehicle.get("ign_status")
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing OBD status: {e}")
            return {"has_obd_data": False, "error": str(e)}

    def get_qos_status(self) -> Dict[str, Any]:
        """Get QoS status and return detailed information"""
        try:
            qos_data = self.get('status/qos')
            if not qos_data:
                return {"has_qos_data": False}
            
            queues = qos_data.get("queues", [])
            analysis = {
                "has_qos_data": True,
                "qos_enabled": qos_data.get("enabled", False),
                "queues_configured": len(queues),
                "queues_active": len([q for q in queues if q.get("ipkts", 0) > 0 or q.get("opkts", 0) > 0]),
                "total_packets": sum(q.get("ipkts", 0) + q.get("opkts", 0) for q in queues)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing QoS status: {e}")
            return {"has_qos_data": False, "error": str(e)}

    def get_firewall_status(self) -> Dict[str, Any]:
        """Get firewall status and return detailed information"""
        try:
            firewall_data = self.get('status/firewall')
            if not firewall_data:
                return {"has_firewall_data": False}
            
            connections = firewall_data.get("connections", [])
            hitcounters = firewall_data.get("hitcounter", [])
            
            analysis = {
                "has_firewall_data": True,
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
            return {"has_firewall_data": False, "error": str(e)}

    def get_dns_status(self) -> Dict[str, Any]:
        """Get DNS status and return detailed information"""
        try:
            dns_data = self.get('status/dns')
            if not dns_data:
                return {"has_dns_data": False}
            
            cache = dns_data.get("cache", {})
            servers = cache.get("servers", [])
            
            analysis = {
                "has_dns_data": True,
                "cache_entries": len(cache.get("entries", [])),
                "cache_size": cache.get("size", 0),
                "servers_configured": len(servers),
                "queries_forwarded": cache.get("forwarded", 0)
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing DNS status: {e}")
            return {"has_dns_data": False, "error": str(e)}

    def get_dhcp_status(self) -> Dict[str, Any]:
        """Get DHCP status and return detailed information"""
        try:
            dhcp_data = self.get('status/dhcp')
            if not dhcp_data:
                return {"has_dhcp_data": False}
            
            devices = list(dhcp_data.keys())
            analysis = {
                "has_dhcp_data": True,
                "devices_configured": len(devices),
                "devices_with_ip": len([d for d in devices if dhcp_data[d].get("ipinfo", {}).get("ip_address")])
            }
            
            return analysis
        except Exception as e:
            self.log(f"Error analyzing DHCP status: {e}")
            return {"has_dhcp_data": False, "error": str(e)}



def _get_app_name() -> str:
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
    except Exception as e:
        print(f"Error getting app name from package.ini: {e}")
        return 'SDK'

# Create a single EventingCSClient instance with name from package.ini
_cs_client = EventingCSClient(_get_app_name())

def get_uptime() -> int:
    """Return the router uptime in seconds."""
    try:
        uptime = int(_cs_client.get('status/system/uptime'))
        return uptime
    except Exception as e:
        _cs_client.log(f"Error getting uptime: {e}")
        return 0

def wait_for_uptime(min_uptime_seconds: int = 60) -> None:
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

def wait_for_ntp(timeout: int = 300, check_interval: int = 1) -> bool:
    """
    Wait until NTP sync age is not null, indicating NTP synchronization.
    
    Args:
        timeout (int): Maximum time to wait in seconds (default: 300)
        check_interval (int): Time between checks in seconds (default: 1)
    
    Returns:
        bool: True if NTP sync was achieved within timeout, False otherwise
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
    """Waits for at least one WAN connection to be 'connected'.
    Returns True if a connection is established within the timeout, otherwise False."""
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
    """Get value of appdata from NCOS Config by name."""
    try:
        appdata = _cs_client.get('config/system/sdk/appdata')
        return next(iter(x["value"] for x in appdata if x["name"] == name), None)
    except Exception as e:
        _cs_client.log(f"Error getting appdata for {name}: {e}")
        return None

def post_appdata(name: str = '', value: str = '') -> None:
    """Create appdata in NCOS Config by name."""
    try:
        _cs_client.post('config/system/sdk/appdata', {"name": name, "value": value})
    except Exception as e:
        _cs_client.log(f"Error posting appdata for {name}: {e}")

def put_appdata(name: str = '', value: str = '') -> None:
    """Set value of appdata in NCOS Config by name."""
    try:
        appdata = _cs_client.get('config/system/sdk/appdata')
        for item in appdata:
            if item["name"] == name:
                _cs_client.put(f'config/system/sdk/appdata/{item["_id_"]}/value', value)
    except Exception as e:
        _cs_client.log(f"Error putting appdata for {name}: {e}")

def delete_appdata(name: str = '') -> None:
    """Delete appdata in NCOS Config by name."""
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

def extract_cert_and_key(cert_name_or_uuid: str = '') -> Tuple[Optional[str], Optional[str]]:
    """Extract and save the certificate and key to the local filesystem. Returns the filenames of the certificate and key files."""
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
    """Return a list of IPv4 wired clients and their details."""
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
    """Return a list of IPv4 Wi-Fi clients and their details."""
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
        return {"wired_clients": [], "wifi_clients": []}

def dec(deg: float, min: float = 0.0, sec: float = 0.0) -> float:
    """Return decimal version of lat or long from deg, min, sec"""
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
    """Return latitude and longitude as floats"""
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
    """Return list of connected WAN UIDs"""
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
    """Return list of modem UIDs with SIMs"""
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
    """Return the device MAC address without colons"""
    try:
        mac = _cs_client.get('status/product_info/mac0')
        if not mac:
            return None
        return mac if format_with_colons else mac.replace(':', '')
    except Exception as e:
        _cs_client.log(f"Error getting device MAC: {e}")
        return None

def get_device_serial_num() -> Optional[str]:
    """Return the device serial number"""
    try:
        return _cs_client.get('status/product_info/manufacturing/serial_num')
    except Exception as e:
        _cs_client.log(f"Error getting device serial number: {e}")
        return None

def get_device_product_type() -> Optional[str]:
    """Return the device product type"""
    try:
        return _cs_client.get('status/product_info/manufacturing/product_name')
    except Exception as e:
        _cs_client.log(f"Error getting device product type: {e}")
        return None

def get_device_name() -> Optional[str]:
    """Return the device name"""
    try:
        return _cs_client.get('config/system/system_id')
    except Exception as e:
        _cs_client.log(f"Error getting device name: {e}")
        return None

def get_device_firmware(include_build_info: bool = False) -> str:
    """Return the device firmware information"""
    try:
        fw_info = _cs_client.get('status/fw_info')
        firmware = f"{fw_info.get('major')}.{fw_info.get('minor')}.{fw_info.get('patch')}-{fw_info.get('fw_release_tag')}"
        
        if include_build_info:
            build_info = fw_info.get('build_info', '')
            if build_info:
                firmware += f" ({build_info})"
        
        return firmware
    except Exception as e:
        _cs_client.log(f"Error getting device firmware: {e}")
        return "Unknown"

def get_system_resources(cpu: bool = True, memory: bool = True, storage: bool = False) -> Dict[str, str]:
    """Return a dictionary containing the system resources"""
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

def get_ncm_status(include_details: bool = False) -> Optional[str]:
    """Return the NCM status"""
    try:
        return _cs_client.get('status/ecm/state')
    except Exception as e:
        _cs_client.log(f"Error getting NCM status: {e}")
        return None

def reboot_device(force: bool = False) -> None:
    """Reboot the device"""
    try:
        _cs_client.put('control/system/reboot', 'reboot hypmgr')
    except Exception as e:
        _cs_client.log(f"Error rebooting device: {e}")
    
# Direct access to the underlying EventingCSClient methods
def get(base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying get method."""
    try:
        return _cs_client.get(base, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in get request for {base}: {e}")
        return None

def post(base: str, value: Any = '', query: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying post method."""
    try:
        return _cs_client.post(base, value, query)
    except Exception as e:
        _cs_client.log(f"Error in post request for {base}: {e}")
        return None

def put(base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying put method."""
    try:
        return _cs_client.put(base, value, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in put request for {base}: {e}")
        return None

def delete(base: str, query: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying delete method."""
    try:
        return _cs_client.delete(base, query)
    except Exception as e:
        _cs_client.log(f"Error in delete request for {base}: {e}")
        return None

def decrypt(base: str, query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """Direct access to the underlying decrypt method."""
    try:
        return _cs_client.decrypt(base, query, tree)
    except Exception as e:
        _cs_client.log(f"Error in decrypt request for {base}: {e}")
        return None

def log(value: str = '') -> None:
    """Direct access to the underlying log method."""
    try:
        return _cs_client.log(value)
    except Exception as e:
        print(f"Error in log request: {e}")

def alert(value: str = '') -> Optional[Dict[str, Any]]:
    """Direct access to the underlying alert method."""
    try:
        return _cs_client.alert(value)
    except Exception as e:
        _cs_client.log(f"Error in alert request: {e}")
        return None

def register(action: str = 'set', path: str = '', callback: Callable = None, *args: Any) -> Dict[str, Any]:
    """Registers a callback for a config store event."""
    try:
        return _cs_client.register(action, path, callback, *args)
    except Exception as e:
        _cs_client.log(f"Error in register request for {path}: {e}")
        return {}

# Alias for register function
on = register

def unregister(eid: int = 0) -> Dict[str, Any]:
    """Unregisters a callback by its event ID."""
    try:
        return _cs_client.unregister(eid)
    except Exception as e:
        _cs_client.log(f"Error in unregister request for eid {eid}: {e}")
        return {}

# Expose the logger for advanced logging control
def get_logger() -> Any:
    """Get the logger instance for advanced logging control."""
    try:
        return _cs_client.logger
    except Exception as e:
        print(f"Error getting logger: {e}")
        return None

# Monkay patch for cp.uptime()
def uptime() -> float:
    try:
        return time.time()
    except Exception as e:
        print(f"Error getting uptime: {e}")
        return 0.0
    
def clean_up_reg(signal: Any, frame: Any) -> None:
    """
    When 'cppython remote_port_forward.py' gets a SIGTERM, config_store_receiver.py doesn't
    clean up registrations. Even if it did, the comm module can't rely on an external service
    to clean up.
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
    """Get GPS status and return detailed information"""
    return _cs_client.get_gps_status()

def get_system_status() -> Dict[str, Any]:
    """Get system status and return detailed information"""
    return _cs_client.get_system_status()

def get_wlan_status() -> Dict[str, Any]:
    """Get WLAN status and return detailed information"""
    return _cs_client.get_wlan_status()

def get_wan_status() -> Dict[str, Any]:
    """Get WAN status and return detailed information"""
    return _cs_client.get_wan_status()

def get_lan_status() -> Dict[str, Any]:
    """Get LAN status and return detailed information"""
    return _cs_client.get_lan_status()

def get_openvpn_status() -> Dict[str, Any]:
    """Get OpenVPN status and return detailed information"""
    return _cs_client.get_openvpn_status()

def get_hotspot_status() -> Dict[str, Any]:
    """Get hotspot status and return detailed information"""
    return _cs_client.get_hotspot_status()

def get_obd_status() -> Dict[str, Any]:
    """Get OBD status and return detailed information"""
    return _cs_client.get_obd_status()

def get_qos_status() -> Dict[str, Any]:
    """Get QoS status and return detailed information"""
    return _cs_client.get_qos_status()

def get_firewall_status() -> Dict[str, Any]:
    """Get firewall status and return detailed information"""
    return _cs_client.get_firewall_status()

def get_dns_status() -> Dict[str, Any]:
    """Get DNS status and return detailed information"""
    return _cs_client.get_dns_status()

def get_dhcp_status() -> Dict[str, Any]:
    """Get DHCP status and return detailed information"""
    return _cs_client.get_dhcp_status()

# ============================================================================
# STATUS MONITORING FUNCTIONS
# ============================================================================

def get_wan_devices_status() -> Optional[Dict[str, Any]]:
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

def get_modem_status() -> Optional[Dict[str, Any]]:
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

def get_signal_strength() -> Optional[Dict[str, Any]]:
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

def get_temperature(unit: str = 'celsius') -> Optional[float]:
    """Return device temperature information"""
    try:
        # Temperature is a direct value, not a directory
        temp = _cs_client.get('status/system/temperature')
        if temp is None:
            return None
        
        # Convert to Fahrenheit if requested
        if unit.lower() == 'fahrenheit':
            return (temp * 9/5) + 32
        return temp
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving temperature: {e}")
        return None

def get_power_usage(include_components: bool = True) -> Optional[Dict[str, Any]]:
    """Return power usage information"""
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

def get_wlan_clients() -> List[Dict[str, Any]]:
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

def get_wlan_radio_status() -> List[Dict[str, Any]]:
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

def get_wlan_radio_by_band(band: str = '2.4 GHz') -> Optional[Dict[str, Any]]:
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

def get_wlan_events() -> Dict[str, Any]:
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

def get_wlan_region_config() -> Dict[str, Any]:
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

def get_wlan_remote_status() -> Dict[str, Any]:
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

def get_wlan_state() -> str:
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

def get_wlan_trace() -> List[Dict[str, Any]]:
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

def get_wlan_debug() -> Dict[str, Any]:
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

def get_wlan_channel_info(band: Optional[str] = None, include_survey: bool = False) -> Dict[str, Any]:
    """
    Return wireless LAN channel information for specified band or all bands.
    
    Args:
        band (str, optional): Frequency band ('2.4 GHz' or '5 GHz'). If None, returns all bands.
        include_survey (bool, optional): Include channel survey data. Default is False.
    
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

def get_wlan_client_count_by_band() -> Dict[str, int]:
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

def get_dhcp_leases() -> Optional[List[Dict[str, Any]]]:
    """Return DHCP lease information"""
    try:
        leases = _cs_client.get('status/dhcpd/leases')
        return leases
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving DHCP leases: {e}")
        return None

def get_network_interfaces() -> Optional[Dict[str, Any]]:
    """Return network interface status"""
    try:
        interfaces = _cs_client.get('status/network')
        return interfaces
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving network interfaces: {e}")
        return None

def get_routing_table() -> Optional[Dict[str, Any]]:
    """Return routing table information"""
    try:
        routes = _cs_client.get('status/routing')
        return routes
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving routing table: {e}")
        return None

def get_certificate_status() -> Optional[Dict[str, Any]]:
    """Return certificate management status"""
    try:
        cert_status = _cs_client.get('status/certmgmt')
        return cert_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving certificate status: {e}")
        return None

def get_storage_status(include_detailed: bool = False) -> Optional[Dict[str, Any]]:
    """Return storage device status"""
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
    """Return USB device status"""
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
    """Return Power over Ethernet status"""
    try:
        # PoE directory appears to be empty on this router
        poe_status = _cs_client.get('status/system/poe_pse')
        return poe_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving PoE status: {e}")
        return None

def get_sensors_status() -> Optional[Dict[str, Any]]:
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

def get_services_status() -> Optional[Dict[str, Any]]:
    """Return system services status"""
    try:
        services_status = _cs_client.get('status/system/services')
        return services_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving services status: {e}")
        return None

def get_apps_status() -> Optional[List[Dict[str, Any]]]:
    """Return SDK applications status"""
    try:
        apps_status = _cs_client.get('status/system/apps')
        return apps_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving apps status: {e}")
        return None

def get_log_status() -> Optional[Dict[str, Any]]:
    """Return system log status"""
    try:
        # Log directory appears to be empty
        log_status = _cs_client.get('status/log')
        return log_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving log status: {e}")
        return None

def get_event_status() -> Optional[Dict[str, Any]]:
    """Return system events status"""
    try:
        event_status = _cs_client.get('status/event')
        return event_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving event status: {e}")
        return None

def get_network_throughput() -> Optional[Dict[str, Any]]:
    """Return network throughput statistics"""
    try:
        stats = _cs_client.get('status/stats')
        return stats
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving network throughput: {e}")
        return None

def get_flow_statistics() -> Optional[Dict[str, Any]]:
    """Return flow statistics"""
    try:
        flow_stats = _cs_client.get('status/flowstats')
        return flow_stats
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving flow statistics: {e}")
        return None

def get_client_usage() -> Optional[Dict[str, Any]]:
    """Return client usage statistics"""
    try:
        client_usage = _cs_client.get('status/client_usage')
        return client_usage
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving client usage: {e}")
        return None

def get_multicast_status() -> Optional[Dict[str, Any]]:
    """Return multicast status"""
    try:
        multicast_status = _cs_client.get('status/multicast')
        return multicast_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving multicast status: {e}")
        return None

def get_vpn_status() -> Optional[Dict[str, Any]]:
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

def get_security_status() -> Optional[Dict[str, Any]]:
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

def get_iot_status() -> Optional[Dict[str, Any]]:
    """Return IoT-related status"""
    try:
        iot_status = _cs_client.get('status/iot')
        return iot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving IoT status: {e}")
        return None

def get_obd_status() -> Optional[Dict[str, Any]]:
    """Return OBD (On-Board Diagnostics) status"""
    try:
        obd_status = _cs_client.get('status/obd')
        return obd_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving OBD status: {e}")
        return None

def get_hotspot_status() -> Optional[Dict[str, Any]]:
    """Return hotspot status"""
    try:
        hotspot_status = _cs_client.get('status/hotspot')
        return hotspot_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving hotspot status: {e}")
        return None

def get_sdwan_status() -> Optional[Dict[str, Any]]:
    """Return SD-WAN status"""
    try:
        sdwan_status = _cs_client.get('status/sdwan_adv')
        return sdwan_status
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving SD-WAN status: {e}")
        return None

def get_comprehensive_status(include_detailed: bool = True, include_clients: bool = True) -> Optional[Dict[str, Any]]:
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
                'network_interfaces': get_network_interfaces(),
                'flow_statistics': get_flow_statistics(),
                'client_usage': get_client_usage(),
                'multicast': get_multicast_status(),
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
    """Wait for modem to establish a connection"""
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
    """Wait for GPS to acquire a fix"""
    try:
        _cs_client.log("Waiting for GPS fix...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            gps_status = get_gps_status()
            if gps_status and gps_status.get('fix', {}).get('lock'):
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
    """
    Reset a specific modem or all modems.
    
    Args:
        modem_id (str, optional): Specific modem ID to reset. If None, resets all modems.
        force (bool, optional): Force reset even if modem is connected. Default is False.
    
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

def reset_wlan(force: bool = False) -> bool:
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

def clear_logs() -> bool:
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

def factory_reset() -> bool:
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

def restart_service(service_name: str, force: bool = False) -> bool:
    """
    Restart a specific system service.
    
    Args:
        service_name (str): Name of the service to restart
        force (bool, optional): Force restart even if service is critical. Default is False.
    
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

def set_log_level(level: str = 'info') -> bool:
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

# ============================================================================
# GRANULAR HELPER FUNCTIONS - QoS
# ============================================================================

def get_qos_queues() -> List[Dict[str, Any]]:
    """
    Return detailed QoS queue information.
    
    Returns:
        list: List of QoS queues with detailed statistics
    """
    try:
        qos_data = _cs_client.get('status/qos')
        return qos_data.get('queues', []) if qos_data else []
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving QoS queues: {e}")
        return []

def get_qos_queue_by_name(queue_name: str = '') -> Optional[Dict[str, Any]]:
    """
    Return specific QoS queue information by name.
    
    Args:
        queue_name (str): Name of the queue to retrieve
        
    Returns:
        dict: Queue information or None if not found
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
    """
    Return aggregated QoS traffic statistics.
    
    Returns:
        dict: Aggregated traffic statistics across all queues
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
    """
    Return DHCP leases for a specific interface.
    
    Args:
        interface_name (str): Interface name to filter by
        
    Returns:
        list: DHCP leases for the specified interface
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
    """
    Return DHCP leases for a specific network.
    
    Args:
        network_name (str): Network name to filter by
        
    Returns:
        list: DHCP leases for the specified network
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
    """
    Return DHCP lease for a specific MAC address.
    
    Args:
        mac_address (str): MAC address to search for
        
    Returns:
        dict: DHCP lease information or None if not found
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
    """
    Return DHCP lease for a specific IP address.
    
    Args:
        ip_address (str): IP address to search for
        
    Returns:
        dict: DHCP lease information or None if not found
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
    """
    Return summary of DHCP leases by interface.
    
    Returns:
        dict: Summary of DHCP leases organized by interface
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
    """
    Return BGP routing protocol status and neighbor information.
    
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
    """
    Return OSPF routing protocol status and neighbor information.
    
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
    """
    Return configured static routes.
    
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
    """
    Return routing policy configuration.
    
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
    """
    Return routes from a specific routing table.
    
    Args:
        table_name (str): Name of the routing table
        
    Returns:
        list: Routes in the specified table
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
    """
    Return ARP table information.
    
    Returns:
        str: ARP table dump showing MAC to IP mappings
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
    """
    Return summary of routing information.
    
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
    """
    Return list of installed certificates.
    
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
    """
    Return specific certificate information by name.
    
    Args:
        cert_name (str): Name of the certificate to retrieve
        
    Returns:
        dict: Certificate information or None if not found
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
    """
    Return specific certificate information by UUID.
    
    Args:
        cert_uuid (str): UUID of the certificate to retrieve
        
    Returns:
        dict: Certificate information or None if not found
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
    """
    Return certificates that will expire within the specified number of days.
    
    Args:
        days_threshold (int): Number of days to check for expiration
        
    Returns:
        list: Certificates expiring within the threshold
    """
    try:
        from datetime import datetime, timedelta
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
    """
    Return summary of certificate information.
    
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
    """
    Return active firewall connections and connection tracking information.
    
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
    """
    Return firewall rule hit counters and statistics.
    
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
    """
    Return firewall traffic marks and their values.
    
    Returns:
        dict: Dictionary of traffic marks and their hex values
    """
    try:
        firewall_data = _cs_client.get('status/firewall')
        return firewall_data.get('marks', {}) if firewall_data else {}
    except Exception as e:
        _cs_client.logger.exception(f"Error retrieving firewall marks: {e}")
        return {}

def get_firewall_state_timeouts() -> Dict[str, Any]:
    """
    Return firewall state timeout configurations.
    
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
    """
    Return firewall connections filtered by protocol.
    
    Args:
        protocol (int): Protocol number (6=TCP, 17=UDP, etc.)
        
    Returns:
        list: Connections for the specified protocol
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
    """
    Return firewall connections involving a specific IP address.
    
    Args:
        ip_address (str): IP address to search for
        
    Returns:
        list: Connections involving the specified IP
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
    """
    Return summary of firewall information.
    
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
