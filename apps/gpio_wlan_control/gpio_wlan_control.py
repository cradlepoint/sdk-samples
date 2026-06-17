# Ericsson Cradlepoint SDK Application
# GPIO WLAN Control - Controls WLAN enabled state based on GPIO connector input
import cp
import time

cp.log('Starting...')

previous_gpio_bool = None

while True:
    try:
        # Get GPIO connector input value
        gpio_value = cp.get_gpio('power_input')
        if gpio_value is None:  # Double check to avoid false positive
            time.sleep(.1)
            gpio_value = cp.get_gpio('power_input')
        
        # Convert to boolean
        gpio_bool = bool(gpio_value)
        
        # Check if toggle appdata is set and toggle if needed
        toggle = cp.get_appdata('gpio_wlan_control_toggle')
        if toggle is None:  # Double check to avoid false positive
            time.sleep(.1)
            toggle = cp.get_appdata('gpio_wlan_control_toggle')

        if toggle is not None:
            gpio_bool = not gpio_bool
        
        # Only update if GPIO value changed
        if gpio_bool != previous_gpio_bool:
            cp.put('control/wlan/enabled', gpio_bool)
            cp.log(f'Set WLAN enabled to {gpio_bool}')
            previous_gpio_bool = gpio_bool
        
        time.sleep(1)
    except Exception as e:
        cp.log(f'Error in main loop: {e}')
        time.sleep(1)
