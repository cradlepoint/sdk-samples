# gpio_any_wan_connected - if any wan is connected (not just modems) set GPIO output to high
from csclient import EventingCSClient
import time
cp = EventingCSClient('gpio_any_wan_connected')
cp.log('Starting...')
while True:
    state = int(cp.get('status/wan/connection_state') == 'connected')
    cp.put('control/gpio/CONNECTOR_GPIO_1', state)
    time.sleep(1)
