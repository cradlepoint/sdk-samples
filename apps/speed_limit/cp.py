"""
NCOS Communication Module (cp) (2026) - Cradlepoint SDK

A clean, module-level interface for communicating with NCOS routers.
Import and use directly without instantiation:

    import cp
    cp.log('Hello')
    data = cp.get('status/system/uptime')
    cp.alert('Something happened')
    cp.register('put', 'control/my/path', my_callback)

Features:
- Router config store communication (get/put/post/delete/patch/decrypt)
- Syslog logging that works correctly on router, in containers, and locally
- NCM alerts
- Event registration and callbacks
- Appdata management
- Device info helpers (GPS, WAN, LAN, WLAN, GPIO, etc.)
- Diagnostic tools (ping, traceroute, CLI execution)
- WAN profile management
- Signal strength monitoring

Copyright (c) 2026 Ericsson Enterprise Wireless Solutions <www.cradlepoint.com>.
All rights reserved.
"""

import base64
import configparser
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import re
import select
import signal as signal_module
import socket
import string
import sys
import threading
import time
import traceback as traceback_module
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import requests
except ImportError:
    requests = None


# =============================================================================
# INTERNAL: Environment Detection & Configuration
# =============================================================================

def _detect_ncos() -> bool:
    """Detect if running on an NCOS router by checking for cs.sock.

    Returns:
        bool: True if cs.sock is reachable (running on NCOS), False otherwise.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect('/var/tmp/cs.sock')
        return True
    except Exception:
        return False


def _get_app_name() -> str:
    """Get app name from the first section of package.ini.

    Returns:
        str: App name from package.ini, or 'SDK' if not found.
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(script_dir, 'package.ini')
        if os.path.exists(ini_path):
            config = configparser.ConfigParser()
            config.read(ini_path)
            sections = config.sections()
            if sections:
                return sections[0]
    except Exception:
        pass
    return 'SDK'


# Module-level state
_app_name = _get_app_name()
_is_ncos = _detect_ncos()
_enable_logging = '/mnt/sdk/' in os.getcwd()
_logger = None

# Initialize logger for syslog on router
if _is_ncos and _enable_logging:
    _handlers = [logging.handlers.SysLogHandler(address='/dev/log')]
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)s: %(message)s',
        datefmt='%b %d %H:%M:%S',
        handlers=_handlers
    )
    _logger = logging.getLogger(_app_name)

# Suppress noisy urllib3 logging
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)


# =============================================================================
# INTERNAL: Socket Communication (Router)
# =============================================================================

_END_OF_HEADER = b"\r\n\r\n"
_STATUS_HEADER_RE = re.compile(rb"status: \w*")
_CONTENT_LENGTH_HEADER_RE = re.compile(rb"content-length: \w*")
_MAX_PACKET_SIZE = 8192
_RECV_TIMEOUT = 2.0


def _sock_receive(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Receive and parse a response from the config store socket.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): Response status ('ok', 'error', 'timeout').
            - data (Any): Parsed JSON body or stripped string.
    """
    sock.settimeout(_RECV_TIMEOUT)
    data = b""
    eoh = -1

    while eoh < 0:
        try:
            buf = sock.recv(_MAX_PACKET_SIZE)
        except socket.timeout:
            return {"status": "timeout", "data": None}
        if not buf:
            break
        data += buf
        eoh = data.find(_END_OF_HEADER)

    if eoh < 0:
        return {"status": "error", "data": None}

    status_match = _STATUS_HEADER_RE.search(data)
    content_len_match = _CONTENT_LENGTH_HEADER_RE.search(data)

    if not status_match or not content_len_match:
        return {"status": "error", "data": None}

    status_hdr = status_match.group(0)[8:]
    content_len = int(content_len_match.group(0)[16:])
    remaining = content_len - (len(data) - eoh - len(_END_OF_HEADER))

    while remaining > 0:
        buf = sock.recv(_MAX_PACKET_SIZE)
        if not buf:
            break
        data += buf
        remaining -= len(buf)

    body = data[eoh:].decode()
    try:
        result = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        result = body.strip()

    return {"status": status_hdr.decode(), "data": result}


def _dispatch(cmd: str) -> Optional[Dict[str, Any]]:
    """Send a command to the router config store and return the response.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): Response status ('ok', 'error', 'timeout').
            - data (Any): Parsed response body.
        Returns None on socket/connection failure.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect('/var/tmp/cs.sock')
            sock.sendall(cmd.encode('ascii'))
            return _sock_receive(sock)
    except Exception as e:
        log(f"Dispatch error: {e}")
        return None


# =============================================================================
# INTERNAL: Remote HTTP Communication (Development)
# =============================================================================

_cached_device_ip = None
_cached_username = None
_cached_password = None
_cached_auth = None


def _get_credentials() -> Tuple[str, str, str]:
    """Load and cache device credentials from sdk_settings.ini.

    Returns:
        Tuple[str, str, str]: (device_ip, username, password) from
            sdk_settings.ini. Empty strings if not found.
    """
    global _cached_device_ip, _cached_username, _cached_password

    if _cached_device_ip is not None:
        return _cached_device_ip, _cached_username, _cached_password

    try:
        parent_ini = os.path.join(os.path.dirname(os.getcwd()), 'sdk_settings.ini')
        current_ini = os.path.join(os.getcwd(), 'sdk_settings.ini')

        if os.path.exists(parent_ini):
            ini_path = parent_ini
        elif os.path.exists(current_ini):
            ini_path = current_ini
        else:
            ini_path = parent_ini

        config = configparser.ConfigParser()
        config.read(ini_path)

        sdk = config['sdk'] if 'sdk' in config else {}
        _cached_device_ip = sdk.get('dev_client_ip', '')
        _cached_username = sdk.get('dev_client_username', '')
        _cached_password = sdk.get('dev_client_password', '')
    except Exception as e:
        log(f"Error reading sdk_settings.ini: {e}")
        _cached_device_ip = ''
        _cached_username = ''
        _cached_password = ''

    return _cached_device_ip, _cached_username, _cached_password


def _get_auth():
    """Get the appropriate HTTP auth object (Basic or Digest) for the device.

    Returns:
        Auth object (HTTPBasicAuth or HTTPDigestAuth) for requests,
        or None if the requests library is unavailable.
    """
    global _cached_auth

    if _cached_auth is not None:
        return _cached_auth

    if requests is None:
        return None

    device_ip, username, password = _get_credentials()

    # Try Basic auth first (NCOS 6.5+)
    try:
        url = f'http://{device_ip}/api/status/product_info'
        resp = requests.get(url, auth=requests.auth.HTTPBasicAuth(username, password))
        if resp.status_code == 200:
            _cached_auth = requests.auth.HTTPBasicAuth(username, password)
            return _cached_auth
    except Exception:
        pass

    _cached_auth = requests.auth.HTTPDigestAuth(username, password)
    return _cached_auth


# =============================================================================
# CORE API: Logging, Alerts, CRUD Operations
# =============================================================================

def log(value: str = '') -> None:
    """Log a message to syslog (router), stdout (container), or console (local).

    Args:
        value: Message to log.
    """
    if _enable_logging and _logger:
        _logger.info(value)
    elif _is_ncos:
        try:
            with open('/dev/stdout', 'w') as f:
                f.write(f'{value}\n')
        except Exception:
            print(value)
    else:
        print(value)


def alert(value: str = '') -> Optional[Dict[str, Any]]:
    """Send a custom alert to NCM. Only works on the router.

    Args:
        value: Alert message text.

    Returns:
        Optional[Dict[str, Any]]: On router, dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload.
        Returns None when running locally.
    """
    if _is_ncos:
        cmd = f"alert\n{_app_name}\n{value}\n"
        return _dispatch(cmd)
    else:
        log(f'Alert (local only): {value}')
        return None


def get(base: str, query: str = '', tree: int = 0) -> Any:
    """GET data from the router config/status tree.

    Args:
        base: Path to resource (e.g. 'status/system/uptime').
        query: Optional query string.
        tree: Tree identifier (default 0).

    Returns:
        The data at the specified path, or None on failure.
    """
    if _is_ncos:
        cmd = f"get\n{base}\n{query}\n{tree}\n"
        result = _dispatch(cmd)
        if result:
            return result.get('data')
        return None
    else:
        if requests is None:
            log("requests library not available for remote access")
            return None
        device_ip, _, _ = _get_credentials()
        url = f'http://{device_ip}/api/{base}/{query}'
        try:
            resp = requests.get(url, auth=_get_auth())
            return json.loads(resp.text).get('data')
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            log(f"Timeout: device at {device_ip} did not respond.")
            return None
        except Exception as e:
            log(f"GET error: {e}")
            return None


