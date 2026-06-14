# geofences.py
# Take custom action when inside or outside a geofence
# Requires 3 consecutive readings (3 seconds) before switching to prevent rapid changes
# Example uses SIM1 when outside geofence, SIM2 when inside geofence

from geopy import distance
import time
import json
import cp

# Default geofences list
default_geofences = [
    {
        "name": "Cradlepoint HQ",
        "lat": 43.618547,
        "lon": -116.206389,
        "radius": 200
    },
    {
        "name": "Boise Airport",
        "lat": 43.569282,
        "lon": -116.222676,
        "radius": 200
    }
]

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

def inside_geofence(lat, lon, geofences_list):
    """Check if location is inside any of the geofences"""
    for geofence in geofences_list:
        dist = distance.distance((lat, lon), (geofence["lat"], geofence["lon"])).m
        if dist < geofence["radius"]:
            return True, geofence["name"]
    return False, None

def get_geofences():
    geofences = cp.get_appdata('geofences')
    if geofences is None:
        geofences = default_geofences
        cp.post_appdata('geofences', json.dumps(geofences))
        cp.log(f'Created default config: {geofences}')
    return json.loads(geofences)

cp.log('Starting...')
# Initialize with a default state based on first reading
in_geofence = None
consecutive_readings = 0
last_state = None
current_geofence = None

# Get initial location and set default state
lat, lon, accuracy = get_location()
geofences = get_geofences()
if lat and lon:
    initial_state, geofence_name = inside_geofence(lat, lon, geofences)
    last_state = initial_state
    in_geofence = initial_state
    current_geofence = geofence_name
    # Set initial SIM based on location
    if initial_state:
        cp.log(f'Initial location inside {geofence_name} Geofence. Setting to SIM2. {lat} {lon}')
        cp.put('config/wan/dual_sim_disable_mask', 'int1,2')
    else:
        cp.log(f'Initial location outside all Geofences. Setting to SIM1. {lat} {lon}')
        cp.put('config/wan/dual_sim_disable_mask', 'int1,1')

while True:
    geofences = get_geofences()    
    lat, lon, accuracy = get_location()
    if lat and lon:
        current_state, geofence_name = inside_geofence(lat, lon, geofences)
        
        if current_state == last_state and geofence_name == current_geofence:
            consecutive_readings += 1
        else:
            consecutive_readings = 1
            last_state = current_state
            current_geofence = geofence_name
        
        if consecutive_readings >= 3:
            if current_state and in_geofence is not True:
                in_geofence = True
                cp.log(f'Entered {geofence_name} Geofence. Switching to SIM2. {lat} {lon}')
                cp.put('config/wan/dual_sim_disable_mask', 'int1,2')
            elif not current_state and in_geofence is not False:
                in_geofence = False
                cp.log(f'Exited all Geofences. Switching to SIM1. {lat} {lon}')
                cp.put('config/wan/dual_sim_disable_mask', 'int1,1')
    time.sleep(1)
