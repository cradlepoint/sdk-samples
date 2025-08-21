# s400_userio.py - This app is used to control the user IO on the S400.

import cp
import time

cp.log('Starting...')

while True:
    # Inputs
    PS_GPIO_1 = cp.get('status/gpio/pwr-connector-user-io-1-data')
    PS_GPIO_2 = cp.get('status/gpio/pwr-connector-user-io-2-data')

    # Outputs
    if PS_GPIO_2 == 1:
        cp.put('control/gpio/em-user-io-9-data', 1)
    else:
        cp.put('control/gpio/em-user-io-9-data', 0)

    if PS_GPIO_1 == 0:
        # Set the following LVTTL outputs to high.
        cp.put('control/gpio/em-user-io-0-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-1-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-2-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-3-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-4-data', 1)
        time.sleep(0.2)

        # Set the following LVTTL outputs to low.
        cp.put('control/gpio/em-user-io-0-data', 0)
        cp.put('control/gpio/em-user-io-1-data', 0)
        cp.put('control/gpio/em-user-io-2-data', 0)
        cp.put('control/gpio/em-user-io-3-data', 0)
        cp.put('control/gpio/em-user-io-4-data', 0)
    else:
        # Set the following LVTTL outputs to high.
        cp.put('control/gpio/em-user-io-4-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-3-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-2-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-1-data', 1)
        time.sleep(0.2)
        cp.put('control/gpio/em-user-io-0-data', 1)
        time.sleep(0.2)

        # Set the following LVTTL outputs to low.
        cp.put('control/gpio/em-user-io-4-data', 0)
        cp.put('control/gpio/em-user-io-3-data', 0)
        cp.put('control/gpio/em-user-io-2-data', 0)
        cp.put('control/gpio/em-user-io-1-data', 0)
        cp.put('control/gpio/em-user-io-0-data', 0)