def put(base: str, value: Any = '', query: str = '', tree: int = 0) -> Optional[Dict[str, Any]]:
    """PUT (update) data in the router config/status tree.

    Args:
        base: Path to resource.
        value: Value to set (will be JSON-serialized).
        query: Optional query string.
        tree: Tree identifier (default 0).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload from config store.
        Returns None on connection/timeout failure.
    """
    value_json = json.dumps(value)
    if _is_ncos:
        cmd = f"put\n{base}\n{query}\n{tree}\n{value_json}\n"
        return _dispatch(cmd)
    else:
        if requests is None:
            return None
        device_ip, _, _ = _get_credentials()
        url = f'http://{device_ip}/api/{base}/{query}'
        try:
            resp = requests.put(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=_get_auth(),
                data={"data": value_json}
            )
            return json.loads(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            log(f"Timeout: device at {device_ip} did not respond.")
            return None
        except Exception as e:
            log(f"PUT error: {e}")
            return None


def post(base: str, value: Any = '', query: str = '') -> Optional[Dict[str, Any]]:
    """POST (create) data in the router config/status tree.

    Args:
        base: Path to resource.
        value: Value to post (will be JSON-serialized).
        query: Optional query string.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload (often the created resource ID).
        Returns None on connection/timeout failure.
    """
    value_json = json.dumps(value)
    if _is_ncos:
        cmd = f"post\n{base}\n{query}\n{value_json}\n"
        return _dispatch(cmd)
    else:
        if requests is None:
            return None
        device_ip, _, _ = _get_credentials()
        url = f'http://{device_ip}/api/{base}/{query}'
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=_get_auth(),
                data={"data": value_json}
            )
            return json.loads(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            log(f"Timeout: device at {device_ip} did not respond.")
            return None
        except Exception as e:
            log(f"POST error: {e}")
            return None


def patch(value: List[Any]) -> Optional[Dict[str, Any]]:
    """PATCH the router config tree (bulk add/remove).

    Args:
        value: List containing [adds_dict, removals_list].

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload.
        Returns None on connection/timeout failure.
    """
    if _is_ncos:
        if value[0].get("config"):
            adds = value[0]
        else:
            adds = {"config": value[0]}
        adds_json = json.dumps(adds)
        removals_json = json.dumps(value[1])
        cmd = f"patch\n{adds_json}\n{removals_json}\n"
        return _dispatch(cmd)
    else:
        if requests is None:
            return None
        device_ip, _, _ = _get_credentials()
        url = f'http://{device_ip}/api/'
        try:
            resp = requests.patch(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=_get_auth(),
                data={"data": json.dumps(value)}
            )
            return json.loads(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            log(f"Timeout: device at {device_ip} did not respond.")
            return None
        except Exception as e:
            log(f"PATCH error: {e}")
            return None


def delete(base: str, query: str = '') -> Optional[Dict[str, Any]]:
    """DELETE data from the router config tree.

    Args:
        base: Path to resource.
        query: Optional query string.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload.
        Returns None on connection/timeout failure.
    """
    if _is_ncos:
        cmd = f"delete\n{base}\n{query}\n"
        return _dispatch(cmd)
    else:
        if requests is None:
            return None
        device_ip, _, _ = _get_credentials()
        url = f'http://{device_ip}/api/{base}/{query}'
        try:
            resp = requests.delete(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=_get_auth(),
                data={"data": base}
            )
            return json.loads(resp.text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            log(f"Timeout: device at {device_ip} did not respond.")
            return None
        except Exception as e:
            log(f"DELETE error: {e}")
            return None


def decrypt(base: str, query: str = '', tree: int = 0) -> Any:
    """Decrypt and retrieve encrypted data from the router. Only works on router.

    Args:
        base: Path to encrypted resource.
        query: Optional query string.
        tree: Tree identifier (default 0).

    Returns:
        Decrypted data, or None if running locally or on failure.
    """
    if _is_ncos:
        cmd = f"decrypt\n{base}\n{query}\n{tree}\n"
        result = _dispatch(cmd)
        if result:
            return result.get('data')
        return None
    else:
        log('Decrypt is only available when running on NCOS.')
        return None


# =============================================================================
# CORE API: Event Registration & Callbacks
# =============================================================================

_event_running = False
_event_sock = None
_event_file = None
_event_thread = None
_registry = {}  # type: Dict[int, Dict[str, Any]]
_next_eid = 1
_event_lock = threading.Lock()


def _start_event_loop() -> None:
    """Start the background event handling loop (internal)."""
    global _event_running, _event_sock, _event_file, _event_thread

    if _event_running:
        return

    if not _is_ncos:
        log('Event registration is only available on NCOS.')
        return

    try:
        pid = os.getpid()
        _event_file = f'/var/tmp/csevent_{pid}.sock'

        try:
            os.unlink(_event_file)
        except FileNotFoundError:
            pass

        _event_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        _event_sock.bind(_event_file)
        _event_sock.listen()
        _event_sock.setblocking(False)

        _event_running = True
        _event_thread = threading.Thread(target=_handle_events, daemon=True)
        _event_thread.start()
    except Exception as e:
        log(f"Error starting event loop: {e}")
        _event_running = False


def _stop_event_loop() -> None:
    """Stop the event loop and unregister all callbacks (internal)."""
    global _event_running, _event_sock, _event_file

    if not _event_running:
        return

    try:
        # Unregister all
        for eid in list(_registry.keys()):
            unregister(eid)

        _event_sock.close()
        os.unlink(_event_file)
    except Exception as e:
        log(f"Error stopping event loop: {e}")
    finally:
        _event_running = False


def _handle_events() -> None:
    """Background thread: poll for config store events and dispatch callbacks."""
    poller = select.poll()
    poller.register(_event_sock, select.POLLIN | select.POLLERR | select.POLLHUP)

    while _event_running:
        try:
            events = poller.poll(1000)
            for fd, ev in events:
                if ev & (select.POLLERR | select.POLLHUP):
                    log("Event socket hangup/error. Stopping event loop.")
                    _stop_event_loop()
                    return

                if ev & select.POLLIN:
                    conn, _ = _event_sock.accept()
                    result = _sock_receive(conn)

                    if not result or not result.get('data'):
                        continue

                    eid = int(result['data']['id'])

                    with _event_lock:
                        entry = _registry.get(eid)

                    if not entry:
                        log(f"No registration found for eid {eid}")
                        continue

                    cb = entry['cb']
                    args = entry['args']

                    # Parse the config value
                    try:
                        cfg = json.loads(result['data']['cfg'])
                    except (TypeError, json.JSONDecodeError):
                        cfg = result['data']['cfg']

                    # Invoke callback
                    try:
                        cb_return = cb(result['data']['path'], cfg, args)
                    except Exception:
                        traceback_module.print_exc()
                        log(f"Exception in callback for eid {eid}")
                        cb_return = None

                    # For 'get' actions, send response back
                    if result['data'].get('action') == 'get' and cb_return is not None:
                        response = json.dumps(cb_return)
                        conn.sendall(response.encode())

        except OSError as e:
            if _event_running:
                log(f"Event loop OSError: {e}")
            break
        except Exception as e:
            if _event_running:
                log(f"Event loop error: {e}")


def register(action: str = 'put', path: str = '', callback: Callable = None, *args: Any) -> Optional[Dict[str, Any]]:
    """Register a callback for a config store event.

    The callback signature must be: callback(path, value, args)
    where args is a tuple of any extra arguments passed here.

    Args:
        action: Event action to listen for ('put', 'get', 'set'). Use 'put' for control tree.
        path: Config store path to monitor.
        callback: Function to invoke when the event fires.
        *args: Additional arguments passed to the callback as a tuple.

    Returns:
        Optional[Dict[str, Any]]: Registration result dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload.
        Returns None on failure or when not running on NCOS.

    Example:
        def on_change(path, value, args):
            cp.log(f'{path} changed to {value}')

        cp.register('put', 'control/myapp/trigger', on_change)
    """
    global _next_eid

    if not _is_ncos:
        log('Event registration is only available on NCOS.')
        return None

    if not _event_running:
        _start_event_loop()

    try:
        with _event_lock:
            eid = _next_eid
            _next_eid += 1
            _registry[eid] = {'cb': callback, 'action': action, 'path': path, 'args': args}

        pid = os.getpid()
        cmd = f"register\n{pid}\n{eid}\n{action}\n{path}\n"
        return _dispatch(cmd)
    except Exception as e:
        log(f"Error registering callback for {path}: {e}")
        return None


# Alias for convenience
on = register


def unregister(eid: int = 0) -> Optional[Dict[str, Any]]:
    """Unregister a previously registered callback.

    Args:
        eid: Event ID returned implicitly during registration (stored in _registry).

    Returns:
        Optional[Dict[str, Any]]: Unregistration result dict with keys:
            - status (str): 'ok' or 'error'.
            - data (Any): Response payload.
        Returns None if eid not found or event loop not running.
    """
    with _event_lock:
        entry = _registry.pop(eid, None)

    if not entry:
        return None

    if _event_running:
        pid = os.getpid()
        cmd = f"unregister\n{pid}\n{eid}\n{entry['action']}\n{entry['path']}\n"
        return _dispatch(cmd)
    return None


# =============================================================================
# APPDATA: Read/Write SDK Application Data
# =============================================================================

def get_appdata(name: str = '') -> Union[Optional[str], Optional[List[Dict[str, Any]]]]:
    """Get appdata value by name, or all appdata entries if no name given.

    Args:
        name: Appdata field name. If empty, returns all appdata entries.

    Returns:
        Union[Optional[str], Optional[List[Dict[str, Any]]]]:
            - If name provided: str value of the matching entry, or None.
            - If name empty: list of dicts, each with keys:
                - name (str): Appdata field name.
                - value (str): Appdata field value.
                - _id_ (str): Internal resource ID.
            Returns None on error.
    """
    try:
        appdata = get('config/system/sdk/appdata')
        if not appdata:
            return None if name else []
        if not name:
            return appdata
        return next((x["value"] for x in appdata if x["name"].lower() == name.lower()), None)
    except Exception as e:
        log(f"Error getting appdata '{name}': {e}")
        return None


def put_appdata(name: str, value: str) -> None:
    """Set appdata value by name. Creates the entry if it doesn't exist.

    Args:
        name: Appdata field name.
        value: Value to set (string).
    """
    try:
        appdata = get('config/system/sdk/appdata')
        if appdata:
            for item in appdata:
                if item["name"] == name:
                    put(f'config/system/sdk/appdata/{item["_id_"]}/value', value)
                    return
        post('config/system/sdk/appdata', {"name": name, "value": value})
    except Exception as e:
        log(f"Error putting appdata '{name}': {e}")


def post_appdata(name: str, value: str) -> None:
    """Create a new appdata entry (does not check for duplicates).

    Args:
        name: Appdata field name.
        value: Value to set.
    """
    try:
        post('config/system/sdk/appdata', {"name": name, "value": value})
    except Exception as e:
        log(f"Error posting appdata '{name}': {e}")


def delete_appdata(name: str) -> None:
    """Delete an appdata entry by name.

    Args:
        name: Appdata field name to delete.
    """
    try:
        appdata = get('config/system/sdk/appdata')
        if appdata:
            for item in appdata:
                if item["name"] == name:
                    delete(f'config/system/sdk/appdata/{item["_id_"]}')
                    return
    except Exception as e:
        log(f"Error deleting appdata '{name}': {e}")


# =============================================================================
# DEVICE INFO: Product, Firmware, Identifiers
# =============================================================================

def get_name() -> Optional[str]:
    """Get the device name (system_id).

    Returns:
        Optional[str]: Device name string, or None on error.
    """
    try:
        return get('config/system/system_id')
    except Exception as e:
        log(f"Error getting device name: {e}")
        return None


def get_mac(format_with_colons: bool = False) -> Optional[str]:
    """Get the device MAC address.

    Args:
        format_with_colons: If True, return with colons. If False, return raw.

    Returns:
        Optional[str]: MAC address string (e.g. '00:30:44:1A:2B:3C' or
            '0030441A2B3C'), or None if unavailable.
    """
    try:
        mac = get('status/product_info/mac0')
        if not mac:
            return None
        return mac if format_with_colons else mac.replace(':', '')
    except Exception as e:
        log(f"Error getting MAC: {e}")
        return None


def get_serial_number() -> Optional[str]:
    """Get the device serial number.

    Returns:
        Optional[str]: Serial number string, or None on error.
    """
    try:
        return get('status/product_info/manufacturing/serial_num')
    except Exception as e:
        log(f"Error getting serial number: {e}")
        return None


def get_product_type() -> Optional[str]:
    """Get the device product name.

    Returns:
        Optional[str]: Product name string (e.g. 'IBR900-600M'),
            or None on error.
    """
    try:
        return get('status/product_info/product_name')
    except Exception as e:
        log(f"Error getting product type: {e}")
        return None


def get_firmware_version(include_build_info: bool = False) -> str:
    """Get the firmware version string.

    Args:
        include_build_info: Include build metadata in the string.

    Returns:
        Firmware version string, or 'Unknown' on error.
    """
    try:
        fw = get('status/fw_info')
        version = f"{fw['major_version']}.{fw['minor_version']}.{fw['patch_version']}-{fw['fw_release_tag']}"
        if include_build_info and fw.get('build_info'):
            version += f" ({fw['build_info']})"
        return version
    except Exception as e:
        log(f"Error getting firmware version: {e}")
        return "Unknown"


def get_uptime() -> int:
    """Get router uptime in seconds.

    Returns:
        int: Uptime in seconds, or 0 on error.
    """
    try:
        return int(get('status/system/uptime'))
    except Exception as e:
        log(f"Error getting uptime: {e}")
        return 0


def get_router_model() -> Optional[str]:
    """Get the router model (part before first dash in product name).

    Returns:
        Optional[str]: Model string (e.g. 'IBR900'), or None on error.
    """
    try:
        product = get_product_type()
        if product:
            return product.split('-')[0]
        return None
    except Exception as e:
        log(f"Error getting router model: {e}")
        return None


# =============================================================================
# WAIT HELPERS
# =============================================================================

def wait_for_uptime(min_uptime_seconds: int = 60, timeout: Optional[int] = None) -> bool:
    """Block until router uptime exceeds the specified minimum.

    Args:
        min_uptime_seconds: Minimum uptime to wait for (default 60).
        timeout: Max seconds to wait, or None to wait indefinitely (default).

    Returns:
        True if uptime reached, False if timeout expired.
    """
    try:
        current = get_uptime()
        if current >= min_uptime_seconds:
            return True
        sleep_time = min_uptime_seconds - current
        if timeout is not None and sleep_time > timeout:
            log(f"Uptime wait would need {sleep_time}s but timeout is {timeout}s")
            time.sleep(timeout)
            return get_uptime() >= min_uptime_seconds
        log(f"Waiting {sleep_time}s for uptime to reach {min_uptime_seconds}s")
        time.sleep(sleep_time)
        return True
    except Exception as e:
        log(f"Error in wait_for_uptime: {e}")
        return False


def wait_for_ntp(timeout: Optional[int] = None, check_interval: int = 1) -> bool:
    """Wait until NTP synchronization is achieved.

    Args:
        timeout: Max seconds to wait, or None to wait indefinitely (default).
        check_interval: Seconds between checks.

    Returns:
        True if NTP synced, False if timeout expired.
    """
    try:
        start = time.time()
        while True:
            if timeout is not None and time.time() - start >= timeout:
                log(f'NTP sync timeout after {timeout}s')
                return False
            sync_age = get('status/system/ntp/sync_age')
            if sync_age is not None:
                log(f'NTP sync achieved, sync_age: {sync_age}')
                return True
            time.sleep(check_interval)
    except Exception as e:
        log(f"Error waiting for NTP: {e}")
        return False


def wait_for_wan_connection(timeout: Optional[int] = None) -> bool:
    """Wait for WAN to reach 'connected' state.

    Args:
        timeout: Max seconds to wait, or None to wait indefinitely (default).

    Returns:
        True if connected, False if timeout expired.
    """
    try:
        state = get('status/wan/connection_state')
        if state == 'connected':
            return True

        log("Waiting for WAN connection...")
        start = time.time()
        while True:
            if timeout is not None and time.time() - start >= timeout:
                log(f"WAN connection timeout after {timeout}s")
                return False
            state = get('status/wan/connection_state')
            if state == 'connected':
                log("WAN connected.")
                return True
            time.sleep(1)
    except Exception as e:
        log(f"Error waiting for WAN: {e}")
        return False


# =============================================================================
# GPS & COORDINATES
# =============================================================================

def dec(deg: float, minutes: float = 0.0, sec: float = 0.0) -> Optional[float]:
    """Convert degrees/minutes/seconds to decimal degrees.

    Args:
        deg: Degrees component.
        minutes: Minutes component.
        sec: Seconds component.

    Returns:
        Decimal degrees rounded to 6 places, or None on error.
    """
    try:
        if str(deg)[0] == '-':
            return round(deg - (minutes / 60) - (sec / 3600), 6)
        else:
            return round(deg + (minutes / 60) + (sec / 3600), 6)
    except Exception as e:
        log(f"Error converting coordinates: {e}")
        return None


def get_lat_long(max_retries: int = 5, retry_delay: float = 0.1) -> Tuple[Optional[float], Optional[float]]:
    """Get GPS latitude and longitude as decimal floats.

    Args:
        max_retries: Number of retries if GPS fix not available.
        retry_delay: Seconds between retries.

    Returns:
        Tuple of (latitude, longitude) or (None, None) if unavailable.
    """
    try:
        fix = get('status/gps/fix')
        retries = 0
        while not fix and retries < max_retries:
            time.sleep(retry_delay)
            fix = get('status/gps/fix')
            retries += 1

        if not fix:
            return None, None

        lat = dec(fix['latitude']['degree'], fix['latitude']['minute'], fix['latitude']['second'])
        lon = dec(fix['longitude']['degree'], fix['longitude']['minute'], fix['longitude']['second'])

        if lat is None or lon is None:
            return None, None

        return float(f"{lat:.6f}"), float(f"{lon:.6f}")
    except Exception:
        return None, None


def get_gps_status() -> Dict[str, Any]:
    """Get comprehensive GPS status.

    Returns:
        Dict with gps_lock, satellites, latitude, longitude, altitude, speed,
        heading, accuracy, last_fix_age. Returns minimal dict if no GPS data.
    """
    try:
        gps_data = get('status/gps')
        if not gps_data:
            return {"gps_lock": False, "satellites": 0}

        fix = gps_data.get("fix", {})
        result = {
            "gps_lock": fix.get("lock", False),
            "satellites": fix.get("satellites", 0),
            "latitude": None,
            "longitude": None,
            "altitude": fix.get("altitude_meters"),
            "speed": fix.get("ground_speed_knots"),
            "heading": fix.get("heading"),
            "accuracy": fix.get("accuracy"),
            "last_fix_age": fix.get("age")
        }

        if fix.get("latitude") and fix.get("longitude"):
            result["latitude"] = dec(
                fix['latitude']['degree'],
                fix['latitude']['minute'],
                fix['latitude']['second']
            )
            result["longitude"] = dec(
                fix['longitude']['degree'],
                fix['longitude']['minute'],
                fix['longitude']['second']
            )

        return result
    except Exception as e:
        log(f"Error getting GPS status: {e}")
        return {"gps_lock": False, "satellites": 0}


# =============================================================================
# WAN & CONNECTIVITY
# =============================================================================

def get_wan_connection_state() -> Optional[str]:
    """Get the WAN connection state string.

    Returns:
        Optional[str]: State string (e.g. 'connected', 'disconnected',
            'standby'), or None on error.
    """
    try:
        return get('status/wan/connection_state')
    except Exception as e:
        log(f"Error getting WAN state: {e}")
        return None


def get_wan_ip_address() -> Optional[str]:
    """Get the WAN IP address.

    Returns:
        Optional[str]: IP address string, or None on error.
    """
    try:
        return get('status/wan/ipinfo/ip_address')
    except Exception as e:
        log(f"Error getting WAN IP: {e}")
        return None


def get_wan_primary_device() -> Optional[str]:
    """Get the primary WAN device UID.

    Returns:
        Optional[str]: Device UID string (e.g. 'mdm-12345678'),
            or None on error.
    """
    try:
        return get('status/wan/primary_device')
    except Exception as e:
        log(f"Error getting WAN primary device: {e}")
        return None


def get_connected_wans(max_retries: int = 10) -> List[str]:
    """Get list of connected WAN device UIDs.

    Args:
        max_retries: Number of retries to get device list.

    Returns:
        List of connected WAN device UIDs.
    """
    try:
        wans = None
        retries = 0
        while not wans and retries < max_retries:
            wans = get('status/wan/devices')
            retries += 1
            if not wans:
                time.sleep(0.1)

        if not wans:
            log('No WAN devices found')
            return []

        connected = [k for k, v in wans.items()
                     if v.get('status', {}).get('connection_state') == 'connected']
        if not connected:
            log('No WANs connected')
        return connected
    except Exception as e:
        log(f"Error getting connected WANs: {e}")
        return []


def get_sims(max_retries: int = 10) -> List[str]:
    """Get list of modem UIDs that have SIMs installed.

    Args:
        max_retries: Number of retries to get device list.

    Returns:
        List of modem UIDs with SIMs (excludes NOSIM devices).
    """
    try:
        devices = None
        retries = 0
        while not devices and retries < max_retries:
            devices = get('status/wan/devices')
            retries += 1
            if not devices:
                time.sleep(0.1)

        if not devices:
            return []

        sims = []
        for uid, status in devices.items():
            if uid.startswith('mdm-'):
                error_text = status.get('status', {}).get('error_text', '')
                if 'NOSIM' not in error_text:
                    sims.append(uid)
        return sims
    except Exception as e:
        log(f"Error getting SIMs: {e}")
        return []


def get_wan_status() -> Optional[Dict[str, Any]]:
    """Get comprehensive WAN status with all devices and diagnostics.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - primary_device (Optional[str]): UID of primary WAN device.
            - connection_state (Optional[str]): First device's state.
            - devices (List[Dict]): Each dict has:
                - uid (str): Device UID.
                - connection_state (Optional[str]): e.g. 'connected'.
                - signal_strength (Optional[int]): Signal in dBm.
                - ip_address (Optional[str]): Assigned IP.
                - uptime (Optional[int]): Connection uptime seconds.
        Returns empty dict if no WAN data, None on error.
    """
    try:
        wan_data = get('status/wan')
        if not wan_data:
            return {}

        result = {
            "primary_device": wan_data.get("primary_device"),
            "connection_state": None,
            "devices": []
        }

        devices = wan_data.get("devices", {})
        for device_id, device_info in devices.items():
            device = {
                "uid": device_id,
                "connection_state": device_info.get("status", {}).get("connection_state"),
                "signal_strength": device_info.get("status", {}).get("signal_strength"),
                "ip_address": device_info.get("status", {}).get("ipinfo", {}).get("ip_address"),
                "uptime": device_info.get("status", {}).get("uptime")
            }
            result["devices"].append(device)

            if result["connection_state"] is None:
                result["connection_state"] = device["connection_state"]

        return result
    except Exception as e:
        log(f"Error getting WAN status: {e}")
        return None


def get_signal_strength(uid: str = None, include_backlog: bool = False) -> Optional[Dict[str, Any]]:
    """Get signal strength and diagnostics for a cellular modem.

    Args:
        uid: Modem device UID (e.g. 'mdm-12345678'). If None, uses first modem.
        include_backlog: Include historical signal data.

    Returns:
        Optional[Dict[str, Any]]: Dict with available signal metrics:
            - signal_strength (int): Signal strength in dBm.
            - cellular_health_score (int): Health score 0-100.
            - cellular_health_category (str): e.g. 'Good', 'Poor'.
            - connection_state (str): e.g. 'connected'.
            - rsrp (str): Reference Signal Received Power.
            - rsrp_5g (str): 5G RSRP.
            - rsrq (str): Reference Signal Received Quality.
            - rsrq_5g (str): 5G RSRQ.
            - sinr (str): Signal to Interference+Noise Ratio.
            - sinr_5g (str): 5G SINR.
            - dbm (str): Signal power in dBm.
            - rf_band (str): Active RF band.
            - service_type (str): e.g. 'LTE', '5G-NR'.
            - signal_backlog (list): Historical data (if requested).
            Only non-empty values are included. Returns None on failure.
    """
    try:
        if uid is None:
            sims = get_sims()
            if not sims:
                return None
            uid = sims[0]

        if not uid.startswith('mdm-'):
            log(f"Not a modem UID: {uid}")
            return None

        device_data = get(f'status/wan/devices/{uid}')
        if not device_data:
            return None

        status = device_data.get('status', {})
        diagnostics = device_data.get('diagnostics', {})

        info = {}

        # Status fields
        if status.get('signal_strength') is not None:
            info['signal_strength'] = status['signal_strength']
        if include_backlog and status.get('signal_backlog'):
            info['signal_backlog'] = status['signal_backlog']
        if status.get('cellular_health_score') is not None:
            info['cellular_health_score'] = status['cellular_health_score']
        if status.get('cellular_health_category'):
            info['cellular_health_category'] = status['cellular_health_category']
        if status.get('connection_state'):
            info['connection_state'] = status['connection_state']

        # Diagnostics - only include non-empty values
        diag_map = {
            'active_apn': 'ACTIVEAPN', 'carrier_id': 'CARRID', 'cell_id': 'CELL_ID',
            'dbm': 'DBM', 'ecio': 'ECIO', 'home_carrier_id': 'HOMECARRID',
            'lte_bandwidth': 'LTEBANDWIDTH', 'phy_cell_id': 'PHY_CELL_ID',
            'rf_band': 'RFBAND', 'rf_channel': 'RFCHANNEL',
            'rsrp': 'RSRP', 'rsrp_5g': 'RSRP_5G',
            'rsrq': 'RSRQ', 'rsrq_5g': 'RSRQ_5G',
            'sinr': 'SINR', 'sinr_5g': 'SINR_5G',
            'service_type': 'SRVC_TYPE', 'service_type_details': 'SRVC_TYPE_DETAILS',
            'tac': 'TAC', 'modem_temp': 'MODEMTEMP'
        }

        for key, diag_key in diag_map.items():
            val = diagnostics.get(diag_key)
            if val is not None and val != '':
                info[key] = val

        return info
    except Exception as e:
        log(f"Error getting signal strength: {e}")
        return None


# =============================================================================
# LAN & CLIENTS
# =============================================================================

def get_lan_clients() -> Dict[str, Any]:
    """Get LAN client information split by IPv4/IPv6.

    Returns:
        Dict[str, Any]: Dict with keys:
            - total_ipv4_clients (int): Count of IPv4 clients.
            - total_ipv6_clients (int): Count of IPv6 (link-local) clients.
            - ipv4_clients (List[Dict]): IPv4 client entries.
            - ipv6_clients (List[Dict]): IPv6 link-local client entries.
    """
    try:
        lan_data = get('status/lan')
        if not lan_data:
            return {"total_ipv4_clients": 0, "total_ipv6_clients": 0,
                    "ipv4_clients": [], "ipv6_clients": []}

        all_clients = lan_data.get("clients", [])
        ipv4 = [c for c in all_clients if not c.get("ip_address", "").startswith("fe80::")]
        ipv6 = [c for c in all_clients if c.get("ip_address", "").startswith("fe80::")]

        return {
            "total_ipv4_clients": len(ipv4),
            "total_ipv6_clients": len(ipv6),
            "ipv4_clients": ipv4,
            "ipv6_clients": ipv6
        }
    except Exception as e:
        log(f"Error getting LAN clients: {e}")
        return {"total_ipv4_clients": 0, "total_ipv6_clients": 0,
                "ipv4_clients": [], "ipv6_clients": []}


def get_ipv4_wired_clients() -> List[Dict[str, Any]]:
    """Get IPv4 wired (non-WiFi) LAN clients with hostname resolution.

    Returns:
        List[Dict[str, Any]]: Each dict has keys:
            - mac (Optional[str]): Client MAC address.
            - hostname (Optional[str]): Resolved hostname from DHCP lease.
            - ip_address (Optional[str]): IPv4 address.
            - network (Optional[str]): LAN network name.
    """
    try:
        lan_clients = get('status/lan/clients') or []
        leases = get('status/dhcpd/leases') or []

        # Filter IPv4 only
        lan_clients = [c for c in lan_clients if ":" not in c.get("ip_address", "")]

        wired = []
        for client in lan_clients:
            mac_upper = client.get("mac", "").upper()
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else None
            network = lease.get("network") if lease else None

            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wired.append({
                "mac": client.get("mac"),
                "hostname": hostname,
                "ip_address": client.get("ip_address"),
                "network": network
            })
        return wired
    except Exception as e:
        log(f"Error getting wired clients: {e}")
        return []


def get_ipv4_wifi_clients() -> List[Dict[str, Any]]:
    """Get IPv4 WiFi clients with SSID, signal, and band info.

    Returns:
        List[Dict[str, Any]]: Each dict has keys:
            - mac (Optional[str]): Client MAC address.
            - hostname (Optional[str]): Resolved hostname.
            - ip_address (Optional[str]): IPv4 address from DHCP.
            - radio (int): Radio index.
            - bss (int): BSS index.
            - ssid (Optional[str]): SSID the client is connected to.
            - network (Optional[str]): LAN network name.
            - band (str): Frequency band ('2.4' or '5').
            - mode (str): WiFi mode (e.g. '802.11ac').
            - bw (str): Channel bandwidth (e.g. '80 MHz').
            - txrate (Optional[int]): TX rate.
            - rssi (Optional[int]): Signal strength (RSSI).
            - time (int): Connection time in seconds.
    """
    try:
        wlan_clients = get('status/wlan/clients') or []
        leases = get('status/dhcpd/leases') or []

        bw_modes = {0: "20 MHz", 1: "40 MHz", 2: "80 MHz", 3: "80+80 MHz", 4: "160 MHz"}
        wlan_modes = {0: "802.11b", 1: "802.11g", 2: "802.11n", 3: "802.11n-only",
                      4: "802.11ac", 5: "802.11ax"}
        wlan_band = {0: "2.4", 1: "5"}

        wifi = []
        for client in wlan_clients:
            radio = client.get("radio")
            bss = client.get("bss")
            ssid = get(f'config/wlan/radio/{radio}/bss/{bss}/ssid')

            mac_upper = client.get("mac", "").upper()
            lease = next((x for x in leases if x.get("mac", "").upper() == mac_upper), None)
            hostname = lease.get("hostname") if lease else client.get("hostname")
            network = lease.get("network") if lease else None

            if hostname and (hostname.upper() == mac_upper.replace(":", "-") or hostname == "*"):
                hostname = None

            wifi.append({
                "mac": client.get("mac"),
                "hostname": hostname,
                "ip_address": lease.get("ip_address") if lease else None,
                "radio": radio,
                "bss": bss,
                "ssid": ssid,
                "network": network,
                "band": wlan_band.get(radio, "Unknown"),
                "mode": wlan_modes.get(client.get("mode"), "Unknown"),
                "bw": bw_modes.get(client.get("bw"), "Unknown"),
                "txrate": client.get("txrate"),
                "rssi": client.get("rssi0"),
                "time": client.get("time", 0)
            })
        return wifi
    except Exception as e:
        log(f"Error getting WiFi clients: {e}")
        return []


def get_ipv4_lan_clients() -> Dict[str, List[Dict[str, Any]]]:
    """Get all IPv4 LAN clients (both wired and WiFi).

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dict with keys:
            - wired_clients (List[Dict]): From get_ipv4_wired_clients().
            - wifi_clients (List[Dict]): From get_ipv4_wifi_clients().
    """
    return {
        "wired_clients": get_ipv4_wired_clients(),
        "wifi_clients": get_ipv4_wifi_clients()
    }


# =============================================================================
# SYSTEM STATUS
# =============================================================================

def get_system_status() -> Optional[Dict[str, Any]]:
    """Get system status including uptime, CPU, memory, disk, services.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - uptime (Optional[int]): System uptime in seconds.
            - temperature (Optional[float]): CPU temperature Celsius.
            - cpu_usage (int): Estimated CPU usage percentage.
            - memory (Dict): Memory info with keys:
                - total_bytes (int): Total RAM.
                - used_bytes (int): Used RAM.
                - free_bytes (int): Available RAM.
                - percentage_used (float): Usage percentage.
            - disk (Dict): Disk info with keys:
                - total_bytes (int): Total disk space.
                - used_bytes (int): Used disk space.
                - free_bytes (int): Free disk space.
                - percentage_used (float): Usage percentage.
            - services_running (int): Count of started services.
            - services_disabled (int): Count of disabled services.
        Returns empty dict if no data, None on error.
    """
    try:
        system_data = get('status/system')
        if not system_data:
            return {}

        # Memory
        mem = system_data.get("memory", {})
        mem_total = float(mem.get("memtotal", 0))
        mem_available = float(mem.get("memavailable", 0))
        mem_used = mem_total - mem_available
        mem_pct = round((mem_used / mem_total * 100) if mem_total > 0 else 0, 1)

        # Disk
        disk_data = get('status/mount/disk_usage/') or {}
        disk_total = float(disk_data.get("total_bytes", 0))
        disk_free = float(disk_data.get("free_bytes", 0))
        disk_used = disk_total - disk_free
        disk_pct = round((disk_used / disk_total * 100) if disk_total > 0 else 0, 1)

        # CPU
        cpu = system_data.get("cpu", {})
        cpu_usage = round(
            float(cpu.get("nice", 0)) +
            float(cpu.get("system", 0)) +
            float(cpu.get("user", 0)) * 100
        )

        # Services
        services = system_data.get("services", {})
        running = sum(1 for s in services.values() if isinstance(s, dict) and s.get("state") == "started")
        disabled = sum(1 for s in services.values() if isinstance(s, dict) and s.get("state") == "disabled")

        return {
            "uptime": system_data.get("uptime"),
            "temperature": system_data.get("temperature"),
            "cpu_usage": cpu_usage,
            "memory": {
                "total_bytes": int(mem_total),
                "used_bytes": int(mem_used),
                "free_bytes": int(mem_available),
                "percentage_used": mem_pct
            },
            "disk": {
                "total_bytes": int(disk_total),
                "used_bytes": int(disk_used),
                "free_bytes": int(disk_free),
                "percentage_used": disk_pct
            },
            "services_running": running,
            "services_disabled": disabled
        }
    except Exception as e:
        log(f"Error getting system status: {e}")
        return None


def get_temperature(unit: str = 'fahrenheit') -> Optional[float]:
    """Get device temperature.

    Args:
        unit: 'celsius' or 'fahrenheit' (default).

    Returns:
        Temperature as float, or None.
    """
    try:
        temp = get('status/system/temperature')
        if temp is None:
            return None
        if unit.lower() == 'fahrenheit':
            return (temp * 9 / 5) + 32
        return temp
    except Exception as e:
        log(f"Error getting temperature: {e}")
        return None


# =============================================================================
# NCM (NetCloud Manager)
# =============================================================================

def get_ncm_status() -> Optional[str]:
    """Get NCM connection state.

    Returns:
        Optional[str]: State string (e.g. 'connected', 'disconnected'),
            or None on error.
    """
    try:
        return get('status/ecm/state')
    except Exception as e:
        log(f"Error getting NCM status: {e}")
        return None


def get_ncm_router_id() -> Optional[str]:
    """Get the router's NCM client ID.

    Returns:
        Optional[str]: NCM client ID string, or None on error.
    """
    try:
        return get('status/ecm/client_id')
    except Exception as e:
        log(f"Error getting NCM router ID: {e}")
        return None


def get_ncm_group_name() -> Optional[str]:
    """Get the router's NCM group name.

    Returns:
        Optional[str]: Group name string, or None on error.
    """
    try:
        return get('status/ecm/info/Group')
    except Exception as e:
        log(f"Error getting NCM group: {e}")
        return None


def get_ncm_account_name() -> Optional[str]:
    """Get the router's NCM account name.

    Returns:
        Optional[str]: Account name string, or None on error.
    """
    try:
        return get('status/ecm/info/Account')
    except Exception as e:
        log(f"Error getting NCM account: {e}")
        return None


def get_ncm_api_keys() -> Optional[Dict[str, Optional[str]]]:
    """Get NCM API keys stored in certificate management.

    Returns:
        Optional[Dict[str, Optional[str]]]: Dict mapping key names to
            their decrypted values. Keys include:
            - 'X-ECM-API-ID' (Optional[str])
            - 'X-ECM-API-KEY' (Optional[str])
            - 'X-CP-API-ID' (Optional[str])
            - 'X-CP-API-KEY' (Optional[str])
            - 'Bearer Token' (Optional[str])
        Returns None on error.
    """
    try:
        certs = get('config/certmgmt/certs')
        if not certs:
            return None

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
                    api_keys[key] = decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')

        return api_keys
    except Exception as e:
        log(f"Error getting NCM API keys: {e}")
        return None


# =============================================================================
# CERTIFICATES
# =============================================================================

def extract_cert_and_key(cert_name_or_uuid: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract certificate and private key to local .pem files.

    Follows the CA chain to build a full-chain certificate file.

    Args:
        cert_name_or_uuid: Certificate name or UUID to extract.

    Returns:
        Tuple of (cert_filename, key_filename) or (None, None) if not found.
    """
    try:
        uuid_re = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        is_uuid = bool(uuid_re.match(cert_name_or_uuid))
        match_field = '_id_' if is_uuid else 'name'

        certs = get('config/certmgmt/certs')
        if not certs:
            return None, None

        cert_x509 = None
        cert_key = None
        ca_uuid = None
        cert_name = None

        for cert in certs:
            if cert.get(match_field) == cert_name_or_uuid:
                cert_name = cert.get('name')
                cert_x509 = cert.get('x509')
                cert_key = decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')
                ca_uuid = cert.get('ca_uuid')
                break
        else:
            log(f'Certificate "{cert_name_or_uuid}" not found')
            return None, None

        # Follow CA chain
        while ca_uuid not in ("", "None", None):
            for cert in certs:
                if cert.get('_id_') == ca_uuid:
                    cert_x509 += "\n" + cert.get('x509', '')
                    ca_uuid = cert.get('ca_uuid')
                    break
            else:
                break

        # Write files
        if cert_x509:
            with open(f"{cert_name}.pem", "w") as f:
                f.write(cert_x509)
        if cert_key:
            with open(f"{cert_name}_key.pem", "w") as f:
                f.write(cert_key)

        cert_file = f"{cert_name}.pem" if cert_x509 else None
        key_file = f"{cert_name}_key.pem" if cert_key else None
        return cert_file, key_file
    except Exception as e:
        log(f"Error extracting cert: {e}")
        return None, None


# =============================================================================
# GPIO
# =============================================================================

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
        'power_input': '/status/gpio/CONNECTOR_GPIO_2',
        'power_output': '/status/gpio/CONNECTOR_GPIO_1',
        'expander_1': '/status/gpio/EXPANDER_GPIO_1',
        'expander_2': '/status/gpio/EXPANDER_GPIO_2',
        'expander_3': '/status/gpio/EXPANDER_GPIO_3',
        'accessory_1': '/status/gpio/ACCESSORY_GPIO_1'
    }
}


def get_gpio(gpio_name: Optional[str] = None, router_model: Optional[str] = None) -> Any:
    """Get GPIO value(s) for the current router model.

    Args:
        gpio_name: Specific GPIO name (e.g. 'power_input'). If None, returns all.
        router_model: Override auto-detected model.

    Returns:
        Any: If gpio_name specified, the single GPIO value (int or bool).
        If gpio_name is None, dict mapping GPIO names to their values.
        Returns None on error or if model not in GPIO_MAP.
    """
    try:
        if router_model is None:
            router_model = get_router_model()
        if not router_model or router_model not in GPIO_MAP:
            log(f"Router model '{router_model}' not in GPIO map")
            return None

        model_gpios = GPIO_MAP[router_model]

        if gpio_name is None:
            # Return all mapped GPIOs
            values = {}
            for name, path in model_gpios.items():
                val = get(path)
                if val is not None:
                    values[name] = val
            return values

        if gpio_name not in model_gpios:
            log(f"GPIO '{gpio_name}' not available for {router_model}")
            return None

        return get(model_gpios[gpio_name])
    except Exception as e:
        log(f"Error getting GPIO: {e}")
        return None


def get_all_gpios() -> Dict[str, Any]:
    """Get raw GPIO data from /status/gpio.

    Returns:
        Dict[str, Any]: Raw GPIO status dict mapping GPIO names to values.
            Empty dict on error.
    """
    try:
        result = get('/status/gpio')
        return result if isinstance(result, dict) else {}
    except Exception as e:
        log(f"Error getting raw GPIOs: {e}")
        return {}


def get_available_gpios(router_model: Optional[str] = None) -> List[str]:
    """Get list of available GPIO names for the current router model.

    Args:
        router_model: Override auto-detected model.

    Returns:
        List of GPIO name strings.
    """
    try:
        if router_model is None:
            router_model = get_router_model()
        if not router_model or router_model not in GPIO_MAP:
            return []
        return list(GPIO_MAP[router_model].keys())
    except Exception as e:
        log(f"Error getting available GPIOs: {e}")
        return []


# =============================================================================
# DIAGNOSTICS: Ping, Traceroute, CLI
# =============================================================================

def ping_host(host: str, count: int = 4, packet_size: int = 56) -> Optional[Dict[str, Any]]:
    """Ping a host using the router's diagnostic tools.

    Args:
        host: Target hostname or IP address.
        count: Number of ping packets (default 4).
        packet_size: Packet size in bytes (default 56).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - host (str): Target host.
            - num (int): Packets sent.
            - size (int): Packet size.
            - tx (int): Packets transmitted.
            - rx (int): Packets received.
            - loss (float): Packet loss percentage.
            - min (float): Minimum RTT in ms.
            - avg (float): Average RTT in ms.
            - max (float): Maximum RTT in ms.
            - error (str): Present instead of stats on failure.
        Returns None on exception.
    """
    try:
        ping_params = {
            "host": host,
            "num": count,
            "size": packet_size,
            "df": True,
            "srcaddr": ""
        }

        # Clear and start
        put('control/ping/start', {})
        put('control/ping/status', '')
        put('control/ping/start', ping_params)

        # Wait for completion
        result = None
        for _ in range(30):
            result = get('control/ping')
            if result and result.get('status') in ("error", "done"):
                break
            time.sleep(0.5)

        stats = {"host": host, "num": count, "size": packet_size}

        if not result:
            stats['error'] = 'No results received'
            return stats

        if result.get('status') == 'error':
            stats['error'] = result.get('result', 'Unknown error')
            return stats

        raw = result.get('result', '')
        if not raw:
            stats['error'] = 'No results received'
            return stats

        # Parse statistics
        lines = raw.split('\n')

        for line in lines:
            if 'packets transmitted' in line:
                tx_m = re.search(r'(\d+)\s+packets transmitted', line)
                rx_m = re.search(r'(\d+)\s+received', line)
                loss_m = re.search(r'([\d.]+)% packet loss', line)
                if tx_m:
                    stats['tx'] = int(tx_m.group(1))
                if rx_m:
                    stats['rx'] = int(rx_m.group(1))
                if loss_m:
                    stats['loss'] = float(loss_m.group(1))
            elif 'min/avg/max' in line:
                rtt_m = re.search(r'min/avg/max\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)', line)
                if rtt_m:
                    stats['min'] = float(rtt_m.group(1))
                    stats['avg'] = float(rtt_m.group(2))
                    stats['max'] = float(rtt_m.group(3))

        # Fallback: parse individual responses if no summary found
        if 'tx' not in stats:
            responses = [l for l in lines if 'icmp_seq=' in l and 'time=' in l]
            stats['tx'] = count
            stats['rx'] = len(responses)
            stats['loss'] = ((count - len(responses)) / count * 100) if count > 0 else 0

            rtts = []
            for resp in responses:
                try:
                    t = float(resp.split('time=')[1].split(' ms')[0])
                    rtts.append(t)
                except Exception:
                    pass
            if rtts:
                stats['min'] = min(rtts)
                stats['max'] = max(rtts)
                stats['avg'] = sum(rtts) / len(rtts)

        return stats
    except Exception as e:
        log(f"Error pinging {host}: {e}")
        return None


def traceroute_host(host: str, max_hops: int = 30) -> Optional[Dict[str, Any]]:
    """Perform traceroute to a host using router diagnostics.

    Args:
        host: Target hostname or IP.
        max_hops: Maximum number of hops.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - host (str): Target host.
            - hops (List[str]): Parsed hop lines with RTT info.
            - hop_count (int): Number of hops.
            - raw_output (str): Full traceroute output.
            - error (str): Present instead of hops on failure.
        Returns None on exception.
    """
    try:
        put('control/traceroute/result', [])
        put('control/traceroute/start', {"host": host})
        time.sleep(1)

        result = None
        accumulated = []
        for _ in range(80):
            result = get('control/traceroute')
            if result and result.get('result'):
                current = result['result']
                if isinstance(current, list):
                    for chunk in current:
                        if chunk and chunk not in accumulated:
                            accumulated.append(chunk)
                elif isinstance(current, str) and current not in accumulated:
                    accumulated.append(current)

            if result and result.get('status') in ("error", "done", "not started"):
                break
            time.sleep(1.0)

        stats = {"host": host}

        if result and result.get('status') == 'error':
            stats['error'] = result.get('result', 'Unknown error')
            return stats

        output = ''.join(accumulated) if accumulated else ''
        if not output and result and result.get('result'):
            r = result['result']
            output = ''.join(r) if isinstance(r, list) else str(r)

        if not output:
            stats['error'] = 'No results received'
            return stats

        lines = output.split('\n')
        hops = [l.strip() for l in lines
                if l.strip() and not l.strip().startswith('traceroute to')
                and ('ms' in l or '*' in l)]

        stats['hops'] = hops
        stats['hop_count'] = len(hops)
        stats['raw_output'] = output
        return stats
    except Exception as e:
        log(f"Error tracerouting {host}: {e}")
        return None


def execute_cli(commands: Union[str, List[str]], timeout: int = 10,
                clean: bool = True) -> Optional[str]:
    """Execute CLI commands on the router and return output.

    Args:
        commands: Single command string or list of commands.
        timeout: Max seconds to wait for output.
        clean: Remove terminal escape sequences from output.

    Returns:
        Command output string, or None on error.
    """
    try:
        import random as _random

        if not commands:
            return None

        if isinstance(commands, str):
            commands = [commands]

        session_id = f"term-{_random.randint(100000000, 999999999)}"
        commands_nl = [cmd + '\n' for cmd in commands]

        interval = 0.3
        max_cycles = int(timeout / interval)
        output = ''
        cmd_iter = iter(commands_nl)
        current_cmd = next(cmd_iter)

        for _ in range(max_cycles):
            put(f"/control/csterm/{session_id}", {"k": current_cmd})
            response = get(f"/control/csterm/{session_id}")
            if response and 'k' in response:
                output += response['k']

            current_cmd = next(cmd_iter, "")
            if not current_cmd and not output.endswith('\n'):
                break
            time.sleep(interval)

        if clean and output:
            # Remove ANSI escape sequences
            output = re.sub(
                r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])',
                '', output
            )

        return output.strip() if output else None
    except Exception as e:
        log(f"Error executing CLI: {e}")
        return None


# =============================================================================
# WAN PROFILE MANAGEMENT
# =============================================================================

def get_wan_profiles() -> Optional[List[Dict[str, Any]]]:
    """Get all WAN profile rules sorted by priority.

    Returns:
        Optional[List[Dict[str, Any]]]: List of WAN profile dicts sorted
            by priority (lowest first). Each dict has keys like _id_,
            priority, trigger_name, disabled, modem, etc.
            Returns None on error.
    """
    try:
        rules = get('config/wan/rules2')
        if not rules:
            return None
        rules.sort(key=lambda x: x.get("priority", 0))
        return rules
    except Exception as e:
        log(f"Error getting WAN profiles: {e}")
        return None


def get_wan_device_profile(device_id: str) -> Optional[Dict[str, Any]]:
    """Get WAN profile applied to a specific device.

    Args:
        device_id: WAN device UID.

    Returns:
        Optional[Dict[str, Any]]: WAN profile dict with keys like
            _id_, priority, trigger_name, disabled, modem settings, etc.
            Returns None if not found.
    """
    try:
        profile_id = get(f'status/wan/devices/{device_id}/config/_id_')
        if not profile_id:
            return None
        return get(f'config/wan/rules2/{profile_id}')
    except Exception as e:
        log(f"Error getting device profile for {device_id}: {e}")
        return None


def set_wan_device_priority(device_id: str, new_priority: float) -> bool:
    """Set priority for a WAN device's profile.

    Args:
        device_id: WAN device UID.
        new_priority: New priority value (lower = higher priority).

    Returns:
        True on success, False on failure.
    """
    try:
        profile = get_wan_device_profile(device_id)
        if not profile:
            return False
        result = put(f'config/wan/rules2/{profile["_id_"]}/priority', new_priority)
        return result is not None
    except Exception as e:
        log(f"Error setting priority for {device_id}: {e}")
        return False


def enable_wan_device(device_id: str) -> bool:
    """Enable a WAN device.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        profile = get_wan_device_profile(device_id)
        if not profile:
            return False
        result = put(f'config/wan/rules2/{profile["_id_"]}/disabled', False)
        return result is not None
    except Exception as e:
        log(f"Error enabling {device_id}: {e}")
        return False


def disable_wan_device(device_id: str) -> bool:
    """Disable a WAN device.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        profile = get_wan_device_profile(device_id)
        if not profile:
            return False
        result = put(f'config/wan/rules2/{profile["_id_"]}/disabled', True)
        return result is not None
    except Exception as e:
        log(f"Error disabling {device_id}: {e}")
        return False


def set_manual_apn(device_or_id: str, new_apn: str) -> Optional[Dict[str, Any]]:
    """Set manual APN for a modem device or WAN rule.

    Args:
        device_or_id: Modem device UID (mdm-xxx) or WAN rule _id_.
        new_apn: APN string to set.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): Whether the operation succeeded.
            - rule_id (str): WAN rule ID that was updated.
            - new_apn (str): The APN that was set.
            - error (str): Present on failure instead of rule_id/new_apn.
        Returns None on exception.
    """
    try:
        rule_id = device_or_id
        if device_or_id.startswith('mdm'):
            config = get(f'status/wan/devices/{device_or_id}/config')
            if not config:
                return {'success': False, 'error': f'Device {device_or_id} not found'}
            rule_id = config.get('_id_')
            if not rule_id:
                return {'success': False, 'error': 'No WAN rule found for device'}

        result = put(f'config/wan/rules2/{rule_id}', {
            "modem": {"apn_mode": "manual", "manual_apn": new_apn}
        })

        if result is not None:
            return {'success': True, 'rule_id': rule_id, 'new_apn': new_apn}
        return None
    except Exception as e:
        log(f"Error setting APN for {device_or_id}: {e}")
        return None


def remove_manual_apn(device_or_id: str) -> Optional[Dict[str, Any]]:
    """Remove manual APN and revert to auto mode.

    Args:
        device_or_id: Modem device UID or WAN rule _id_.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): Whether the operation succeeded.
            - rule_id (str): WAN rule ID that was updated.
            - error (str): Present on failure.
        Returns None if device not found.
    """
    try:
        rule_id = device_or_id
        if device_or_id.startswith('mdm'):
            config = get(f'status/wan/devices/{device_or_id}/config')
            if not config:
                return None
            rule_id = config.get('_id_')
            if not rule_id:
                return None

        result = put(f'config/wan/rules2/{rule_id}', {"modem": {"apn_mode": "auto"}})
        if result is not None:
            return {'success': True, 'rule_id': rule_id}
        return {'success': False, 'error': 'Failed to update'}
    except Exception as e:
        log(f"Error removing APN for {device_or_id}: {e}")
        return None


# =============================================================================
# DEVICE MANAGEMENT
# =============================================================================

def reboot_device() -> None:
    """Reboot the router."""
    try:
        put('control/system/reboot', 'reboot hypmgr')
    except Exception as e:
        log(f"Error rebooting: {e}")


def set_description(description: str) -> Optional[Dict[str, Any]]:
    """Set device description.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): True on success.
            - description (str): The description that was set.
        Returns None on failure.
    """
    try:
        result = put('config/system/desc', description)
        if result is not None:
            return {'success': True, 'description': description}
        return None
    except Exception as e:
        log(f"Error setting description: {e}")
        return None


def set_asset_id(asset_id: str) -> Optional[Dict[str, Any]]:
    """Set device asset ID.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): True on success.
            - asset_id (str): The asset ID that was set.
        Returns None on failure.
    """
    try:
        result = put('config/system/asset_id', asset_id)
        if result is not None:
            return {'success': True, 'asset_id': asset_id}
        return None
    except Exception as e:
        log(f"Error setting asset ID: {e}")
        return None


def set_name(name: str) -> Optional[Dict[str, Any]]:
    """Set device name (system_id).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): True on success.
            - name (str): The name that was set.
        Returns None on failure.
    """
    try:
        result = put('config/system/system_id', name)
        if result is not None:
            return {'success': True, 'name': name}
        return None
    except Exception as e:
        log(f"Error setting name: {e}")
        return None


# =============================================================================
# SIGNAL HANDLER & CLEANUP
# =============================================================================

def _cleanup(sig: Any, frame: Any) -> None:
    """Clean up event registrations on SIGTERM."""
    try:
        _stop_event_loop()
    except Exception:
        pass
    sys.exit(0)


signal_module.signal(signal_module.SIGTERM, _cleanup)


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# These aliases allow code written for the old cp.py to work with cp2
# without modification in most cases.

# The old module exposed CSClient and EventingCSClient classes.
# For backward compat, we provide a minimal shim:

class _BackcompatClient:
    """Minimal shim for code that references cp.CSClient or cp.EventingCSClient."""

    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return get(*args, **kwargs)

    def put(self, *args, **kwargs):
        return put(*args, **kwargs)

    def post(self, *args, **kwargs):
        return post(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return delete(*args, **kwargs)

    def patch(self, *args, **kwargs):
        return patch(*args, **kwargs)

    def decrypt(self, *args, **kwargs):
        return decrypt(*args, **kwargs)

    def log(self, *args, **kwargs):
        return log(*args, **kwargs)

    def alert(self, *args, **kwargs):
        return alert(*args, **kwargs)

    def register(self, *args, **kwargs):
        return register(*args, **kwargs)

    def unregister(self, *args, **kwargs):
        return unregister(*args, **kwargs)

    def start(self):
        _start_event_loop()

    def stop(self):
        _stop_event_loop()


CSClient = _BackcompatClient
EventingCSClient = _BackcompatClient

# Placeholder for additional functions below


# =============================================================================
# GRANULAR STATUS: LAN
# =============================================================================

def get_lan_status() -> Optional[Dict[str, Any]]:
    """Get comprehensive LAN status including clients, networks, devices, stats.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - total_ipv4_clients (int): IPv4 client count.
            - total_ipv6_clients (int): IPv6 client count.
            - lan_stats (Dict): LAN traffic statistics.
            - ipv4_clients (List[Dict]): IPv4 client entries.
            - ipv6_clients (List[Dict]): IPv6 client entries.
            - networks (List[Dict]): Each with name, display_name,
                ip_address, netmask, type, devices.
            - devices (List[Dict]): Each with name, interface,
                link_state, type.
        Returns empty dict if no data, None on error.
    """
    try:
        lan_data = get('status/lan')
        if not lan_data:
            return {}

        lan_stats = get('status/lan/stats') or {}
        client_data = get_lan_clients()

        result = {
            "total_ipv4_clients": client_data.get("total_ipv4_clients", 0),
            "total_ipv6_clients": client_data.get("total_ipv6_clients", 0),
            "lan_stats": lan_stats,
            "ipv4_clients": client_data.get("ipv4_clients", []),
            "ipv6_clients": client_data.get("ipv6_clients", []),
            "networks": [],
            "devices": []
        }

        for net_name, net_info in lan_data.get("networks", {}).items():
            info = net_info.get("info", {})
            result["networks"].append({
                "name": net_name,
                "display_name": info.get("name"),
                "ip_address": info.get("ip_address"),
                "netmask": info.get("netmask"),
                "type": info.get("type"),
                "devices": net_info.get("devices", [])
            })

        for dev_name, dev_info in lan_data.get("devices", {}).items():
            result["devices"].append({
                "name": dev_name,
                "interface": dev_info.get("info", {}).get("iface"),
                "link_state": dev_info.get("status", {}).get("link_state"),
                "type": dev_info.get("info", {}).get("type")
            })

        return result
    except Exception as e:
        log(f"Error getting LAN status: {e}")
        return None


def get_lan_networks() -> Optional[Dict[str, Any]]:
    """Get LAN network information.

    Returns:
        Optional[Dict[str, Any]]: Dict with key:
            - networks (List[Dict]): Each with name, display_name,
                ip_address, netmask, type, devices.
        Returns empty dict if no data, None on error.
    """
    try:
        lan_data = get('status/lan')
        if not lan_data:
            return {}
        networks = []
        for net_name, net_info in lan_data.get("networks", {}).items():
            info = net_info.get("info", {})
            networks.append({
                "name": net_name,
                "display_name": info.get("name"),
                "ip_address": info.get("ip_address"),
                "netmask": info.get("netmask"),
                "type": info.get("type"),
                "devices": net_info.get("devices", [])
            })
        return {"networks": networks}
    except Exception as e:
        log(f"Error getting LAN networks: {e}")
        return None


def get_lan_devices() -> Optional[Dict[str, Any]]:
    """Get LAN device information.

    Returns:
        Optional[Dict[str, Any]]: Dict with key:
            - devices (List[Dict]): Each with name, interface,
                link_state, type.
        Returns empty dict if no data, None on error.
    """
    try:
        lan_data = get('status/lan')
        if not lan_data:
            return {}
        devices = []
        for dev_name, dev_info in lan_data.get("devices", {}).items():
            devices.append({
                "name": dev_name,
                "interface": dev_info.get("info", {}).get("iface"),
                "link_state": dev_info.get("status", {}).get("link_state"),
                "type": dev_info.get("info", {}).get("type")
            })
        return {"devices": devices}
    except Exception as e:
        log(f"Error getting LAN devices: {e}")
        return None


def get_lan_statistics() -> Optional[Dict[str, Any]]:
    """Get overall LAN statistics.

    Returns:
        Optional[Dict[str, Any]]: Dict with key:
            - lan_stats (Dict): Raw LAN statistics from config store.
        Returns empty dict if no data, None on error.
    """
    try:
        stats = get('status/lan/stats')
        return {"lan_stats": stats} if stats else {}
    except Exception as e:
        log(f"Error getting LAN stats: {e}")
        return None


def get_lan_device_stats(device_name: str) -> Optional[Dict[str, Any]]:
    """Get statistics for a specific LAN device.

    Returns:
        Optional[Dict[str, Any]]: Raw device statistics dict from
            config store, or None on error.
    """
    try:
        return get(f'status/lan/devices/{device_name}/stats')
    except Exception as e:
        log(f"Error getting stats for {device_name}: {e}")
        return None


# =============================================================================
# GRANULAR STATUS: WAN
# =============================================================================

def get_wan_devices() -> Optional[Dict[str, Any]]:
    """Get WAN device list with basic status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - primary_device (Optional[str]): Primary WAN device UID.
            - devices (List[Dict]): Each with uid, connection_state,
                signal_strength, ip_address, uptime.
        Returns empty dict if no data, None on error.
    """
    try:
        wan_data = get('status/wan')
        if not wan_data:
            return {}
        devices = []
        for uid, info in wan_data.get("devices", {}).items():
            devices.append({
                "uid": uid,
                "connection_state": info.get("status", {}).get("connection_state"),
                "signal_strength": info.get("status", {}).get("signal_strength"),
                "ip_address": info.get("status", {}).get("ipinfo", {}).get("ip_address"),
                "uptime": info.get("status", {}).get("uptime")
            })
        return {"primary_device": wan_data.get("primary_device"), "devices": devices}
    except Exception as e:
        log(f"Error getting WAN devices: {e}")
        return None


def get_wan_modem_diagnostics(device_id: str) -> Optional[Dict[str, Any]]:
    """Get modem diagnostics for a specific WAN device.

    Returns:
        Optional[Dict[str, Any]]: Raw diagnostics dict with keys like
            RSRP, SINR, RFBAND, CELL_ID, etc. None if not a modem
            or on error.
    """
    try:
        if not device_id.startswith("mdm"):
            return None
        return get(f'status/wan/devices/{device_id}/diagnostics')
    except Exception as e:
        log(f"Error getting diagnostics for {device_id}: {e}")
        return None


def get_wan_modem_stats(device_id: str) -> Optional[Dict[str, Any]]:
    """Get modem statistics for a specific WAN device.

    Returns:
        Optional[Dict[str, Any]]: Raw modem stats dict. None if not a
            modem or on error.
    """
    try:
        if not device_id.startswith("mdm"):
            return None
        return get(f'status/wan/devices/{device_id}/stats')
    except Exception as e:
        log(f"Error getting stats for {device_id}: {e}")
        return None


def get_wan_ethernet_info(device_id: str) -> Optional[Dict[str, Any]]:
    """Get ethernet device info for a specific WAN device.

    Returns:
        Optional[Dict[str, Any]]: Raw ethernet info dict. None if not
            an ethernet device or on error.
    """
    try:
        if not device_id.startswith("ethernet"):
            return None
        return get(f'status/wan/devices/{device_id}/info')
    except Exception as e:
        log(f"Error getting ethernet info for {device_id}: {e}")
        return None


def get_wan_devices_status() -> Optional[Dict[str, Any]]:
    """Get raw WAN devices status tree.

    Returns:
        Optional[Dict[str, Any]]: Dict mapping device UIDs to their
            full status trees. None on error.
    """
    try:
        return get('status/wan/devices')
    except Exception as e:
        log(f"Error getting WAN devices status: {e}")
        return None


# =============================================================================
# GRANULAR STATUS: WLAN
# =============================================================================

def get_wlan_status() -> Optional[Dict[str, Any]]:
    """Get comprehensive WLAN status.

    Returns:
        Optional[Dict[str, Any]]: Raw WLAN status tree including state,
            clients, radio info, events. None on error.
    """
    try:
        return get('status/wlan')
    except Exception as e:
        log(f"Error getting WLAN status: {e}")
        return None


def get_wlan_clients() -> List[Dict[str, Any]]:
    """Get connected wireless clients.

    Returns:
        List[Dict[str, Any]]: List of client dicts with keys like mac,
            radio, bss, rssi0, txrate, mode, bw, time. Empty on error.
    """
    try:
        return get('status/wlan/clients') or []
    except Exception as e:
        log(f"Error getting WLAN clients: {e}")
        return []


def get_wlan_radio_status() -> List[Dict[str, Any]]:
    """Get wireless radio status for all bands.

    Returns:
        List[Dict[str, Any]]: List of radio dicts with keys like band,
            channel, channel_list, txpower, clients. Empty on error.
    """
    try:
        return get('status/wlan/radio') or []
    except Exception as e:
        log(f"Error getting WLAN radio status: {e}")
        return []


def get_wlan_radio_by_band(band: str = '2.4 GHz') -> Optional[Dict[str, Any]]:
    """Get radio status for a specific band ('2.4 GHz' or '5 GHz').

    Returns:
        Optional[Dict[str, Any]]: Radio dict with keys like band,
            channel, channel_list, txpower, clients. None if not found.
    """
    try:
        for radio in get_wlan_radio_status():
            if radio.get('band') == band:
                return radio
        return None
    except Exception as e:
        log(f"Error getting radio for band {band}: {e}")
        return None


def get_wlan_state() -> str:
    """Get WLAN operational state ('On', 'Off', etc.).

    Returns:
        str: WLAN state string, or 'Unknown' on error.
    """
    try:
        status = get('status/wlan')
        return status.get('state', 'Unknown') if status else 'Unknown'
    except Exception as e:
        log(f"Error getting WLAN state: {e}")
        return 'Unknown'


def get_wlan_events() -> Dict[str, Any]:
    """Get WLAN events (associate, deauth, disassociate, etc.).

    Returns:
        Dict[str, Any]: Dict of event types to event data.
            Empty dict on error.
    """
    try:
        status = get('status/wlan')
        return status.get('events', {}) if status else {}
    except Exception as e:
        log(f"Error getting WLAN events: {e}")
        return {}


def get_wlan_channel_info(band: Optional[str] = None,
                          include_survey: bool = False) -> Dict[str, Any]:
    """Get channel info for specified band or all bands.

    Returns:
        Dict[str, Any]: If band specified, dict with keys:
            - current_channel (Optional[int]): Active channel.
            - available_channels (List[int]): Allowed channels.
            - channel_locked (bool): Whether channel is locked.
            - txpower (int): Transmit power.
            - survey_data (List): Channel survey (if requested).
        If no band, dict keyed by band name with same structure.
        Empty dict on error.
    """
    try:
        if band:
            radio = get_wlan_radio_by_band(band)
            if not radio:
                return {}
            info = {
                'current_channel': radio.get('channel'),
                'available_channels': radio.get('channel_list', []),
                'channel_locked': radio.get('channel_locked', False),
                'txpower': radio.get('txpower', 0)
            }
            if include_survey:
                info['survey_data'] = radio.get('survey', [])
            return info
        else:
            result = {}
            for radio in get_wlan_radio_status():
                b = radio.get('band', 'Unknown')
                result[b] = {
                    'current_channel': radio.get('channel'),
                    'available_channels': radio.get('channel_list', []),
                    'channel_locked': radio.get('channel_locked', False),
                    'txpower': radio.get('txpower', 0)
                }
                if include_survey:
                    result[b]['survey_data'] = radio.get('survey', [])
            return result
    except Exception as e:
        log(f"Error getting WLAN channel info: {e}")
        return {}


def get_wlan_client_count() -> int:
    """Get count of connected wireless clients.

    Returns:
        int: Number of connected WiFi clients, or 0 on error.
    """
    try:
        return len(get_wlan_clients())
    except Exception as e:
        log(f"Error getting WLAN client count: {e}")
        return 0


def get_wlan_client_count_by_band() -> Dict[str, int]:
    """Get wireless client count per frequency band.

    Returns:
        Dict[str, int]: Mapping of band name (e.g. '2.4 GHz') to
            client count. Empty dict on error.
    """
    try:
        counts = {}
        for radio in get_wlan_radio_status():
            counts[radio.get('band', 'Unknown')] = len(radio.get('clients', []))
        return counts
    except Exception as e:
        log(f"Error getting client count by band: {e}")
        return {}


# =============================================================================
# GRANULAR STATUS: Services, DHCP, DNS, Firewall, VPN, etc.
# =============================================================================

def get_dhcp_status() -> Optional[Dict[str, Any]]:
    """Get DHCP status with lease information.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - total_leases (int): Total lease count.
            - active_leases (int): Non-expired lease count.
            - leases (List[Dict]): Full lease entries.
        Returns empty dict if no data, None on error.
    """
    try:
        dhcp_data = get('status/dhcpd')
        if not dhcp_data:
            return {}
        leases = dhcp_data.get("leases", [])
        current_time = int(time.time())
        active = len([l for l in leases if l.get("expire", 0) > current_time])
        return {
            "total_leases": len(leases),
            "active_leases": active,
            "leases": leases
        }
    except Exception as e:
        log(f"Error getting DHCP status: {e}")
        return None


def get_dhcp_leases() -> Optional[List[Dict[str, Any]]]:
    """Get DHCP lease list.

    Returns:
        Optional[List[Dict[str, Any]]]: List of lease dicts with keys
            like mac, ip_address, hostname, expire, network.
            None on error.
    """
    try:
        return get('status/dhcpd/leases')
    except Exception as e:
        log(f"Error getting DHCP leases: {e}")
        return None


def get_dns_status() -> Optional[Dict[str, Any]]:
    """Get DNS status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - cache_entries (int): Number of cached entries.
            - cache_size (int): Cache size.
            - servers_configured (int): Number of DNS servers.
            - queries_forwarded (int): Forwarded query count.
        Returns empty dict if no data, None on error.
    """
    try:
        dns_data = get('status/dns')
        if not dns_data:
            return {}
        cache = dns_data.get("cache", {})
        return {
            "cache_entries": len(cache.get("entries", [])),
            "cache_size": cache.get("size", 0),
            "servers_configured": len(cache.get("servers", [])),
            "queries_forwarded": cache.get("forwarded", 0)
        }
    except Exception as e:
        log(f"Error getting DNS status: {e}")
        return None


def get_firewall_status() -> Optional[Dict[str, Any]]:
    """Get firewall status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - connections_tracked (int): Active connection count.
            - state_timeouts (Dict): Timeout settings per state.
            - hitcounters (List): Rule hit counter entries.
        Returns empty dict if no data, None on error.
    """
    try:
        fw = get('status/firewall')
        if not fw:
            return {}
        return {
            "connections_tracked": len(fw.get("connections", [])),
            "state_timeouts": fw.get("state_timeouts", {}),
            "hitcounters": fw.get("hitcounter", [])
        }
    except Exception as e:
        log(f"Error getting firewall status: {e}")
        return None


def get_openvpn_status() -> Optional[Dict[str, Any]]:
    """Get OpenVPN status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - tunnels_configured (int): Total tunnel count.
            - tunnels_active (int): Tunnels with status 'up'.
            - stats_available (bool): Whether stats data exists.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/openvpn')
        if not data:
            return {}
        tunnels = data.get("tunnels", [])
        return {
            "tunnels_configured": len(tunnels),
            "tunnels_active": len([t for t in tunnels if t.get("status") == "up"]),
            "stats_available": bool(data.get("stats"))
        }
    except Exception as e:
        log(f"Error getting OpenVPN status: {e}")
        return None


