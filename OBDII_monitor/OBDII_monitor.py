# OBDII_monitor - Monitor OBD-II values, put latest values in asset_id, and alert on conditions defined in SDK AppData.
#
# The app will create an entry in SDK AppData for "OBDII_monitor".
# Set the polling interval in seconds from 1-50.  Higher than 50 can miss historical values.
# Define the PID names you want to monitor and any conditions for alerting (optional):
#
# Example for just monitoring odometer with no alert conditions:
# "ODOMETER": {"condition": "", "value": ""}
# This will put ODOMETER value in the asset_id field but not send alerts.
#
# For alerting, set condition and value.  Conditions:
# ">" greater than, "<" less than, "=" equal to, "!=" not equal to
# Example for monitoring speed with alerting:
# "VEHICLE_SPEED": {"condition": ">", "value": 80}
# Example for alerting if fuel system monitor not complete:
# "FUEL_SYSTEM_MONITOR": {"condition": "!=", "value": "COMPLETE"}


import cp
import time
import json

defaults = {
    "interval": 30,  # seconds between polls
    "VEHICLE_SPEED": {"condition": ">", "value": 80},   # MPH
    "ODOMETER": {"condition": "", "value": ""},
    "FUEL_LEVEL": {"condition": "<", "value": 5},  # percent %
    "ENGINE_OIL_TEMPERATURE": {"condition": ">", "value": 260},  # degrees fahrenheit
    "ENGINE_OIL_PRESSURE": {"condition": "<", "value": 25}  # PSI
}

def get_config(name):
    try:
        appdata = cp.get('config/system/sdk/appdata')
        return json.loads([x["value"] for x in appdata if x["name"] == name][0])
    except:
        cp.log('No config found - saving defaults.')
        cp.post('config/system/sdk/appdata', {"name": name, "value": json.dumps(defaults)})
        return defaults

def get_location():
    """Return latitude and longitude as floats"""
    try:
        fix = cp.get('status/gps/fix')
        lat = fix['latitude']
        lon = fix['longitude']
        lat = dec(lat["degree"], lat["minute"], lat["second"])
        lon = dec(lon["degree"], lon["minute"], lon["second"])
        return lat, lon, fix.get('accuracy')
    except:
        return None, None, None

def dec(deg, min, sec):
    """Return decimal version of lat or long from deg, min, sec"""
    if str(deg)[0] == '-':
        dec = deg - (min / 60) - (sec / 3600)
    else:
        dec = deg + (min / 60) + (sec / 3600)
    return round(dec, 5)

def evaluate(pid, alert, previous_value):
    deviation = None  # deviation is any value that does not match the given alert criteria
    for value in pid["values"][-alerts["interval"]:]:
        if alert["condition"] == ">":
            if float(value[0]) > float(alert["value"]):
                if deviation:
                    if float(value[0]) > float(deviation):
                        deviation = value[0]
                else:
                    deviation = value[0]
        elif alert["condition"] == "<":
            if float(value[0]) < float(alert["value"]):
                if deviation:
                    if float(value[0]) < float(deviation):
                        deviation = value[0]
                else:
                    deviation = value[0]
        elif alert["condition"] == "=":
            try:
                if value[0] == alert["value"]:
                    deviation = value[0]
            except:
                pass  # fail open on "="
        elif alert["condition"] == "!=":
            try:
                if value[0] != alert["value"]:
                    deviation = value[0]
            except:
                deviation = value[0]  # fail closed on "!="

    if deviation:
        lat, lon, accuracy = get_location()
        msg = f'OBDII_monitor - VIN: {vin} {pid["name"]}: {deviation} {pid["units"]} {alert["condition"]} {alert["value"]} Location: {lat}, {lon}'
        cp.log(msg)
        cp.alert(msg)

cp.log('Starting...')
alerts = get_config('OBDII_monitor')
previous_value = {}
while True:
    alerts = get_config('OBDII_monitor')
    time.sleep(alerts["interval"])
    vin = cp.get('status/obd/vehicle/vin')
    pids = cp.get('status/obd/pids')
    text = ''
    for pid in pids:
        if pid["name"] in alerts.keys():
            evaluate(pid, alerts[pid["name"]], previous_value)  # Alerts
            cp.log(f'{str(pid["pid"])} - {pid["name"]}: {pid["last_value"]}')
            text += f'{pid["name"]}: {pid["last_value"]}, '
    text = text[:-2]
    cp.put('config/system/asset_id', text)
