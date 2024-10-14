# rate_limit - enable QoS rule 1 until datacap alert is met then toggle to rule 2
from csclient import EventingCSClient
import time
cp = EventingCSClient('rate_limit')
cp.log('Starting...')
limited = False
while True:
    alert = cp.get('status/wan/datacap/completed_alerts/0/alerts')
    if alert and not limited:
        cp.log('Exceeded monthly data usage threshold - implementing reduced bandwidth QoS rule.')
        cp.put('config/qos/rules/0/enabled', False)
        cp.put('config/qos/rules/1/enabled', True)
        limited = True
    elif not alert and limited:
        cp.put('config/qos/rules/0/enabled', True)
        cp.put('config/qos/rules/1/enabled', False)
        cp.log('Monthly data usage reset - disabling reduced bandwidth QoS rule.')
        limited = False
    time.sleep(10)
