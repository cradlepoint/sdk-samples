# gpio_any_wan_connected - if any wan is connected (not just modems) set GPIO output to high
import cp
import time
cp.log('Starting...')
previous_state = None
while True:
    state = int(cp.get('status/wan/connection_state') == 'connected')
    if state != previous_state:
        cp.put('control/gpio/ACCESSORY_GPIO_1', state)
        cp.log(f'Set control/gpio/ACCESSORY_GPIO_1 to {state}')
        previous_state = state
    time.sleep(1)
