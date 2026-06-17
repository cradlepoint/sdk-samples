# client_rssi_monitor will get the mac address and rssi of connected wlan clients and put them in the asset_id field.

import cp
import time
import datetime

interval = 30  # Seconds between monitoring polls

bw_modes = {0:"20 MHz",1:"40 MHz",2:"80 Mhz",3:"80+80 Mhz",4:"160 Mhz"}
wlan_modes = {0:"802.11b",1:"802.11g",2:"802.11n",3:"802.11n-only",4:"802.11ac",5:"802.11ax"}
wlan_band = {0:"2.4",1:"5"}

cp.log('Starting...')

while True:
    try:
        clients = {}
        wlan_clients = cp.get('status/wlan/clients')
        wlan_macs = [x["mac"] for x in wlan_clients]
        leases = cp.get('status/dhcpd/leases')
        for lease in leases:
            ssid = lease.get("ssid")
            if ssid and not clients.get(ssid):
                clients[ssid] = []
            if lease.get("mac") in wlan_macs:
                clients[ssid].append(lease)
        cp.log(f'CLIENTS: {clients}')
        for ssid, ssid_clients in clients.items():
            for i, client in enumerate(ssid_clients):
                for wlan_client in wlan_clients:
                    if wlan_client["mac"] == client["mac"]:
                        clients[ssid][i]["bw"] = bw_modes[wlan_client["bw"]]
                        clients[ssid][i]["mode"] = wlan_modes[wlan_client["mode"]]
                        clients[ssid][i]["radio"] = wlan_band[wlan_client["radio"]]
                        clients[ssid][i]["txrate"] = wlan_client["txrate"]
                        clients[ssid][i]["rssi"] = wlan_client["rssi0"]
                        clients[ssid][i]["time"] = str(datetime.timedelta(seconds=wlan_client["time"]))
        text = ''
        for ssid, ssid_clients in clients.items():
            text += f'{ssid} ('
            for client in ssid_clients:
                identifier = client["hostname"] or client["mac"]
                text += f'{identifier}: {client["mode"]}, {client["bw"]}, {client["txrate"]} Mbps, {client["radio"]} Ghz, {client["rssi"]} dBm, {client["time"]} | '
            text = text[:-2] + ') '
        cp.log(text)
        cp.put('config/system/asset_id', text)
    except Exception as e:
        cp.logger.exception(e)
    time.sleep(interval)
