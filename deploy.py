#!/usr/bin/env python3
"""Cross-platform deploy script for Cradlepoint SDK apps.
Works on Windows, macOS, and Linux. Standalone alternative to make.py deploy.

Usage: python3 deploy.py <app_name>
"""
import configparser
import json
import subprocess
import sys
import time
import urllib.request
import base64
from datetime import datetime


def read_settings():
    config = configparser.ConfigParser()
    config.read('sdk_settings.ini')
    return {
        'ip': config.get('sdk', 'dev_client_ip'),
        'username': config.get('sdk', 'dev_client_username'),
        'password': config.get('sdk', 'dev_client_password'),
    }


def update_app_name(app_name):
    config = configparser.ConfigParser()
    config.read('sdk_settings.ini')
    config.set('sdk', 'app_name', app_name)
    with open('sdk_settings.ini', 'w') as f:
        config.write(f)


def run(cmd):
    """Run a make.py command, exit on failure."""
    result = subprocess.run([sys.executable, 'make.py'] + cmd.split())
    if result.returncode != 0:
        print(f'ERROR: make.py {cmd} failed (exit {result.returncode})')
        sys.exit(1)


def fetch_logs(settings, app_name):
    """Fetch and display recent logs for the app."""
    url = f"http://{settings['ip']}/api/status/log/"
    credentials = base64.b64encode(
        f"{settings['username']}:{settings['password']}".encode()
    ).decode()
    req = urllib.request.Request(url, headers={'Authorization': f'Basic {credentials}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for entry in data.get('data', [])[-20:]:
            if app_name in str(entry):
                ts = datetime.fromtimestamp(entry[0]).strftime('%H:%M:%S')
                print(f'{ts} {entry[3]}')
    except Exception as e:
        print(f'Warning: Could not fetch logs: {e}')


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 deploy.py <app_name>')
        sys.exit(1)

    app_name = sys.argv[1]
    settings = read_settings()
    update_app_name(app_name)

    print(f'Deploying {app_name} to {settings["ip"]}...')

    run('purge')
    time.sleep(2)
    run(f'build {app_name}')
    run(f'install {app_name}')
    time.sleep(5)

    print('Checking logs...')
    fetch_logs(settings, app_name)


if __name__ == '__main__':
    main()
