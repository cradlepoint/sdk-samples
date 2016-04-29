"""
A basic but complete echo server
"""

from http.server import BaseHTTPRequestHandler, HTTPServer

from cp_lib.app_base import CradlepointAppBase

# avoid 8080, as the router may have servcie on it.
DEF_HOST_PORT = 9001
DEF_HOST_IP = ""
DEF_WEB_MESSAGE = "Hello World"


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    if "web_server" in app_base.settings:
        host_port = int(app_base.settings["web_server"].get(
            "host_port", DEF_HOST_PORT))

        host_ip = app_base.settings["web_server"].get(
            "host_ip", DEF_HOST_IP)

        web_message = app_base.settings["web_server"].get(
            "message", DEF_WEB_MESSAGE)
    else:
        # we create, so WebServerRequestHandler can obtain
        app_base.settings["web_server"] = dict()

        host_port = DEF_HOST_PORT
        app_base.settings["web_server"]["host_port"] = host_port

        host_ip = DEF_HOST_IP
        app_base.settings["web_server"]["host_ip"] = host_ip

        web_message = DEF_WEB_MESSAGE
        app_base.settings["web_server"]["message"] = web_message

    # we want on all interfaces
    server_address = (host_ip, host_port)

    app_base.logger.info("Starting Server:{}".format(server_address))
    app_base.logger.info("Web Message is:{}".format(web_message))

    httpd = HTTPServer(server_address, WebServerRequestHandler)
    # set by singleton - pushes in any/all instances
    WebServerRequestHandler.APP_BASE = app_base

    try:
        httpd.serve_forever()

    except KeyboardInterrupt:
        app_base.logger.info("Stopping Server, Key Board interrupt")

    return 0


class WebServerRequestHandler(BaseHTTPRequestHandler):
    """

    """

    # a singleton to support pass-in of our settings and logger
    APP_BASE = None

    def do_GET(self):

        if self.APP_BASE is not None:
            self.APP_BASE.logger.info("Request from :{}".format(
                self.address_string()))
            web_message = self.APP_BASE.settings["web_server"]["message"]

        else:
            web_message = DEF_WEB_MESSAGE

        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Send message back to client
        # Write content as utf-8 data
        self.wfile.write(bytes(web_message, "utf8"))
        return


if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/simple_web")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
