"""
Probe the GPS hardware and log the results.
"""
import cs
import json


APP_NAME = 'gps_probe'

gps_enabled = cs.CSClient().get('/config/system/gps/enabled').get('data')

if not gps_enabled:
    cs.CSClient().log(APP_NAME, 'GPS Function is NOT Enabled')

else:
    cs.CSClient().log(APP_NAME, 'GPS Function is Enabled')

    gps_data = cs.CSClient().get('/status/gps')
    json_value = json.dumps(gps_data, ensure_ascii=True, indent=4)
    json_lines = json_value.split(sep='\n')
    for line in json_lines:
        cs.CSClient().log(APP_NAME, line)
