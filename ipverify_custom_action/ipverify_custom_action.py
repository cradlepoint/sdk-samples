# ipverify_custom_action - register function for callback on ipverify status change
# This example would use ipverify to ping a host over a VPN and the app will restart
# the VPN service if the ipverify test fails.
# This assumes the first ipverify test is the one we want to monitor.
#
# Log examples:
# 11:58:41 AM INFO ipverify_custom_action VPN Monitor Failed - Resetting Tunnel.

import cp
import time


def custom_action(path, value, *args):
    if not value:  # Test has failed
        cp.log('VPN Monitor Failed - Restarting Tunnel.')
        cp.put('config/vpn/enabled', False)
        time.sleep(1)
        cp.put('config/vpn/enabled', True)


cp.log('Starting...')
ipverify_uid = cp.get('config/identities/ipverify/0/_id_')
while not ipverify_uid:
    cp.log('Waiting for ipverify configuration...')
    ipverify_uid = cp.get('config/identities/ipverify/0/_id_')
    time.sleep(10)
cp.log(f'Watching ipverify test {ipverify_uid}')
cp.register('put', f'status/ipverify/{ipverify_uid}/pass', custom_action)
while True:
    time.sleep(1)