def get_hotspot_status() -> Optional[Dict[str, Any]]:
    """Get hotspot status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - clients_connected (int): Connected client count.
            - sessions_active (int): Active session count.
            - domains_allowed (int): Allowed domain count.
            - hosts_allowed (int): Allowed host count.
            - rate_limit_triggered (bool): Whether rate limit is active.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/hotspot')
        if not data:
            return {}
        return {
            "clients_connected": len(data.get("clients", {})),
            "sessions_active": len(data.get("sessions", {})),
            "domains_allowed": len(data.get("allowed", {}).get("domains", [])),
            "hosts_allowed": len(data.get("allowed", {}).get("hosts", {})),
            "rate_limit_triggered": data.get("rateLimitTrigger", False)
        }
    except Exception as e:
        log(f"Error getting hotspot status: {e}")
        return None


def get_qos_status() -> Optional[Dict[str, Any]]:
    """Get QoS status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - qos_enabled (bool): Whether QoS is enabled.
            - queues_configured (int): Total queue count.
            - queues_active (int): Queues with traffic.
            - total_packets (int): Sum of all queue packets.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/qos')
        if not data:
            return {}
        queues = data.get("queues", [])
        return {
            "qos_enabled": data.get("enabled", False),
            "queues_configured": len(queues),
            "queues_active": len([q for q in queues
                                  if q.get("ipkts", 0) > 0 or q.get("opkts", 0) > 0]),
            "total_packets": sum(q.get("ipkts", 0) + q.get("opkts", 0) for q in queues)
        }
    except Exception as e:
        log(f"Error getting QoS status: {e}")
        return None


