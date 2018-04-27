'''
A Simple HTTP Server for a custom dashboard.
'''

import cs
import cgi
import json
import sys

from app_logging import AppLogger
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http import HTTPStatus

# Create an AppLogger for logging to syslog in NCOS.
log = AppLogger()


def start_server():
    # avoid 8080, as the router may have service on it.
    # Firewall rules will need to be changed in the router
    # to allow access on this port.
    server_address = ('', 9001)

    log.debug('Starting Server: {}'.format(server_address))
    httpd = HTTPServer(server_address, WebServerRequestHandler)

    try:
        httpd.serve_forever()

    except KeyboardInterrupt:
        log.debug('Stopping Server, Key Board interrupt')

    return 0


def get_router_data():
    system_id = cs.CSClient().get('/config/system/system_id').get('data', '')
    modem_temp = cs.CSClient().get('/status/system/modem_temperature').get('data', '')
    host_os = sys.platform
    router_data = {'host_os': host_os,
                   'system_id': system_id,
                   'modem_temp': modem_temp
                   }
    return router_data


def button_one_click():
    log.debug('button_one_click()')


def button_two_click():
    log.debug('button_two_click()')


def ip_config(ip_data):
    log.debug('ip_config() - ipdata: {}'.format(ip_data))


def handle_uploaded_config_file(file_data):
    file_data_str = file_data.decode('utf-8')
    log.debug('handle_uploaded_config_file(): {}'.format(file_data_str))


def get_ip_config_info(form):
    ip_key = 'ip_addr'
    subnet_mask_key = 'subnet_mask'
    default_gateway_key = 'default_gateway'
    ip_data = dict()
    ip_data[ip_key] = form.getvalue(ip_key, '')
    ip_data[subnet_mask_key] = form.getvalue(subnet_mask_key, '')
    ip_data[default_gateway_key] = form.getvalue(default_gateway_key, '')
    return ip_data


class WebServerRequestHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        log.debug('Received Get request: {}'.format(self.path))
        # Add code here if you want to capture something in a GET request. Otherwise,
        # let the parent class handle it.
        super().do_GET()

    def do_POST(self):
        # Log the Get request
        log.debug('Received Post request: {}'.format(self.path))

        # Parse the form data posted
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': self.headers['Content-Type'],
                     })

        # Get the information posted in the form
        for field in form.keys():
            field_item = form[field]
            # log.debug('field_item: {}'.format(field_item))

            if field_item.filename:
                # The field contains an uploaded file
                file_data = field_item.file.read()
                handle_uploaded_config_file(file_data)
                value = "file {}".format(field_item.filename)
            else:
                value = form[field].value
                log.debug('Received Post request value: {}'.format(value))

                # Check for the value that you want to handle.
                if value == 'button_one_click':
                    button_one_click()

                if value == 'button_two_click':
                    button_two_click()

                if value == 'ip_config':
                    ip_data = get_ip_config_info(form)
                    ip_config(ip_data)
                    value = '{} - {}'.format(value, ip_data)

                if value == 'router_data':
                    self.send_response(HTTPStatus.OK)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(get_router_data()), 'utf-8'))
                    return

            # This is here just to echo back to the client what is receive.
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes('<html><body><h1>Server Received: {}</h1></body></html>'.format(value), 'utf-8'))


if __name__ == '__main__':
    try:
        start_server()
    except Exception as e:
        log.error('Exception occurred! exception: {}'.format(e))
