'''
Logger for the app
'''

import settings
import sys
import logging
import logging.handlers


###########################################################
# This is a singleton class to setup syslog logging
# and allows different log levels (i.e INFO, DEBUG, etc.)
# These logs will be displayed in the router syslog with
# the APP_NAME defined in settings.py.
# Example:
# 11:53:41 AM  [    INFO] [  app_template] Info log
#
# To log from another file:
# from app_logging import AppLogger
#
# log.info('This is an INFO log.')
# log.debug('This is a DEBUG log')
# etc.
###########################################################
class AppLogger(object):
    __instance = None
    __app_name = settings.APP_NAME

    def __new__(cls):
        if AppLogger.__instance is None:
            AppLogger.__instance = object.__new__(cls)

            logging.basicConfig(
                format='%(asctime)s %(name)s: %(message)s',
                level=logging.DEBUG
            )
            AppLogger.logger = logging.getLogger(AppLogger.__app_name)
            AppLogger.logger.setLevel(level=logging.DEBUG)
            log_address = '/dev/log'
            if sys.platform == 'Darwin':
                log_address = '/var/run/syslog'

            if sys.platform == 'win32':
                syslog = logging.handlers.SysLogHandler()
            else:
                syslog = logging.handlers.SysLogHandler(address=log_address)

            syslog.ident = '%s: ' % AppLogger.__app_name
            syslog.setFormatter(logging.Formatter(
                '%(message)s'
            ))
            AppLogger.logger.addHandler(syslog)

        return AppLogger.__instance

    def __log(fmt, *args, level=logging.DEBUG):
        AppLogger.logger.log(level, fmt, *args)

    def critical(self, fmt, *args):
        AppLogger.logger.log(logging.CRITICAL, fmt, *args)

    def error(self, fmt, *args):
        AppLogger.logger.log(logging.ERROR, fmt, *args)

    def warning(self, fmt, *args):
        AppLogger.logger.log(logging.WARNING, fmt, *args)

    def info(self, fmt, *args):
        AppLogger.logger.log(logging.INFO, fmt, *args)

    def debug(self, fmt, *args):
        AppLogger.logger.log(logging.DEBUG, fmt, *args)
