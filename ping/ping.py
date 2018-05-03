'''
This application will ping an address and log the results
'''

import cs
import sys
import time
import logging
import logging.handlers

handlers = [logging.StreamHandler()]

if sys.platform == 'linux2':
    # on router also use the syslog
    handlers.append(logging.handlers.SysLogHandler(address='/dev/log'))

logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(name)s: %(message)s',
        datefmt='%b %d %H:%M:%S',
        handlers=handlers)

log = logging.getLogger('ping-sdk')

host = 'www.google.com' # IP address can also be used

cstore = cs.CSClient()
cstore.put('control/ping/start/host', host)
cstore.put('control/ping/start/size', 64)

log.info('ping host: %s', host)
result = {}
try_count = 0;

while try_count < 10:
    result = cstore.get('control/ping')
    if result.get('data') and result.get('data').get('status') in ["error", "done"]:
        break
    time.sleep(1)
    try_count += 1

error_str = ""
if try_count == 10 or not result.get('data') or result.get('data').get('status') != "done":
    error_str = "An error occurred"

log.info("ping result: %s\n%s", error_str, result['data']['result'])
