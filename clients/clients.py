# clients.py
# Put clients in asset_id field
# Or specify a different path in SDK appdata named "clients"

import time
import cp

cp.log('Starting...')

while True:
    results_field = cp.get_appdata('clients') or '/config/system/asset_id'
    lan_data = cp.get_lan_clients()
    clients = lan_data['ipv4_clients']
    text = f"{lan_data['total_ipv4_clients']} Clients: "
    for client in clients:
        text += f"{client['ip_address']} ({client['mac']}), "
    text = text[:-2]
    cp.put(results_field, text)
    cp.log(text)
    time.sleep(60)
