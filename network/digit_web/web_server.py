"""
A basic but complete echo server
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from cp_lib.app_base import CradlepointAppBase

# avoid 8080, as the router may have service on it.
DEF_HOST_PORT = 9001
DEF_HOST_IP = ""
DEF_START_COUNT = 1099


def run_router_app(app_base):
    """

    :param CradlepointAppBase app_base: prepared resources: logger, cs_client
    :return:
    """
    my_server = WebServerThread('Digit_Web', app_base)
    my_server.start()
    return 0


class WebServerThread(threading.Thread):

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
        if "web_server" in self.app_base.settings:
            host_port = int(self.app_base.settings["web_server"].get(
                "host_port", DEF_HOST_PORT))

            host_ip = self.app_base.settings["web_server"].get(
                "host_ip", DEF_HOST_IP)

            start_count = int(self.app_base.settings["web_server"].get(
                "start_count", DEF_START_COUNT))
        else:
            # we create, so WebServerRequestHandler can obtain
            self.app_base.settings["web_server"] = dict()

            host_port = DEF_HOST_PORT
            self.app_base.settings["web_server"]["host_port"] = host_port

            host_ip = DEF_HOST_IP
            self.app_base.settings["web_server"]["host_ip"] = host_ip

            start_count = DEF_START_COUNT

        # push in the start count
        self.app_base.put_user_data('counter', start_count)

        # we want on all interfaces
        server_address = (host_ip, host_port)

        self.app_base.logger.info("Starting Server:{}".format(server_address))

        self.app_base.logger.info("Running")

        httpd = HTTPServer(server_address, WebServerRequestHandler)
        # set by singleton - pushes in any/all instances
        WebServerRequestHandler.APP_BASE = self.app_base

        try:
            httpd.serve_forever()

        except KeyboardInterrupt:
            self.app_base.logger.info("Stopping Server, Key Board interrupt")

    def please_stop(self):
        """
        Now thread is being asked to start running
        """
        raise NotImplementedError


class WebServerRequestHandler(BaseHTTPRequestHandler):
    """

    """

    # a singleton to support pass-in of our settings and logger
    APP_BASE = None

    START_LINES = '<!DOCTYPE html><html lang="en"><head>' +\
                  '<meta charset="UTF-8"><title>The Count Is</title>' +\
                  '</head><body><TABLE border="1"><TR>'

    IMAGE_LINES = '<TD><img src="%s"></TD>'

    END_LINES = '</TR></TABLE></body></html>'

    # images should be 190x380 pixels
    IMAGES = {
        '0': "sdigit_0.jpg",
        '1': "sdigit_1.jpg",
        '2': "sdigit_2.jpg",
        '3': "sdigit_3.jpg",
        '4': "sdigit_4.jpg",
        '5': "sdigit_5.jpg",
        '6': "sdigit_6.jpg",
        '7': "sdigit_7.jpg",
        '8': "sdigit_8.jpg",
        '9': "sdigit_9.jpg",
        '.': "sdigit_dot.jpg",
        ' ': "sdigit_blank.jpg",
    }

    PATH = "network/digit_web/"

    # def __init__(self):
    #     BaseHTTPRequestHandler.__init__(self)
    #     self.path = None
    #     return

    def do_GET(self):

        if self.path == "/":
            self.path = "/counter.html"

        if self.APP_BASE is not None:
            self.APP_BASE.logger.debug("Path={}".format(self.path))

        try:

            mime_type = 'text/html'
            send_reply = False
            if self.path.endswith(".html"):

                # fetch the current value, which might have changed
                count = "%5d" % int(self.APP_BASE.get_user_data('counter'))

                web_message = self.START_LINES
                for ch in count:
                    web_message += self.IMAGE_LINES % self.IMAGES[ch]
                web_message += self.END_LINES
                web_message = bytes(web_message, "utf-8")
                send_reply = True

            elif self.path.endswith(".jpg"):
                mime_type = 'image/jpg'
                f = open(self.PATH + self.path, 'rb')
                web_message = f.read()
                send_reply = True

            elif self.path.endswith(".ico"):
                mime_type = 'image/x-icon'
                f = open(self.PATH + self.path, 'rb')
                web_message = f.read()
                send_reply = True

            else:
                raise IOError

        except IOError:
            self.send_error(404, 'File Not Found: %s' % self.path)
            return

        if send_reply:
            # Send response status code
            self.send_response(200)

            # Send headers
            self.send_header('Content-type', mime_type)
            self.end_headers()

            # Send message back to client
            # Write content as utf-8 data
            self.wfile.write(web_message)

        return


if __name__ == "__main__":
    import sys

    my_app = CradlepointAppBase("network/simple_web")
    _result = run_router_app(my_app)
    my_app.logger.info("Exiting, status code is {}".format(_result))
    sys.exit(_result)
