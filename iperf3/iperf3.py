# iperf3 - run iperf3 to user defined server and update asset_id

import cp
import subprocess
import json
import time
import requests
import os
import sys

sdk_data = 'iperf3_server'
default_server = ''

def process_results(download, upload):
    # put results in asset_id
    msg = f'{download}Mbps Download {upload}Mbps Upload'
    cp.put('config/system/asset_id', msg)
    # Log
    cp.log(msg)
    # Alert
    cp.alert(msg)

def run_iperf3(server):
    try:
        args = f'-c {server} -J'
        command = f'./iperf3-arm64v8 {args}'.split(' ')
        results = ''
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            try:
                proc.wait(timeout=60)  # Set timeout to 60 seconds
                for line in proc.stdout:
                    results += line.decode('utf-8')
            except subprocess.TimeoutExpired:
                proc.kill()
                cp.logger.exception('iperf3 command timed out after 60 seconds')
                return None
        try:
            json_results = json.loads(results)
        except json.JSONDecodeError:
            cp.logger.exception('JSONDecodeError: ' + results)
            return None
        return json_results
    except subprocess.SubprocessError as e:
        cp.logger.exception(f'SubprocessError running iperf3: {e}')
        return None
    except Exception as e:
        cp.logger.exception(f'Unexpected error running iperf3: {e}')
        return None

def get_server():
    appdata = cp.get('config/system/sdk/appdata')
    try:
        server = [x["value"] for x in appdata if x["name"] == sdk_data][0]
        if not server:
            cp.log('Set iperf3 server in System > SDK Appdata.')
    except IndexError:
        cp.log('Set iperf3 server in System > SDK Appdata.')
        cp.post('config/system/sdk/appdata', {'name': sdk_data, 'value': default_server})
        server = default_server
    return server

def main(path, value, *args):
    if not value:  # asset_id has been cleared, run iperf3
        server = get_server()
        if not server:
            cp.log('No iPerf3 server set in System > SDK Appdata.')
        else:
            cp.log(f'Running iperf3 upload to {server}')
            upload = run_iperf3(server)
            cp.log(f'Running iperf3 download from {server}')
            download = run_iperf3(server + ' -R')

            if upload and download:
                upload = round(upload["end"]["sum_sent"]["bits_per_second"] / 1000000, 2)
                download = round(download["end"]["sum_received"]["bits_per_second"] / 1000000, 2)
                process_results(download, upload)
            else:
                cp.log('No results from iperf3')

def download_iperf3():
    try:
        # iperf3 binary URL
        url = "https://github.com/userdocs/iperf3-static/releases/download/3.17.1%2B/iperf3-arm64v8"

        # If file doesn't exist, download it
        filename = url.split("/")[-1]
        if not os.path.exists(filename):
            # Download the tar.gz file
            cp.log(f"Downloading {url}...")
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to download the file from {url}. Status code: {response.status_code}")

                # Save the file in the target folder
            filename = os.path.join("./", list(filter(None, url.split("/")))[-1])
            with open(filename, "wb") as file:
                file.write(response.content)
            
            # Make the file executable
            os.chmod(filename, 0o755)
            
            cp.log(f"Downloaded and made {filename} executable")
        else:
            cp.log(f"{filename} found")
        return True
    except Exception as e:
        cp.log(f"An error occurred: {e}")
        return False

cp.log('Starting...')
if download_iperf3():
    cp.log('Set iPerf3 server in System > SDK Appdata.  Clear asset_id to run iPerf3.')
    if not cp.get('config/system/asset_id'):
        cp.put('config/system/asset_id', 'Clear this to run iPerf3.')
    cp.on('put', 'config/system/asset_id', main)
    main(None, None, None)
    while True:
        time.sleep(1)
