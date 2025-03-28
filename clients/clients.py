# clients.py
# Put clients in asset_id field

import time
from cpsdk import CPSDK

cp = CPSDK('clients')
cp.log('Starting...')
while True:
    results_field = cp.get_appdata('clients') or '/config/system/asset_id'
    clients = cp.get('status/lan/clients')
    ipv4_clients = [client for client in clients if not client['ip_address'].startswith('fe80')]
    text = f"{len(ipv4_clients)} Clients: "
    for client in ipv4_clients:
        text += f"{client['ip_address']} ({client['mac']}), "
    text = text[:-2]
    cp.put(results_field, text)
    time.sleep(10)
