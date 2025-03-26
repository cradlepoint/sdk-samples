# ddns.py
# Update the ddns_hostname with the IP address of the WAN device matching the ddns_wan_profile

# Initialize the CPSDK
from cpsdk import CPSDK
cp = CPSDK('ddns')

import requests
import base64
import time

def update_ddns(username, password, hostname, ip):
    # Send the update request
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'User-Agent': 'Python-Script ddnsUpdater/1.0 admin@example.com'
    }
    params = {
        'hostname': hostname,
        'myip': ip
    }
    response = requests.get(ddns_update_url, headers=headers, params=params)
    return response.text

previous_ip = ''
while True:
    ddns_username = cp.get_appdata('ddns_username')
    ddns_password = cp.get_appdata('ddns_password')
    ddns_hostname = cp.get_appdata('ddns_hostname')
    ddns_update_url = cp.get_appdata('ddns_update_url')
    ddns_wan_profile = cp.get_appdata('ddns_wan_profile')

    # If not all fields are set, skip the update and log an error
    if not all([ddns_username, ddns_password, ddns_hostname, ddns_update_url, ddns_wan_profile]):
        cp.log("Missing required SDK Appdata fields: ddns_username, ddns_password, ddns_hostname, ddns_update_url, ddns_wan_profile")
        time.sleep(10)
        continue

    # Get all WAN devices
    wan_devs = cp.get('status/wan/devices')

    # Get the device key name where config/trigger_name matches ddns_wan_name
    wan_dev_name = next((dev_name for dev_name, dev in wan_devs.items() 
                        if dev.get('config', {}).get('trigger_name', '').lower() == ddns_wan_profile.lower()), None)

    if wan_dev_name:
        wan_ip = cp.get(f'status/wan/devices/{wan_dev_name}/status/ipinfo/ip_address')
        
        if wan_ip and wan_ip != previous_ip:
            # Update the DNS record with WAN IP
            result = update_ddns(
                username=ddns_username,
                password=ddns_password,
                hostname=ddns_hostname,
                ip=wan_ip
            )
            previous_ip = wan_ip
            cp.log(f"DNS Update Response: {result}")
    else:
        cp.log(f"No WAN device found with trigger_name: {ddns_wan_profile}")
    time.sleep(10)
