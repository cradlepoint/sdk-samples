import time

# NOTES:
# - since this MAIN.PY exists, the tool building the TAR.GZIP archive will
#   ignore (not use) the standard ./config/main.py
#
# - it is critical that the file "simple/hello_world/__init__.py" is empty
#
# - although this file does NOT use the "simple/hello_world/settings.ini"
#   will be required by the tool building the TAR.GZIP archive!


def do_something():
    logger.info("Hello SDK World!")
    time.sleep(10)
    return


if __name__ == "__main__":
    import sys
    import logging
    import logging.handlers

    if sys.platform == "win32":
        # technically, will run on Linux, but designed for CP router
        raise NotImplementedError("This code only runs on router")

    logger = logging.getLogger("routerSDK")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")

    # create the Syslog handler, which blends output on router's
    # Syslog output
    handler = logging.handlers.SysLogHandler(
        address="/dev/log", facility=logging.handlers.SysLogHandler.LOG_LOCAL6)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Starting ...")
    time.sleep(2.0)

    while True:
        # we do this wrap to dump any Python exception traceback out to
        # Syslog. Of course, this simple code won't likely fail, but it
        # demos the requirement! Without this, you'd see no error!
        try:
            do_something()
        except:
            logger.exception("simple main.py failed!")
            raise
