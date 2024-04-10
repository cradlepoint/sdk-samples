# appdata_sample - example of how to use SDK Appdata to store and retrieve settings in NCOS Configs.
# the get_appdata() function will return the value of the appdata entry with the specified name.
# if the appdata is not found, it will save the default_appdata to the NCOS Configs and return it.

from csclient import EventingCSClient
import json
import time

default_appdata = {
    "server": "192.168.0.1",
    "port": 8000
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

cp = EventingCSClient('appdata_sample')
cp.log('Starting...')

# Run a loop to get the appdata every 10 seconds so you can see user changes.
while True:
    appdata = get_appdata('appdata_sample')
    cp.log(f'Appdata: {appdata}')
    time.sleep(10)
