from time import sleep
from csclient import EventingCSClient

SCAN_INTERVAL = 10

cp = EventingCSClient('connected_clients')
cp.log("Scanning for connected clients every {}s".format(SCAN_INTERVAL))

while True:
    connected_clients = cp.get('/status/lan/clients/')
    if connected_clients is not None:
        mac_addresses = []
        for client in connected_clients:
            if client['mac'] not in mac_addresses:
                mac_addresses.append(client['mac'])
        mac_addresses = ','.join(mac_addresses)
    else:
        mac_addresses = ''
    cp.log('connected clients: {}'.format(mac_addresses))
    cp.put('/config/system/desc/', mac_addresses)
    sleep(SCAN_INTERVAL)
