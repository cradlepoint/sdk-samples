# geofences - Send alert when entering and exiting geofences.

from csclient import EventingCSClient
from geopy import distance
import time
import json

config = [
    {
        "name": "Cradlepoint HQ",
        "lat": 43.618515,
        "lon": -116.206356,
        "radius": 100
    },
    {
        "name": "Idaho State Capitol",
        "lat": 43.617750,
        "lon": -116.199702,
        "radius": 250
    }
]

cp = EventingCSClient('geofences')

def get_location():
    """Return latitude and longitude as floats"""
    fix = cp.get('status/gps/fix')
    try:
        lat_deg = fix['latitude']['degree']
        lat_min = fix['latitude']['minute']
        lat_sec = fix['latitude']['second']
        lon_deg = fix['longitude']['degree']
        lon_min = fix['longitude']['minute']
        lon_sec = fix['longitude']['second']
        lat = dec(lat_deg, lat_min, lat_sec)
        lon = dec(lon_deg, lon_min, lon_sec)
        accuracy = fix.get('accuracy')
        return lat, lon, accuracy
    except:
        return None, None, None

def dec(deg, min, sec):
    """Return decimal version of lat or lon from deg, min, sec"""
    if str(deg)[0] == '-':
        dec = deg - (min / 60) - (sec / 3600)
    else:
        dec = deg + (min / 60) + (sec / 3600)
    return round(dec, 5)

def check_geofence(geofence):
    dist = distance.distance((lat, lon), (geofence["lat"], geofence["lon"])).m
    return dist < geofence["radius"]

def get_config(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        data = json.loads([x["value"] for x in appdata if x["name"] == name][0])
        if data != config:
            cp.log(f'Loaded config: {data}')
            return data
        else:
            return config
    except Exception as e:
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(config)})
        cp.log(f'Saved config: {config}')
        return config

cp.log('Starting...')
in_geofence = None
while True:
    config = get_config('geofences')
    lat, lon, accuracy = get_location()
    if not in_geofence:
        for fence in config:
            if check_geofence(fence):
                in_geofence = fence
                cp.log(f'Entered {in_geofence["name"]} Geofence. {lat} {lon}')
                cp.alert(f'Entered {in_geofence["name"]} Geofence. {lat} {lon}')
                break
    else:
        if not check_geofence(in_geofence):
            cp.log(f'Exited {in_geofence["name"]} Geofence. {lat} {lon}')
            cp.alert(f'Exited {in_geofence["name"]} Geofence. {lat} {lon}')
            in_geofence = None
    time.sleep(3)