def get_obd_status() -> Optional[Dict[str, Any]]:
    """Get OBD (vehicle diagnostics) status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - adapter_configured (bool): OBD adapter configured.
            - adapter_connected (bool): OBD adapter connected.
            - vehicle_connected (bool): Vehicle connection active.
            - pids_supported (int): Supported PID count.
            - pids_enabled (int): Enabled PID count.
            - ignition_status (Optional[str]): Ignition state.
            - pids (List[Dict]): PID entries.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/obd')
        if not data:
            return {}
        adapter = data.get("adapter", {})
        vehicle = data.get("vehicle", {})
        pids = data.get("pids", [])
        return {
            "adapter_configured": adapter.get("configured", False),
            "adapter_connected": adapter.get("connected", False),
            "vehicle_connected": vehicle.get("ext_tool") != "Disconnected",
            "pids_supported": len([p for p in pids if p.get("supported")]),
            "pids_enabled": len([p for p in pids if p.get("enabled")]),
            "ignition_status": vehicle.get("ign_status"),
            "pids": pids
        }
    except Exception as e:
        log(f"Error getting OBD status: {e}")
        return None


def get_vpn_status() -> Optional[Dict[str, Any]]:
    """Get combined VPN status (OpenVPN, L2TP, GRE, VXLAN).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - openvpn (Optional[Dict]): OpenVPN status summary.
            - l2tp (Any): Raw L2TP status.
            - gre (Any): Raw GRE status.
            - vxlan (Any): Raw VXLAN status.
        Returns None on error.
    """
    try:
        return {
            'openvpn': get_openvpn_status(),
            'l2tp': get('status/l2tp'),
            'gre': get('status/gre'),
            'vxlan': get('status/vxlan')
        }
    except Exception as e:
        log(f"Error getting VPN status: {e}")
        return None


def get_services_status() -> Optional[Dict[str, Any]]:
    """Get system services status.

    Returns:
        Optional[Dict[str, Any]]: Dict mapping service names to their
            state dicts (with 'state' key). None on error.
    """
    try:
        return get('status/system/services')
    except Exception as e:
        log(f"Error getting services status: {e}")
        return None


def get_apps_status() -> Optional[Dict[str, Any]]:
    """Get internal and external (SDK) app status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - internal_apps (List): Internal app entries.
            - external_apps (List): SDK app entries.
            - total_apps (int): Combined app count.
            - running_apps (int): Apps with state 'started'.
        Returns None on error.
    """
    try:
        internal = get('status/system/apps') or []
        sdk = get('status/system/sdk') or {}
        external = sdk.get('apps', [])
        return {
            'internal_apps': internal,
            'external_apps': external,
            'total_apps': len(internal) + len(external),
            'running_apps': (
                len([a for a in internal if a.get('state') == 'started']) +
                len([a for a in external if a.get('state') == 'started'])
            )
        }
    except Exception as e:
        log(f"Error getting apps status: {e}")
        return None


def get_routing_table() -> Optional[Dict[str, Any]]:
    """Get routing table information.

    Returns:
        Optional[Dict[str, Any]]: Raw routing status tree from config
            store. None on error.
    """
    try:
        return get('status/routing')
    except Exception as e:
        log(f"Error getting routing table: {e}")
        return None


def get_certificate_status() -> Optional[Dict[str, Any]]:
    """Get certificate management status.

    Returns:
        Optional[Dict[str, Any]]: Raw certificate management status
            tree. None on error.
    """
    try:
        return get('status/certmgmt')
    except Exception as e:
        log(f"Error getting certificate status: {e}")
        return None


def get_sdwan_status() -> Optional[Dict[str, Any]]:
    """Get SD-WAN advanced status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - forward_error_correction (Dict): FEC status.
            - link_monitoring (Dict): Link monitoring data.
            - quality_of_experience (Dict): QoE metrics.
            - user_mode_driver (Dict): UMD status.
            - wan_bonding (Dict): WAN bonding status.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/sdwan_adv')
        if not data:
            return {}
        return {
            "forward_error_correction": data.get("forward_error_correction", {}),
            "link_monitoring": data.get("link_mon", {}),
            "quality_of_experience": data.get("qoe", {}),
            "user_mode_driver": data.get("user_mode_driver", {}),
            "wan_bonding": data.get("wan_bonding", {})
        }
    except Exception as e:
        log(f"Error getting SD-WAN status: {e}")
        return None


