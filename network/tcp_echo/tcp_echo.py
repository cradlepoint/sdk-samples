"""
A basic but complete echo server
"""

import socket
import time
import gc

from cp_lib.app_base import CradlepointAppBase

"""
Notes for tcp_echo_server and tcp_echo_client

Anytime your code access an external resource or even internet-based server,
be prepared for the unexpected!

Common socket error reasons are shown here:
    https://www.python.org/dev/peps/pep-3151/#common-errnos-with-socket-error

BIND ERROR note:
    Your code is attempting to obtain and lock an exclusive resource. That
    attempt might fail for various reasons - the most common one is that
    another program/task ALREADY has locked that resource. In fact, it might
    even be a second copy of your own program running! While this sample
    merely exits, realistic server code could delay (use time.sleep()) for a
    few minutes, then try again. Still, feed back to users is critical,
    because if nothing changes ... nothing CHANGES.

    A second common error will be that Linux (such as used by Cradlepoint
    routers) does not allow non-privileged programs to open server sockets
    on ports lower than 1024. This script simulates this on Windows by
    manually raising an exception.
    TODO - what does Linux do?

    Example trace on a Win32 computer, when bind() fails due to resource
            ALREADY being used/locked.
        tcp_echo - INFO - Preparing to wait on TCP socket 9999
        tcp_echo - ERROR - socket.bind() failed - [WinError 10048] Only one
                           usage of each socket address (protocol/network
                           address/port) is normally permitted
        tcp_echo - ERROR - Exiting, status code is -1

BYTES, STR, UTF8 note:
    When looking on the internet for answers or code samples, be careful
    to seek Python 3 examples! A big change in Python 3, is that all strings
    now support UNICODE, which defaults to UTF8. UTF8 allows strings to
    include foreign language symbols, such as accent marks in European
    languages, or even direct Chinese (like å, δ, or 語).
        - See https://docs.python.org/3/howto/unicode.html

    But the key importance for Cradlepoint router development, is that both
    the SOCKET and the PYSERIAL modules recv/send bytes() objects, not str()
    objects! So for example, the line "sock.send('Hello, world')" will throw
    an exception because the SOCKET module works with "bytes" objects, not
    "str" objects. The trivial solution for string constants
    is to define them as b'Hello, world', not 'Hello, world'!

    To convert types of existing variable data:
      new_bytes_thing = string_thing.encode()  # def x.encode(encoding='utf-8')
      new_string_thing = bytes_thing.decode()  # def x.decode(encoding='utf-8')

CLOSE ERROR note:
    It is best-practice to always CLOSE your socket when you know it is
    "going away". In this sample, this step is not technically required,
    because when Python exits the routine and variable 'sock' goes out of
    scope, Python will close the socket. However, by explicitly closing it
    yourself, you are reminding viewers that the socket is being discarded.
    An empty try/except OSError/pass wrapper ignore error conditions where
    the socket.close() would fail due to other error situations

CONNECT ERROR note:
    Your code is attempting to link to a remote resource, which may not be
    accessible, or not accepting connections. While this sample merely exits,
    realistic client code could delay (use time.sleep()) for a few minutes,
    then try again. Still, feed back to users
    is critical, because if nothing changes ... nothing CHANGES.

    Example trace on a Win32 computer, when connect() fails due to resource
            ALREADY being used.
        tcp_echo - INFO - Preparing to connect on TCP socket 9999
        tcp_echo - ERROR - socket.connect() failed - [WinError 10061] No
                           connection could be made because the target
                           machine actively refused it
        tcp_echo - ERROR - Exiting, status code is -1

KEEP ALIVE note:
    For historical reasons, TCP sockets default to not use keepalive, which
    is a means to detect when an idle peer "has gone away". On cellular, this
    is pretty much guaranteed to happen at least once a day - if not after
    5 minutes of being idle! Without TCP keepalive, a server socket can be
    idle, and the memory resources used held FOREVER (as in years and years,
    or until the Cradlepoint router reboots!)

    Use this line: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    While many online samples show ways to define the timing behavior,
    however this is very OS dependant, plus on many smaller OS product, the
    TCP KeepAlive settings are global, so changing in one applications
    changes the timing for ALL applications. A better solution is to confirm
    that the default/common TCP Keepalive settings (probe count and time
    delays) are set to reasonable values for cellular.

MEMORY note:
    As Python variables are created and deleted, Python manages a list of
    "garbage", which is unused data that has not yet been freed. Python does
    this, because proving data is unused takes time - for example, if I
    delete a string variable of the value "Hello World", that actual data
    MIGHT be shared with multiple variables. Therefore Python caches the
    object as "possibly free", and using various estimates, Python
    periodically batch processes the "possibly free" collection list.

    While in general you should allow Python to do its job, when you have
    an object which is known to be large AND no longer used, manually
    running memory cleanup is safest on a small embedded system. Situations
    to consider  manual garbage collection are:
    1) when a client socket closes, which is especially critical if the
       client might repeatedly reconnect. For example, each socket (with
       buffers) could contain up to 1/4 MB of memory
    2) when a child thread exists, as the thread also could consume a large
       collection of dead memory objects
    3) after a large imported object, as as when an XML file has been parsed
       into memory. For example, an XML text file of 10K may consume over
       1MB of RAM after being parsed into memory.

"""


