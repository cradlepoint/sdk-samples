'''
A Simple HTTP Server for a custom dashboard.
'''

import cgi
import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http import HTTPStatus
from csclient import EventingCSClient


def get_router_data():
    system_id = cp.get('/config/system/system_id').get('data', '')
    modem_temp = cp.get('/status/system/modem_temperature').get('data', '')
    host_os = sys.platform
    router_data = {'host_os': host_os,
                   'system_id': system_id,
                   'modem_temp': modem_temp
                   }
    return router_data


def button_one_click():
    cp.log('button_one_click()')


def button_two_click():
    cp.log('button_two_click()')


def ip_config(ip_data):
    cp.log('ip_config() - ipdata: {}'.format(ip_data))


def handle_uploaded_config_file(file_data):
    file_data_str = file_data.decode('utf-8')
    cp.log('handle_uploaded_config_file(): {}'.format(file_data_str))


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
        cp.log('Received Get request: {}'.format(self.path))
        # Add code here if you want to capture something in a GET request. Otherwise,
        # let the parent class handle it.
        super().do_GET()

    def do_POST(self):
        # Log the Get request
        cp.log('Received Post request: {}'.format(self.path))

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
            # cp.log('field_item: {}'.format(field_item))

            if field_item.filename:
                # The field contains an uploaded file
                file_data = field_item.file.read()
                handle_uploaded_config_file(file_data)
                value = "file {}".format(field_item.filename)
            else:
                value = form[field].value
                cp.log('Received Post request value: {}'.format(value))

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


cp = EventingCSClient('simple_custom_dashboard')
server_address = ('', 9001)
cp.log('Starting Server: {}'.format(server_address))
httpd = HTTPServer(server_address, WebServerRequestHandler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    cp.log('Stopping Server, Key Board interrupt')
