# send_to_server - get data from user defined paths and POST to user defined server at user defined interval.
# Settings are stored in SDK Appdata.

import cp
import json
import time
import requests

default_appdata = {
    "server_url": "https://httpbin.org/post",  # Server to POST to
    "interval": 10,  # Seconds between POST requests
    "payload": {
        # Identifiers:
        "hostname": "config/system/system_id",
        "mac": "status/product_info/mac0",
        "serial_number": "status/product_info/manufacturing/serial_num",
        # Data:
        "gps": "status/gps/fix",
        # "gpio": "status/gpio",
        # "obd": "status/obd",
        # "clients": "status/lan/clients",
    }
}

def get_appdata(name):
    """Get appdata from NCOS Configs. If not found, save default_appdata and return it."""
    try:
        appdata = cp.get('config/system/sdk/appdata')
        data = json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except:
        data = default_appdata
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(data)})
        cp.log(f'No appdata found - Saved default: {data}')
    return data

cp.log('Starting...')

while True:
    config = get_appdata('send_to_server')
    payload = {}
    for key, path in config['payload'].items():
        payload[key] = cp.get(path)
    cp.log(f'Payload: {payload}')
    resp = requests.post(config['server_url'], json=payload)
    cp.log(f'POST {config["server_url"]} {resp.status_code}')
    time.sleep(config['interval'])
