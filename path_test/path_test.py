'''
Try to import cookiejar.py
'''

import os
import sys
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
log = logging.getLogger('path_test')

log.info('Current directory - %s', os.path.abspath(__file__))
log.info('Current PYTHONPATH = %s', sys.path)

try:
    from http import cookiejar
except ImportError:
    log.error('failure to import cookiejar (because it doesn\'t exist)')

sys.path.append('%s/additional_libs' % os.path.abspath(__file__))
log.info('Current PYTHONPATH = %s', sys.path)

try:
    from additional_libs.http import cookiejar
except ImportError:
    log.error('still unable to import cookiejar')
else:
    log.info('cookiejar was imported:\n%r', dir(cookiejar))

log.info('finished')
