"""
Simple client to run against jsonrpc_server.py
"""
import json
import socket
import sys
import time

from cp_lib.app_base import CradlepointAppBase
# import cp_lib.data.json_get_put as json_get_put

# avoid 8080, as the router may have service on it.
DEF_HOST_PORT = 9901
DEF_HOST_IP = "localhost"


def run_client(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """

    tests = [
        {"path": "logging.level", "exp": "debug"},
        {"path": "router_api.user_name", "exp": "admin"},
        {"path": "application.firmware", "exp": "6.1"},
        {"path": "application.restart", "exp": "true"},

        {"path": "router_api", "exp": "admin"},
    ]

    for test in tests:
        data = {"jsonrpc": "2.0", "method": "get_setting",
                "params": {"path": test["path"]}, "id": 1}

        # then convert to JSON string
        data = json.dumps(data).encode()

        app_base.logger.debug("Sent:{}".format(data))

        server_address = (DEF_HOST_IP, DEF_HOST_PORT)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Connect to server and send data
            sock.connect(server_address)
            sock.sendall(data)

            # Receive data from the server and shut down
            received = str(sock.recv(1024), "utf-8")
        finally:
            sock.close()

        received = json.dumps(received)

        app_base.logger.debug("Recv:{}".format(received))

        time.sleep(1.0)

    return 0


def do_one_get(app_base, data):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :param data: the data
    :type data: str or dict or bytes
    :return:
    """
    if isinstance(data, dict):
        # then convert to JSON string
        data = json.dumps(data)

    if isinstance(data, str):
        # then convert to JSON string
        data = data.encode('utf-8')

    app_base.logger.debug("Sent:{}".format(data))

    server_address = (DEF_HOST_IP, DEF_HOST_PORT)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to server and send data
        sock.connect(server_address)
        sock.sendall(data)

        # Receive data from the server and shut down
        received = str(sock.recv(1024), "utf-8")
    finally:
        sock.close()

    app_base.logger.debug("Recv:{}".format(received))

    return json.loads(received)


if __name__ == "__main__":

    my_app = CradlepointAppBase("data/jsonrpc_settings")
    _result = run_client(my_app)

    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
