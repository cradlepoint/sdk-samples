"""
A basic but complete echo server
"""

import socketserver
import threading
import time

import cp_lib.data.json_get_put as json_get_put
from cp_lib.app_base import CradlepointAppBase

# avoid 8080, as the router may have service on it.
DEF_HOST_PORT = 9901
DEF_HOST_IP = ""

# hold the CradlepointAppBase for access by the TCP handler
my_base = None


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    global my_base

    my_base = app_base

    my_server = JsonServerThread('Json', app_base)
    my_server.start()

    # we need to block the main thread here, because this sample is running
    # a SECOND thread for the actual server. This makes no sense in a pure
    # sample-code scenario, but doing it this way does allow you to
    # import & run the class JsonServerThread() from another demo app
    # which requires multiple threads - such as my Counter demo which
    # requires both a web server AND a JSON RPC server as 2 threads.
    try:
        while True:
            time.sleep(15.0)

    except KeyboardInterrupt:
        app_base.logger.info("Stopping Server, Key Board interrupt")

    return 0


class JsonServerThread(threading.Thread):

    def __init__(self, name, app_base):
        """
        prep our thread, but do not start yet

        :param str name: name for the thread
        :param CradlepointAppBase app_base: prepared resources: logger, etc
        """
        threading.Thread.__init__(self, name=name)

        self.app_base = app_base
        self.app_base.logger.info("started INIT")

        return

    def run(self):
        """
        Now thread is being asked to start running
        """
        if "jsonrpc" in self.app_base.settings:
            host_port = int(self.app_base.settings["jsonrpc"].get(
                "host_port", DEF_HOST_PORT))

            host_ip = self.app_base.settings["jsonrpc"].get(
                "host_ip", DEF_HOST_IP)
        else:
            # we create, so WebServerRequestHandler can obtain
            self.app_base.settings["jsonrpc"] = dict()

            host_port = DEF_HOST_PORT
            self.app_base.settings["jsonrpc"]["host_port"] = host_port

            host_ip = DEF_HOST_IP
            self.app_base.settings["jsonrpc"]["host_ip"] = host_ip

        # we want on all interfaces
        server_address = (host_ip, host_port)

        self.app_base.logger.info("Starting Server:{}".format(server_address))

        server = socketserver.TCPServer(server_address, MyHandler)

        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        try:
            server.serve_forever()

        except KeyboardInterrupt:
            self.app_base.logger.info("Stopping Server, Key Board interrupt")

    def please_stop(self):
        """
        Now thread is being asked to start running
        """
        raise NotImplementedError


class MyHandler(socketserver.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        """
        Handle a TCP packet
        :return:
        """
        global my_base

        # self.request is the TCP socket connected to the client
        message = self.request.recv(1024).strip()
        assert my_base is not None
        """ :type my_base: CradlepointAppBase """

        my_base.logger.debug(
            "Client {} asked:".format(self.client_address[0]))
        my_base.logger.debug(message)

        # parse & confirm appears valid
        message = json_get_put.jsonrpc_check_request(message,
                                                     test_params=True)
        my_base.logger.debug("checked:{}".format(message))
        # my_base.logger.debug("type:{}".format(type(message["method"])))

        if "error" not in message:
            # then so far, so good
            method = message["method"].lower()

            if method == "get_setting":
                my_base.logger.debug(
                    "GetSetting:{}".format(message["params"]))
                message = json_get_put.jsonrpc_get(
                    my_base.settings, message)

            elif method == "get_data":
                my_base.logger.debug(
                    "GetData:{}".format(message["params"]))
                message = json_get_put.jsonrpc_get(
                    my_base.data, message)

            elif method == "put_data":
                my_base.logger.debug(
                    "PutData:{}".format(message["params"]))
                message = json_get_put.jsonrpc_put(
                    my_base.data, message)

            else:
                message["error"] = {
                    "code": -32601,
                    "message": "Unknown \"method\": {}".format(method)}

        # else, if request["error"] is already true, then return error

        message = json_get_put.jsonrpc_prep_response(message, encode=True)
        """ :type message: str """
        my_base.logger.debug("returning:{}".format(message))
        self.request.sendall(message.encode())

        my_base.logger.debug("")
        return

if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/simple_jsonrpc")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
