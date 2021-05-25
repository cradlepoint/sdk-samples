from time import sleep
from csclient import EventingCSClient
import json

SLEEP_INTERVAL = 10

cp = EventingCSClient('connected_clients')
while True:
    #connected_clients = json.loads(cp.get('/status/lan/clients/'))
    connected_clients = cp.get('/status/lan/clients/')
    mac_addresses = ''
    for client in connected_clients:
        mac_addresses += client['mac'] + ','
    mac_addresses = mac_addresses.rstrip(',')
    cp.put('/config/system/desc', mac_addresses)
    sleep(SLEEP_INTERVAL)

#def update_desc(path, value, *args):
#    connected_clients = json.loads(value)
#    mac_addresses = ''
#    for client in connected_clients:
#        mac_addresses += client['mac'] + ','
#    mac_addresses.rstrip(',')
#    cp.put('/config/system/desc', mac_addresses)
#
#cp.register('put', '/status/lan/clients', update_desc)