def get_flow_statistics() -> Optional[Dict[str, Any]]:
    """Get flow statistics with destination info.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - total_destinations (int): Unique destination count.
            - total_packets (int): Total packet count.
            - destinations (List): Destination entries.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/flowstats')
        if not data:
            return {}
        ipdst = data.get("ipdst", {})
        return {
            "total_destinations": ipdst.get("totaldsts", 0),
            "total_packets": ipdst.get("totalpkts", 0),
            "destinations": ipdst.get("destinations", [])
        }
    except Exception as e:
        log(f"Error getting flow statistics: {e}")
        return None


def get_client_usage() -> Optional[Dict[str, Any]]:
    """Get client usage statistics with bandwidth info.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - enabled (bool): Whether client usage tracking is on.
            - total_clients (int): Number of tracked clients.
            - total_traffic (Dict): Aggregate traffic with keys:
                - down_bytes (int): Total download bytes.
                - up_bytes (int): Total upload bytes.
                - total_bytes (int): Combined bytes.
            - stats (List[Dict]): Per-client usage entries.
        Returns empty dict if no data, None on error.
    """
    try:
        data = get('status/client_usage')
        if not data:
            return {}
        stats = data.get("stats", [])
        total_down = sum(c.get("down_bytes", 0) for c in stats)
        total_up = sum(c.get("up_bytes", 0) for c in stats)
        return {
            "enabled": data.get("enabled", False),
            "total_clients": len(stats),
            "total_traffic": {
                "down_bytes": total_down,
                "up_bytes": total_up,
                "total_bytes": total_down + total_up
            },
            "stats": stats
        }
    except Exception as e:
        log(f"Error getting client usage: {e}")
        return None


def get_power_usage(include_components: bool = True) -> Optional[Dict[str, Any]]:
    """Get power usage information.

    Returns:
        Optional[Dict[str, Any]]: Dict with component keys (if requested):
            - system_power, cpu_power, modem_power, wifi_power,
              poe_pse_power, ethernet_ports_power, bluetooth_power,
              usb_power, gps_power, led_power (each Optional[Any]).
            - total (Optional[Any]): Total power usage.
        Returns None on error.
    """
    try:
        result = {}
        if include_components:
            components = ['system_power', 'cpu_power', 'modem_power', 'wifi_power',
                          'poe_pse_power', 'ethernet_ports_power', 'bluetooth_power',
                          'usb_power', 'gps_power', 'led_power']
            for comp in components:
                try:
                    result[comp] = get(f'status/power_usage/{comp}')
                except Exception:
                    result[comp] = None
        try:
            result['total'] = get('status/power_usage/total')
        except Exception:
            result['total'] = None
        return result
    except Exception as e:
        log(f"Error getting power usage: {e}")
        return None


def get_storage_status() -> Optional[Dict[str, Any]]:
    """Get storage health status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - health (Any): Storage health data.
            - slc_health (Any): SLC storage health data.
        Returns None on error.
    """
    try:
        return {
            'health': get('status/system/storage/health'),
            'slc_health': get('status/system/storage/slc_health')
        }
    except Exception as e:
        log(f"Error getting storage status: {e}")
        return None


def get_sensors_status() -> Optional[Dict[str, Any]]:
    """Get sensor status (level, day).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - level (Any): Level sensor data.
            - day (Any): Day sensor data.
        Returns None on error.
    """
    try:
        return {
            'level': get('status/system/sensors/level'),
            'day': get('status/system/sensors/day')
        }
    except Exception as e:
        log(f"Error getting sensors: {e}")
        return None


def get_iot_status() -> Optional[Dict[str, Any]]:
    """Get IoT status.

    Returns:
        Optional[Dict[str, Any]]: Raw IoT status tree from config store.
            None on error.
    """
    try:
        return get('status/iot')
    except Exception as e:
        log(f"Error getting IoT status: {e}")
        return None


def get_event_status() -> Optional[Dict[str, Any]]:
    """Get system events status.

    Returns:
        Optional[Dict[str, Any]]: Raw event status tree from config
            store. None on error.
    """
    try:
        return get('status/event')
    except Exception as e:
        log(f"Error getting event status: {e}")
        return None


def get_description() -> Optional[str]:
    """Get device description.

    Returns:
        Optional[str]: Device description string, or None on error.
    """
    try:
        return get('config/system/desc')
    except Exception as e:
        log(f"Error getting description: {e}")
        return None


def get_asset_id() -> Optional[str]:
    """Get device asset ID.

    Returns:
        Optional[str]: Asset ID string, or None on error.
    """
    try:
        return get('config/system/asset_id')
    except Exception as e:
        log(f"Error getting asset ID: {e}")
        return None


# =============================================================================
# SPEED TEST (netperf-based)
# =============================================================================

def speed_test(host: str = "", interface: str = "", duration: int = 5,
               packet_size: int = 0, protocol: str = "tcp",
               direction: str = "both") -> Optional[Dict[str, Any]]:
    """Perform network speed test using router's netperf.

    Args:
        host: Target host (empty for auto-detect).
        interface: Network interface (empty for auto-detect via primary WAN).
        duration: Test duration in seconds.
        packet_size: Packet size (0 for default).
        protocol: 'tcp' or 'udp'.
        direction: 'recv', 'send', or 'both'.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - download_bps (float): Download speed in bits/sec.
            - upload_bps (float): Upload speed in bits/sec.
            - latency_ms (float): Latency in milliseconds.
            - test_duration (int): Test duration used.
            - interface (str): Interface tested on.
            - host (str): Target host.
            - protocol (str): Protocol used.
        Returns None on failure.
    """
    try:
        if not interface:
            primary = get_wan_primary_device()
            if primary:
                interface = get(f'status/wan/devices/{primary}/info/iface') or "any"
            else:
                interface = "any"

        results = {
            'download_bps': 0, 'upload_bps': 0, 'latency_ms': 0,
            'test_duration': duration, 'interface': interface,
            'host': host, 'protocol': protocol
        }

        params = {
            "input": {
                "options": {
                    "limit": {"size": packet_size, "time": duration},
                    "port": None, "fwport": None, "host": host,
                    "ifc_wan": interface,
                    "tcp": protocol == "tcp", "udp": protocol == "udp",
                    "send": False, "recv": True, "rr": False
                },
                "tests": None
            },
            "run": 1
        }

        put('/state/system/netperf', {"run_count": 0})
        time.sleep(1)

        def _run_test(p):
            put('control/netperf', p)
            for _ in range(duration + 10):
                out = get('control/netperf/output')
                if out and out.get('status') in ('complete', 'error'):
                    if out.get('results_path'):
                        return get(out['results_path'].lstrip('/'))
                    return None
                time.sleep(1)
            return None

        if direction in ("recv", "both"):
            dl = _run_test(params)
            if dl and 'tcp_down' in dl:
                tp = dl['tcp_down']
                if tp and 'THROUGHPUT' in tp:
                    results['download_bps'] = _convert_throughput(
                        float(tp['THROUGHPUT']), tp.get('THROUGHPUT_UNITS', ''))

            if direction == "both":
                time.sleep(3)

        if direction in ("send", "both"):
            put('/state/system/netperf', {"run_count": 0})
            time.sleep(1)
            params["input"]["options"]["send"] = True
            params["input"]["options"]["recv"] = False
            ul = _run_test(params)
            if ul and 'tcp_up' in ul:
                tp = ul['tcp_up']
                if tp and 'THROUGHPUT' in tp:
                    results['upload_bps'] = _convert_throughput(
                        float(tp['THROUGHPUT']), tp.get('THROUGHPUT_UNITS', ''))

        return results
    except Exception as e:
        log(f"Error in speed test: {e}")
        return None


def stop_speed_test() -> Optional[Dict[str, Any]]:
    """Stop any running speed test.

    Returns:
        Optional[Dict[str, Any]]: Config store response dict, or None
            on error.
    """
    try:
        return put('control/netperf/stop', '')
    except Exception as e:
        log(f"Error stopping speed test: {e}")
        return None


def _convert_throughput(value: float, units: str) -> float:
    """Convert throughput to bits per second.

    Returns:
        float: Throughput value converted to bits per second.
    """
    if '10^6bits/s' in units:
        return value * 1000000
    elif 'bytes/s' in units:
        return value * 8
    return value


# =============================================================================
# USER MANAGEMENT
# =============================================================================

def create_user(username: str, password: str, group: str = "admin") -> Dict[str, Any]:
    """Create a new user on the router.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether creation succeeded.
            - username (str): The username.
            - group (str): The group assigned.
            - result (Any): Raw config store response (on success).
            - error (str): Error message (on failure).
    """
    try:
        result = post('config/system/users/', {
            "group": group, "password": password, "username": username
        })
        return {'success': True, 'username': username, 'group': group, 'result': result}
    except Exception as e:
        return {'success': False, 'error': str(e), 'username': username}


def get_users() -> Dict[str, Any]:
    """Get list of all users.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether retrieval succeeded.
            - users (List[Dict]): User entries (on success), each with
                username, group, _id_.
            - error (str): Error message (on failure).
    """
    try:
        result = get('config/system/users/')
        return {'success': True, 'users': result}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_user(username: str) -> Dict[str, Any]:
    """Delete a user by username.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether deletion succeeded.
            - username (str): The username.
            - result (Any): Raw config store response (on success).
            - error (str): Error message (on failure).
    """
    try:
        users_result = get_users()
        if not users_result.get('success'):
            return users_result

        users = users_result.get('users', [])
        if isinstance(users, list):
            for user in users:
                if isinstance(user, dict) and user.get('username') == username:
                    user_id = user.get('_id_')
                    result = delete(f'config/system/users/{user_id}')
                    return {'success': True, 'username': username, 'result': result}

        return {'success': False, 'error': f'User {username} not found'}
    except Exception as e:
        return {'success': False, 'error': str(e), 'username': username}


def ensure_user_exists(username: str, password: str,
                       group: str = "admin") -> Dict[str, Any]:
    """Ensure a user exists, creating if needed.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether the user exists/was created.
            - username (str): The username.
            - action (str): 'exists' or 'created'.
            - error (str): Error message (on failure).
    """
    try:
        users_result = get_users()
        if users_result.get('success'):
            users = users_result.get('users', [])
            if isinstance(users, list):
                for user in users:
                    if isinstance(user, dict) and user.get('username') == username:
                        return {'success': True, 'username': username, 'action': 'exists'}
        result = create_user(username, password, group)
        if result.get('success'):
            result['action'] = 'created'
        return result
    except Exception as e:
        return {'success': False, 'error': str(e), 'username': username}


def ensure_fresh_user(username: str, group: str = "admin") -> Dict[str, Any]:
    """Delete existing user and recreate with random password.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether creation succeeded.
            - username (str): The username.
            - password (str): Generated random password (on success).
            - action (str): 'created_fresh' (on success).
            - error (str): Error message (on failure).
    """
    try:
        import random as _rand
        delete_user(username)
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(_rand.choice(chars) for _ in range(16))
        result = create_user(username, password, group)
        result['password'] = password
        result['action'] = 'created_fresh'
        return result
    except Exception as e:
        return {'success': False, 'error': str(e), 'username': username}


def validate_password(username: str, password: str) -> Dict[str, Any]:
    """Validate a plaintext password against the stored hash for a user.

    Supports NCOS password hash format:
        $3$iterations$salt$key_b64 - PBKDF2-HMAC-SHA256

    The salt field is used as raw ASCII bytes (not base64-decoded).
    The key field is base64-encoded.

    Note: The REST API (local dev mode) returns a masked $0$ hash that
    cannot be validated. This function works reliably on-router where
    cp.get() returns the real $3$ hash via the SDK socket.

    Args:
        username: The username to validate.
        password: The plaintext password to check.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether the operation completed.
            - valid (bool): Whether the password matches (on success).
            - username (str): The username checked.
            - error (str): Error message (on failure).
    """
    try:
        users_result = get_users()
        if not users_result.get('success'):
            return {'success': False, 'error': 'Failed to retrieve users',
                    'username': username}

        users = users_result.get('users', [])
        stored_hash = None
        if isinstance(users, list):
            for user in users:
                if isinstance(user, dict) and user.get('username') == username:
                    stored_hash = user.get('password', '')
                    break

        if stored_hash is None:
            return {'success': False, 'error': f'User {username} not found',
                    'username': username}

        # Parse hash format: $algo$[iterations$]salt_b64$key_b64
        parts = stored_hash.split('$')
        # parts[0] is always empty string before first $
        algo = parts[1] if len(parts) > 1 else ''

        if algo == '0' and len(parts) == 4:
            # $0$ is a masked/encrypted format returned by the REST API.
            # It cannot be validated — only the real $3$ hash (from the
            # SDK socket on-router) supports local validation.
            return {'success': False,
                    'error': 'Cannot validate $0$ hash (REST API returns '
                             'masked passwords). Run on-router for real '
                             'hash validation.',
                    'username': username}
        elif algo == '3' and len(parts) == 5:
            # $3$iterations$salt$key_b64 — PBKDF2-HMAC-SHA256
            hash_algo = 'sha256'
            iterations = int(parts[2])
            salt_str = parts[3]
            expected_key_b64 = parts[4]
        else:
            return {'success': False,
                    'error': f'Unsupported hash format (algo=${algo}$, '
                             f'{len(parts)} parts)',
                    'username': username}

        # Salt is used as raw ASCII string bytes, not base64-decoded
        salt_bytes = salt_str.encode('utf-8')
        expected_key = base64.b64decode(expected_key_b64)

        derived_key = hashlib.pbkdf2_hmac(
            hash_algo,
            password.encode('utf-8'),
            salt_bytes,
            iterations,
            dklen=len(expected_key)
        )

        valid = hmac.compare_digest(derived_key, expected_key)
        return {'success': True, 'valid': valid, 'username': username}

    except Exception as e:
        return {'success': False, 'error': str(e), 'username': username}


# =============================================================================
# LOG MONITORING & SMS
# =============================================================================

def monitor_log(pattern: Optional[str] = None, callback: Optional[Callable] = None,
                follow: bool = True, max_lines: int = 0,
                timeout: int = 0) -> Optional[Dict[str, Any]]:
    """Monitor /var/log/messages with optional pattern matching and callback.

    Runs in a background thread. Returns control info for stopping.

    Args:
        pattern: Regex pattern to filter lines (None = all lines).
        callback: Function called with each matching line.
        follow: Tail -f behavior.
        max_lines: Max lines to process (0 = unlimited).
        timeout: Timeout in seconds (0 = no timeout).

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): Whether monitoring started.
            - thread_id (int): Background thread ID (on success).
            - stop_event (threading.Event): Set to stop monitoring.
            - line_queue (Queue): Lines queued if no callback given.
            - error (str): Error message (on failure).
    """
    from subprocess import Popen, PIPE
    from queue import Queue

    try:
        log_file = '/var/log/messages'
        if not os.path.exists(log_file):
            return {'success': False, 'error': f'{log_file} not found'}

        compiled = re.compile(pattern) if pattern else None
        stop_event = threading.Event()
        line_queue = Queue()

        def worker():
            try:
                cmd = ['/usr/bin/tail']
                if follow:
                    cmd.append('-F')
                if max_lines > 0:
                    cmd.extend(['-n', str(max_lines)])
                cmd.append(log_file)

                proc = Popen(cmd, stdout=PIPE, stderr=PIPE,
                             bufsize=1, universal_newlines=True)
                start = time.time()
                count = 0

                for line in iter(proc.stdout.readline, ''):
                    if stop_event.is_set():
                        break
                    if timeout > 0 and (time.time() - start) > timeout:
                        break
                    if max_lines > 0 and count >= max_lines:
                        break

                    line = line.rstrip('\n\r')
                    if not line:
                        continue
                    count += 1

                    if compiled and not compiled.search(line):
                        continue

                    if callback:
                        try:
                            callback(line)
                        except Exception as e:
                            log(f"Monitor callback error: {e}")
                    else:
                        line_queue.put(line)

                proc.terminate()
                proc.wait(timeout=5)
            except Exception as e:
                log(f"Monitor worker error: {e}")
            finally:
                line_queue.put(None)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        return {
            'success': True,
            'thread_id': t.ident,
            'stop_event': stop_event,
            'line_queue': line_queue
        }
    except Exception as e:
        log(f"Error starting monitor_log: {e}")
        return {'success': False, 'error': str(e)}


def stop_monitor_log(monitor_result: Dict[str, Any]) -> Dict[str, Any]:
    """Stop a running monitor_log operation.

    Returns:
        Dict[str, Any]: Dict with keys:
            - success (bool): Whether stop succeeded.
            - stopped (bool): True if event was set (on success).
            - error (str): Error message (on failure).
    """
    try:
        if not monitor_result or not monitor_result.get('success'):
            return {'success': False, 'error': 'Invalid monitor result'}
        stop_event = monitor_result.get('stop_event')
        if stop_event:
            stop_event.set()
            return {'success': True, 'stopped': True}
        return {'success': False, 'error': 'No stop_event found'}
    except Exception as e:
        log(f"Error stopping monitor: {e}")
        return {'success': False, 'error': str(e)}


def monitor_sms(callback: Callable, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """Monitor for SMS messages and parse phone/message to callback.

    Callback signature: callback(phone_number, message, raw_line)

    Returns:
        Optional[Dict[str, Any]]: Same as monitor_log() return value.
            Dict with success, stop_event, line_queue, thread_id.
    """
    def sms_parser(raw_line: str):
        try:
            if "SMS received:" in raw_line:
                sms_part = raw_line.split("SMS received:", 1)[1].strip()
                parts = sms_part.split()
                if len(parts) >= 2:
                    callback(parts[-1], " ".join(parts[:-1]), raw_line)
                else:
                    callback("unknown", sms_part, raw_line)
        except Exception as e:
            log(f"SMS parse error: {e}")

    return monitor_log(pattern="SMS received:", callback=sms_parser, timeout=timeout)


def stop_monitor_sms(monitor_result: Dict[str, Any]) -> Dict[str, Any]:
    """Stop a running SMS monitor.

    Returns:
        Dict[str, Any]: Same as stop_monitor_log() return value.
    """
    return stop_monitor_log(monitor_result)


def send_sms(phone_number: str, message: str,
             port: Optional[str] = None) -> Optional[str]:
    """Send an SMS message via CLI.

    Args:
        phone_number: Destination phone number.
        message: Message text.
        port: Modem port (auto-detected if None).

    Returns:
        Optional[str]: CLI output string from the send command,
            or None on error.
    """
    try:
        if not phone_number or not message:
            log("phone_number and message are required for send_sms")
            return None

        if port is None:
            devices = get('status/wan/devices') or {}
            for uid, info in devices.items():
                if uid.startswith('mdm-'):
                    dev_info = get(f'status/wan/devices/{uid}/info')
                    if dev_info and dev_info.get('connected'):
                        port = dev_info.get('port')
                        break
            if not port:
                log("No connected modem found for SMS")
                return None

        return execute_cli(f'sms {phone_number} "{message}" {port}')
    except Exception as e:
        log(f"Error sending SMS: {e}")
        return None


# =============================================================================
# PACKET CAPTURE
# =============================================================================

def start_packet_capture(interface: str = "any", filter_expr: str = "",
                         count: int = 20, timeout: int = 600,
                         url: str = "", filename: str = "") -> Optional[Dict[str, Any]]:
    """Start packet capture using tcpdump API.

    Args:
        interface: Network interface (e.g. 'any', 'mdm-xxx', 'mon0').
        filter_expr: BPF filter expression.
        count: Number of packets (0 = unlimited).
        timeout: Capture timeout in seconds (0 = unlimited).
        url: Upload URL (CloudShark or custom endpoint).
        filename: Optional pcap filename. Auto-generated if empty.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - filename (str): Generated pcap filename.
            - parameters (Dict): Capture parameters used.
            - api_url (str): API URL for the capture.
            - capture_result (Any): Response from config store.
        Returns None on error.
    """
    try:
        from datetime import datetime as _dt
        if not filename:
            timestamp = _dt.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}.pcap"

        params = {
            "iface": interface, "args": filter_expr,
            "wifichannel": "", "wifichannelwidth": "",
            "wifiextrachannel": "", "timeout": timeout,
            "count": count, "url": url
        }

        query = urllib.parse.urlencode(params)
        api_url = f"tcpdump/{filename}?{query}"
        capture_result = get(api_url)

        return {
            'filename': filename,
            'parameters': params,
            'api_url': api_url,
            'capture_result': capture_result
        }
    except Exception as e:
        log(f"Error starting packet capture: {e}")
        return None


def stop_packet_capture() -> Dict[str, Any]:
    """Stop packet capture (informational - captures stop via timeout/count).

    Returns:
        Dict[str, Any]: Dict with keys:
            - message (str): Informational message.
            - suggestion (str): Usage guidance.
    """
    return {
        'message': 'Captures are controlled by timeout and count parameters',
        'suggestion': 'Use shorter timeout or lower count for shorter captures'
    }


def download_packet_capture(filename: str, local_path: Optional[str] = None,
                            capture_params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """Download a captured pcap file.

    Args:
        filename: Pcap filename.
        local_path: Local save path (default: current directory).
        capture_params: Original capture parameters for URL construction.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - filename (str): Pcap filename.
            - local_path (str): Where file was saved.
            - file_size (int): Downloaded file size in bytes.
            - success (bool): True on success.
        Returns None on error.
    """
    try:
        if not local_path:
            local_path = f"./{filename}"

        device_ip, username, password = _get_credentials()

        if capture_params:
            params = urllib.parse.urlencode(capture_params)
            url = f"http://{device_ip}/api/tcpdump/{filename}?{params}"
        else:
            url = f"http://{device_ip}/api/tcpdump/{filename}"

        pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwd_mgr.add_password(None, f"http://{device_ip}", username, password)
        handler = urllib.request.HTTPBasicAuthHandler(pwd_mgr)
        opener = urllib.request.build_opener(handler)
        urllib.request.install_opener(opener)

        urllib.request.urlretrieve(url, local_path)
        file_size = os.path.getsize(local_path)

        return {
            'filename': filename,
            'local_path': local_path,
            'file_size': file_size,
            'success': True
        }
    except Exception as e:
        log(f"Error downloading capture: {e}")
        return None


# =============================================================================
# FILE SERVER
# =============================================================================

def start_file_server(folder_path: str = "files", port: int = 8000,
                      host: str = "0.0.0.0",
                      title: str = "File Download") -> Optional[Dict[str, Any]]:
    """Start a web file server with custom UI for downloading files.

    Serves a responsive HTML page listing files with metadata, sorted
    by modification time (newest first). Individual files are served
    for download. Mobile-friendly layout.

    Args:
        folder_path: Relative path to serve files from.
        port: Port number (default 8000).
        host: Bind address (default all interfaces).
        title: Page title shown in the UI.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - status (str): 'started'.
            - url (str): Server URL (e.g. 'http://0.0.0.0:8000').
            - folder_path (str): Absolute path being served.
            - port (int): Port number.
        Returns None on error.
    """
    import http.server
    import socketserver
    import mimetypes
    from datetime import datetime as _dt

    try:
        if os.path.isabs(folder_path):
            folder_path = os.path.basename(folder_path)

        full_path = os.path.join(os.getcwd(), folder_path)
        os.makedirs(full_path, exist_ok=True)

        def _format_size(size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"

        def _build_html(files, total_size):
            file_count = len(files)
            total_human = _format_size(total_size)
            html = (
                '<!DOCTYPE html><html lang="en"><head>'
                '<meta charset="UTF-8">'
                '<meta name="viewport" '
                'content="width=device-width,initial-scale=1.0">'
                f'<title>{title}</title><style>'
                '*{margin:0;padding:0;box-sizing:border-box}'
                'body{font-family:-apple-system,BlinkMacSystemFont,'
                "'Segoe UI',Roboto,sans-serif;background:#fff;"
                'color:#1a1a1a;line-height:1.6;min-height:100vh}'
                '.header{background:#fff;border-bottom:1px solid '
                '#e5e5e5;padding:2rem;text-align:center}'
                '.header h1{font-size:2.5rem;font-weight:600;'
                'color:#1a1a1a;margin-bottom:.5rem}'
                '.header p{color:#666;font-size:1.1rem;'
                'margin-bottom:2rem}'
                '.stats{display:flex;justify-content:center;'
                'gap:2rem;flex-wrap:wrap}'
                '.stat{background:#f8f9fa;border:1px solid #e5e5e5;'
                'padding:1rem 1.5rem;border-radius:6px;'
                'color:#1a1a1a;font-weight:500}'
                '.container{max-width:1000px;margin:0 auto;'
                'background:#fff}'
                '.content{padding:2rem}'
                '.file-list{display:grid;gap:1rem}'
                '.file-item{display:flex;align-items:center;'
                'padding:1.5rem;background:#fff;border:1px solid '
                '#e5e5e5;border-radius:8px;transition:all .2s ease}'
                '.file-item:hover{border-color:#0066cc;'
                'box-shadow:0 4px 12px rgba(0,102,204,.1);'
                'transform:translateY(-1px)}'
                '.file-icon{width:48px;height:48px;background:'
                '#f8f9fa;border:1px solid #e5e5e5;border-radius:6px;'
                'display:flex;align-items:center;'
                'justify-content:center;color:#666;font-size:1.2rem;'
                'margin-right:1rem;flex-shrink:0}'
                '.file-info{flex:1}'
                '.file-name{font-size:1.1rem;font-weight:600;'
                'color:#1a1a1a;margin-bottom:.25rem;'
                'word-break:break-all}'
                '.file-meta{color:#666;font-size:.9rem;display:flex;'
                'gap:1rem;flex-wrap:wrap}'
                '.download-btn{background:#0066cc;color:#fff;'
                'padding:.75rem 1.5rem;border:none;border-radius:6px;'
                'text-decoration:none;font-weight:500;font-size:.9rem;'
                'transition:all .2s ease;display:inline-block}'
                '.download-btn:hover{background:#0052a3;'
                'transform:translateY(-1px)}'
                '.empty{text-align:center;padding:4rem 2rem;'
                'color:#666}'
                '.empty h3{font-size:1.5rem;font-weight:600;'
                'color:#1a1a1a;margin-bottom:.5rem}'
                '@media(max-width:768px){'
                '.header{padding:1.5rem 1rem}'
                '.header h1{font-size:2rem}'
                '.content{padding:1rem}'
                '.file-item{flex-direction:column;text-align:center}'
                '.file-icon{margin:0 0 1rem 0}'
                '.file-meta{justify-content:center}'
                '.stats{flex-direction:column;align-items:center;'
                'gap:1rem}}'
                '</style></head><body><div class="container">'
                '<div class="header">'
                f'<h1>{title}</h1>'
                '<p>Download files from the server</p>'
                '<div class="stats">'
                f'<div class="stat">{file_count} files</div>'
                f'<div class="stat">{total_human}</div>'
                '</div></div><div class="content">'
            )
            if files:
                html += '<div class="file-list">'
                for f in files:
                    html += (
                        '<div class="file-item">'
                        '<div class="file-icon">\U0001f4c4</div>'
                        '<div class="file-info">'
                        f'<div class="file-name">{f["name"]}</div>'
                        '<div class="file-meta">'
                        f'<span>\U0001f4c5 {f["modified"]}</span>'
                        f'<span>\U0001f4cf {f["size_human"]}</span>'
                        f'<span>\U0001f3f7\ufe0f {f["type"]}</span>'
                        '</div></div>'
                        f'<a href="{f["name"]}" class="download-btn"'
                        ' download>\u2b07\ufe0f Download</a>'
                        '</div>'
                    )
                html += '</div>'
            else:
                html += (
                    '<div class="empty">'
                    '<h3>No files found</h3>'
                    f'<p>Add files to <code>{folder_path}</code>'
                    ' to see them here.</p></div>'
                )
            html += '</div></div></body></html>'
            return html

        class FileHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=full_path, **kwargs)

            def do_GET(self):
                if self.path == '/':
                    self._send_listing()
                else:
                    super().do_GET()

            def _send_listing(self):
                try:
                    files = []
                    total_size = 0
                    for item in os.listdir(full_path):
                        item_path = os.path.join(full_path, item)
                        if os.path.isfile(item_path):
                            st = os.stat(item_path)
                            mtime = _dt.fromtimestamp(st.st_mtime)
                            files.append({
                                'name': item,
                                'size': st.st_size,
                                'size_human': _format_size(st.st_size),
                                'modified': mtime.strftime(
                                    '%Y-%m-%d %H:%M:%S'),
                                'type': (mimetypes.guess_type(item)[0]
                                         or 'application/octet-stream')
                            })
                            total_size += st.st_size
                    files.sort(
                        key=lambda x: x['modified'], reverse=True)
                    html = _build_html(files, total_size)
                    encoded = html.encode('utf-8')
                    self.send_response(200)
                    self.send_header(
                        'Content-type', 'text/html; charset=utf-8')
                    self.send_header(
                        'Content-Length', str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                except Exception as e:
                    self.send_error(500, f"Error: {e}")

            def log_message(self, fmt, *args):
                log(f"FileServer: {fmt % args}")

        def run():
            try:
                with socketserver.TCPServer(
                        (host, port), FileHandler) as httpd:
                    httpd.socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    httpd.serve_forever()
            except Exception as e:
                log(f"File server error: {e}")

        t = threading.Thread(target=run, daemon=True)
        t.start()

        url = f'http://{host}:{port}'
        log(f"File server started on {url} serving {full_path}")

        return {
            'status': 'started', 'url': url,
            'folder_path': full_path, 'port': port
        }
    except Exception as e:
        log(f"Error starting file server: {e}")
        return None


# =============================================================================
# WAN PROFILE EXTRAS
# =============================================================================

def set_wan_device_default_connection_state(device_id: str,
                                            connection_state: str) -> bool:
    """Set default connection state for a WAN device.

    Args:
        device_id: WAN device UID.
        connection_state: 'alwayson', 'auto', 'ondemand', or 'disabled'.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        profile = get_wan_device_profile(device_id)
        if not profile:
            return False
        result = put(
            f'config/wan/rules2/{profile["_id_"]}/def_conn_state', connection_state)
        return result is not None
    except Exception as e:
        log(f"Error setting connection state for {device_id}: {e}")
        return False


