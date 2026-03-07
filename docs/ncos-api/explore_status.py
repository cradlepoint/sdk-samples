#!/usr/bin/env python3
"""
NCOS Status API Explorer

Explores status tree paths on a Cradlepoint router via REST API or SSH CLI.
Reads credentials from sdk_settings.ini in the project root.

Usage:
  python3 explore_status.py [--method rest|ssh] [path]

Examples:
  python3 explore_status.py                           # Explore status/wan/
  python3 explore_status.py status/wan/connection_state
  python3 explore_status.py status/wan/devices --method ssh
"""

import json
import os
import subprocess
import sys

def load_sdk_settings():
    """Load IP, username, password from sdk_settings.ini."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(project_root, 'sdk_settings.ini')
    settings = {'ip': '192.168.1.4', 'user': 'admin', 'pass': ''}
    if os.path.exists(ini_path):
        with open(ini_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == 'dev_client_ip':
                        settings['ip'] = v
                    elif k == 'dev_client_username':
                        settings['user'] = v
                    elif k == 'dev_client_password':
                        settings['pass'] = v
    return settings

def fetch_via_rest(path, settings):
    """Fetch status path via REST API (curl)."""
    url = f"http://{settings['ip']}/api/{path}"
    cmd = ['curl', '-s', '-u', f"{settings['user']}:{settings['pass']}", url]
    try:
        out = subprocess.check_output(cmd, timeout=10)
        return json.loads(out)
    except Exception as e:
        return {'success': False, 'error': str(e)}

def fetch_via_ssh(path, settings):
    """Fetch status path via SSH CLI get command."""
    cmd = [
        'sshpass', '-p', settings['pass'],
        'ssh', '-o', 'StrictHostKeyChecking=no',
        f"{settings['user']}@{settings['ip']}",
        'get', path
    ]
    try:
        out = subprocess.check_output(cmd, timeout=10)
        text = out.decode('utf-8').strip()
        try:
            return json.loads(text)
        except ValueError:
            return text
    except Exception as e:
        return {'error': str(e)}

def main():
    method = 'rest'
    path = 'status/wan'
    args = sys.argv[1:]
    while args:
        a = args.pop(0)
        if a == '--method' and args:
            method = args.pop(0).lower()
        elif not a.startswith('-'):
            path = a
            break

    settings = load_sdk_settings()
    if method == 'ssh':
        result = fetch_via_ssh(path, settings)
        print(json.dumps(result, indent=2))
    else:
        result = fetch_via_rest(path, settings)
        print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