def tcp_echo_server(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    # logger.debug("Settings({})".format(sets))

    host_ip = 'localhost'
    host_port = 9999
    buffer_size = 1024

    if "tcp_echo" in app_base.settings:
        host_ip = app_base.settings["tcp_echo"].get("host_ip", '')
        host_port = int(app_base.settings["tcp_echo"].get("host_port", 9999))
        buffer_size = int(app_base.settings["tcp_echo"].get("buffer_size",
                                                            1024))

    while True:
        # define the socket resource, including the type (stream == "TCP")
        app_base.logger.info("Preparing TCP socket %d" % host_port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # attempt to actually lock resource, which may fail if unavailable
        #   (see BIND ERROR note)
        try:
            sock.bind((host_ip, host_port))
        except OSError as msg:
            app_base.logger.error("socket.bind() failed - {}".format(msg))

            # technically, Python will close when 'sock' goes out of scope,
            # but be disciplined and close it yourself. Python may warning
            # you of unclosed resource, during runtime.
            try:
                sock.close()
            except OSError:
                pass

            # we exit, because if we cannot secure the resource, the errors
            # are likely permanent.
            return -1

        # only allow 1 client at a time
        sock.listen(1)

        while True:
            # loop forever
            app_base.logger.info("Waiting on TCP socket %d" % host_port)
            client, address = sock.accept()
            app_base.logger.info("Accepted connection from {}".format(address))

            # for cellular, ALWAYS enable TCP Keep Alive (see KEEP ALIVE note)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # set non-blocking so we can do a manual timeout (use of select()
            # is better ... but that's another sample)
            # client.setblocking(0)

            while True:
                app_base.logger.debug("Waiting to receive data")
                data = client.recv(buffer_size)
                # data is type() bytes, to echo we don't need to convert
                # to str to format or return.
                app_base.logger.debug("See data({})".format(data))
                if data:
                    client.send(data)
                else:
                    break

                time.sleep(1.0)

            app_base.logger.info("Client disconnected")
            client.close()

            # since this server is expected to run on a small embedded system,
            # free up memory ASAP (see MEMORY note)
            del client
            gc.collect()

    return 0


def tcp_echo_client(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """

    host_ip = 'localhost'
    host_port = 9999
    buffer_size = 1024

    if "tcp_echo" in app_base.settings:
        host_ip = app_base.settings["tcp_echo"].get("host_ip", 'localhost')
        host_port = int(app_base.settings["tcp_echo"].get("host_port", 9999))
        buffer_size = int(app_base.settings["tcp_echo"].get("buffer_size",
                                                            1024))

    # allocate the socket resource, including the type (stream == "TCP")
    app_base.logger.info("Preparing to connect on TCP socket %d" % host_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # for cellular, ALWAYS enable TCP Keep Alive - (see KEEP ALIVE note)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # attempt to actually lock the resource, which may fail if unavailable
    #   (see CONNECT ERROR note)
    try:
        sock.connect((host_ip, host_port))
    except OSError as msg:
        app_base.logger.error("socket.connect() failed - {}".format(msg))

        # Python will close when variable 'sock' goes out of scope
        #   (see CLOSE ERROR note)
        try:
            sock.close()
        except OSError:
            pass

        # we exit, because if we cannot secure the resource, the errors are
        #   likely permanent.
        return -1

    # note: sock.send('Hello, world') will fail, because Python 3 socket()
    #       handles BYTES (see BYTES and STR note)
    data = b'Hello, world'
    app_base.logger.debug("Request({})".format(data))
    sock.send(data)
    data = sock.recv(buffer_size)
    app_base.logger.debug("Response({})".format(data))
    sock.close()

    time.sleep(1.0)

    return 0


if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/tcp_echo")

    if len(sys.argv) == 1:
        # if no cmdline args, we assume SERVER
        _result = tcp_echo_server(my_app)
    else:
        _result = tcp_echo_client(my_app)

    my_app.logger.info("Exiting, status code is {}".format(_result))

    sys.exit(_result)
