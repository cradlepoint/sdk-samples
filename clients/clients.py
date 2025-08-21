# Ericsson Cradlepoint SDK Application
import time
import cp
cp.log('Starting...')
while True:
    clients = cp.get_ipv4_lan_clients()
    text = f'{len(clients["wired_clients"]) + len(clients["wifi_clients"])} clients: '
    for client in clients['wired_clients']:
        text += f'{client["ip_address"]} ({client["mac"]})'
    for client in clients['wifi_clients']:
        text += f'{client["ip_address"]} ({client["mac"]})'
    text = text[:-2]
    cp.put('/config/system/asset_id', text)
    cp.log(text)
    time.sleep(300)