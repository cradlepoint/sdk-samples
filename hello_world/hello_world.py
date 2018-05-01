'''
Outputs a 'Hello World!' log every 10 seconds.
'''

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
log = logging.getLogger('hello_world')

while True:
    log.info("Hello World!")
    time.sleep(10)
