'''
Outputs a 'Hello World!' log every 10 seconds.
'''

import time
import logging
import logging.handlers

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)s: %(message)s',
                    datefmt='%b %d %H:%M:%S',
                    handlers=[logging.StreamHandler(),
                              logging.handlers.SysLogHandler(address='/dev/log')])
log = logging.getLogger('hello_world')

while True:
    log.info("Hello World!")
    time.sleep(10)
