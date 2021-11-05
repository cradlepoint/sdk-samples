"""
A Simple Web server
"""

from csclient import EventingCSClient
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebServerRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Log the Get request
        cp.log(f'Received Get request: {self.path}')

        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Send message back to client
        # Write content as utf-8 data
        self.wfile.write(bytes(WEB_MESSAGE, "utf8"))
        return


cp = EventingCSClient('simple_web_server')

WEB_MESSAGE = "Hello World from Cradlepoint router!"

server_address = ("", 9001)

cp.log("Starting Server: {}".format(server_address))
cp.log("Web Message is: {}".format(WEB_MESSAGE))

httpd = HTTPServer(server_address, WebServerRequestHandler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    cp.log("Stopping Server, Key Board interrupt")