def set_wan_device_bandwidth(device_id: str, ingress_kbps: Optional[int] = None,
                             egress_kbps: Optional[int] = None) -> bool:
    """Set bandwidth limits for a WAN device.

    Returns:
        bool: True if all requested updates succeeded, False otherwise.
    """
    try:
        profile = get_wan_device_profile(device_id)
        if not profile:
            return False
        pid = profile["_id_"]
        ok = True
        if ingress_kbps is not None:
            if not put(f'config/wan/rules2/{pid}/bandwidth_ingress', ingress_kbps):
                ok = False
        if egress_kbps is not None:
            if not put(f'config/wan/rules2/{pid}/bandwidth_egress', egress_kbps):
                ok = False
        return ok
    except Exception as e:
        log(f"Error setting bandwidth for {device_id}: {e}")
        return False


def make_wan_device_highest_priority(device_id: str) -> bool:
    """Make a WAN device the highest priority.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        profiles = get_wan_profiles()
        if not profiles:
            return False
        lowest = min(p.get("priority", 0) for p in profiles)
        return set_wan_device_priority(device_id, lowest - 1.0)
    except Exception as e:
        log(f"Error making {device_id} highest priority: {e}")
        return False


def add_advanced_apn(carrier: str, apn: str) -> Optional[Dict[str, Any]]:
    """Add an advanced APN to the custom APNs list.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): Whether the operation succeeded.
            - carrier (str): Carrier name (on success).
            - apn (str): APN value (on success).
            - note (str): 'already exists' if duplicate.
            - error (str): Error message (on failure).
    """
    try:
        existing = get('config/wan/custom_apns') or []
        for entry in existing:
            if entry.get('carrier') == carrier and entry.get('apn') == apn:
                return {'success': True, 'note': 'already exists'}
        existing.append({"carrier": carrier, "apn": apn})
        result = put('config/wan/custom_apns', existing)
        if result is not None:
            return {'success': True, 'carrier': carrier, 'apn': apn}
        return {'success': False, 'error': 'Failed to update'}
    except Exception as e:
        log(f"Error adding advanced APN: {e}")
        return {'success': False, 'error': str(e)}


def delete_advanced_apn(carrier_or_apn: str) -> Optional[Dict[str, Any]]:
    """Delete advanced APN entries matching carrier or APN name.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - success (bool): Whether deletion succeeded.
            - deleted_count (int): Number of entries removed.
            - error (str): Error message (on failure).
    """
    try:
        existing = get('config/wan/custom_apns') or []
        remaining = [e for e in existing
                     if e.get('carrier') != carrier_or_apn
                     and e.get('apn') != carrier_or_apn]
        deleted = len(existing) - len(remaining)
        if deleted == 0:
            return {'success': False, 'deleted_count': 0,
                    'error': f'No match for "{carrier_or_apn}"'}
        result = put('config/wan/custom_apns', remaining)
        if result is not None:
            return {'success': True, 'deleted_count': deleted}
        return {'success': False, 'error': 'Failed to update'}
    except Exception as e:
        log(f"Error deleting advanced APN: {e}")
        return {'success': False, 'error': str(e)}


def get_wan_device_summary() -> Optional[Dict[str, Any]]:
    """Get summary of all WAN devices with profile info.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - devices (List[Dict]): Each with uid, profile_name,
                priority, disabled, connection_state. Sorted by priority.
            - profiles (Optional[List[Dict]]): All WAN profiles.
            - total_devices (int): Device count.
        Returns None on error.
    """
    try:
        wan_devices = get('status/wan/devices')
        if not wan_devices:
            return None
        profiles = get_wan_profiles()
        devices_info = []
        for uid in wan_devices:
            profile = get_wan_device_profile(uid)
            if profile:
                devices_info.append({
                    "uid": uid,
                    "profile_name": profile.get("trigger_name"),
                    "priority": profile.get("priority"),
                    "disabled": profile.get("disabled", False),
                    "connection_state": wan_devices[uid].get(
                        "status", {}).get("connection_state")
                })
        devices_info.sort(key=lambda x: x.get("priority", 0))
        return {
            "devices": devices_info,
            "profiles": profiles,
            "total_devices": len(devices_info)
        }
    except Exception as e:
        log(f"Error getting WAN device summary: {e}")
        return None


# =============================================================================
# MISC HELPERS
# =============================================================================

def stop_ping() -> Optional[Dict[str, Any]]:
    """Stop any running ping process.

    Returns:
        Optional[Dict[str, Any]]: Config store response dict, or None
            on error.
    """
    try:
        return put('control/ping/stop', '')
    except Exception as e:
        log(f"Error stopping ping: {e}")
        return None


def dns_lookup(hostname: str, record_type: str = "A") -> Optional[Dict[str, Any]]:
    """Perform DNS lookup.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - hostname (str): Queried hostname.
            - record_type (str): Record type requested.
            - result (Any): Raw config store response.
        Returns None on error.
    """
    try:
        result = post('control/dns/lookup', {
            "hostname": hostname, "record_type": record_type
        })
        return {'hostname': hostname, 'record_type': record_type, 'result': result}
    except Exception as e:
        log(f"Error in DNS lookup for {hostname}: {e}")
        return None


def clear_dns_cache() -> Optional[Dict[str, Any]]:
    """Clear the router's DNS cache.

    Returns:
        Optional[Dict[str, Any]]: Config store response dict, or None
            on error.
    """
    try:
        return post('control/dns/cache', {"clear": True})
    except Exception as e:
        log(f"Error clearing DNS cache: {e}")
        return None


def get_security_status() -> Optional[Dict[str, Any]]:
    """Get combined security status.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - firewall (Optional[Dict]): Firewall status summary.
            - security (Any): Raw security status.
            - certificates (Optional[Dict]): Certificate status.
        Returns None on error.
    """
    try:
        return {
            'firewall': get_firewall_status(),
            'security': get('status/security'),
            'certificates': get_certificate_status()
        }
    except Exception as e:
        log(f"Error getting security status: {e}")
        return None


def get_comprehensive_status() -> Optional[Dict[str, Any]]:
    """Get a comprehensive status report of the router.

    Returns:
        Optional[Dict[str, Any]]: Dict with keys:
            - system (Optional[Dict]): System status summary.
            - wan (Optional[Dict]): WAN status summary.
            - lan (Dict): LAN client info.
            - wlan_state (str): WLAN state string.
            - gps (Dict): GPS status.
            - ncm (Optional[str]): NCM connection state.
            - firmware (str): Firmware version string.
            - temperature (Optional[float]): Device temperature.
        Returns None on error.
    """
    try:
        return {
            'system': get_system_status(),
            'wan': get_wan_status(),
            'lan': get_lan_clients(),
            'wlan_state': get_wlan_state(),
            'gps': get_gps_status(),
            'ncm': get_ncm_status(),
            'firmware': get_firmware_version(),
            'temperature': get_temperature()
        }
    except Exception as e:
        log(f"Error getting comprehensive status: {e}")
        return None


# Legacy alias
uptime = time.time
