# tunnel_modem_reset.py
# Monitor tunnels and if down, reset modem it egresses from.

import cp
import time

def wait_for_tunnels():
    # Wait up to 10 minutes for all tunnels to be up
    start_time = time.time()
    timeout = 600  # 10 minutes in seconds

    cp.log(f'Waiting for tunnels to be up... Timeout: {timeout} seconds')

    try:
        while True:
            tunnels = cp.get('status/vpn/tunnels')
            if tunnels:
                if all(t['state'] == 'up' for t in tunnels):
                    cp.log('All tunnels are up')
                    return
            
            # Check if we've exceeded the timeout
            if time.time() - start_time > timeout:
                cp.log('Timeout waiting for tunnels to be up after 10 minutes')
                return
                
            time.sleep(5)
    except Exception as e:
        cp.logger.exception(e)


# Application starts here
cp.log('Starting...')

wait_for_tunnels()

while True:
    try:
        time.sleep(5)
        tunnels = cp.get('status/vpn/tunnels')
        if tunnels:
            if not all(t['state'] == 'up' for t in tunnels):
                for tunnel in tunnels:
                    if tunnel['state'] != 'up':
                        time.sleep(10)
                        if cp.get(f'status/vpn/tunnels/{tunnel["_id_"]}/state') != 'up':
                            modem_uid = tunnel['name'].split('_')[1]
                            msg = f'NCX tunnel {tunnel["name"]} is down. Resetting modem {modem_uid}'
                            cp.log(msg)
                            cp.alert(msg)
                            time.sleep(5)
                            cp.put(f'control/wan/devices/mdm-{modem_uid}/reset', True)
                            cp.log(f'Modem {modem_uid} reset')
                            wait_for_tunnels()
    except Exception as e:
        cp.logger.exception(e)