# wan_ip_change_alert - Send alert on WAN IP change and track previous IPs
import cp
import time

default_recheck = 300

cp.log('Starting...')
previous_wan_ip = None
while True:
    # Get recheck interval
    recheck = cp.get_appdata('wan_ip_change_alert_recheck')
    try:
        recheck = int(recheck)
    except (TypeError, ValueError):
        cp.log(f'SDK Appdata wan_ip_change_alert_recheck not found or invalid. Setting to {default_recheck}.')
        recheck = default_recheck

    # Monitor WAN IP address
    wan_ip = cp.get('status/wan/ipinfo/ip_address')
    while not wan_ip:
        wan_ip = cp.get('status/wan/ipinfo/ip_address')
    if wan_ip is not None and wan_ip != previous_wan_ip:  # IP Changed
        time.sleep(recheck) # wait recheck seconds
        if cp.get('status/wan/ipinfo/ip_address') == wan_ip:
            cp.alert(f'WAN IP Address Changed from {previous_wan_ip} to {wan_ip}')
            cp.log(f'WAN IP Address Changed from {previous_wan_ip} to {wan_ip}')
            previous_wan_ip = wan_ip
    time.sleep(1)
