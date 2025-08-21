# power_alert - Send alert when external power is lost and restored.
# only works on devices with battery (E100, x10).

import cp
import time

cp.log('Starting...')
previous_power = cp.get('status/system/battery/ext_power')
while True:
    power = cp.get('status/system/battery/ext_power')
    if previous_power and not power:
        cp.alert('External power lost!')
        previous_power = power
    elif not previous_power and power:
        cp.alert('External power restored!')
        previous_power = power
    time.sleep(1)
