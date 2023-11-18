# Installer_UI - Web UI for installers to configure WiFi and run speedtests.

from csclient import EventingCSClient
import tornado.web
import json
from speedtest import Speedtest

class MainHandler(tornado.web.RequestHandler):
    """Handles / endpoint requests."""
    def get(self):
        """Return index.html to UI with current_ssid."""
        try:
            current_ssid = get_ssid()
            self.render("index.html",current_ssid=current_ssid)
        except Exception as e:
            cp.logger.exception(e)
            self.write('Error loading index.html')

class SaveHandler(tornado.web.RequestHandler):
    """Handles save/ endpoint requests."""
    def post(self):
        """Return save results JSON to UI."""
        installer_password = get_config('installer_password')
        wifi_ssid = self.get_argument('wifi_ssid')
        wifi_password = self.get_argument('wifi_password')
        password_entered = self.get_argument('password_entered')
        if not all([wifi_ssid, wifi_password, password_entered]):
            self.write(json.dumps({
                'success': False,
                'result': 'Please enter all fields!'
            }))
            return
        if password_entered == installer_password:
            cp.log(f'Installer changed WiFi SSID to {wifi_ssid} and password to {wifi_password}')
            cp.put(f'config/wlan/radio/0/bss/0/ssid', wifi_ssid)
            cp.put(f'config/wlan/radio/1/bss/0/ssid', wifi_ssid)
            cp.put(f'config/wlan/radio/0/bss/0/wpapsk', wifi_password)
            cp.put(f'config/wlan/radio/1/bss/0/wpapsk', wifi_password)
            self.write(json.dumps({
                'success': True,
                'result': 'Success!\nRestarting WiFi...',
                'current_ssid': wifi_ssid
            }))
        else:
            cp.log('Incorrect password entered')
            self.write(json.dumps({
                'success': False,
                'result': 'Incorrect Password!'
            }))
            return

class SpeedtestHandler(tornado.web.RequestHandler):
    """Handles speedtest/ endpoint requests."""
    def post(self):
        """Return speedtest results JSON to UI."""
        installer_password = get_config('installer_password')
        password_entered = self.get_argument('password_entered')
        if password_entered == installer_password:
            result = run_speedtest()
            self.write(json.dumps({
                'success': True,
                'result': result
            }))
        else:
            cp.log('Incorrect password entered')
            self.write(json.dumps({
                'success': False,
                'result': 'Incorrect Password!'
            }))

def run_speedtest():
    try:
        cp.log('Starting Speedtest...')
        s = Speedtest()
        server = s.get_best_server()
        cp.log(f'Found Best Ookla Server: {server["sponsor"]}')
        cp.log("Performing Ookla Download Test...")
        d = s.download()
        cp.log("Performing Ookla Upload Test...")
        u = s.upload(pre_allocate=False)
        download = '{:.2f}'.format(d / 1000 / 1000)
        upload = '{:.2f}'.format(u / 1000 / 1000)
        cp.log('Ookla Speedtest Complete! Results:')
        cp.log(f'Client ISP: {s.results.client["isp"]}')
        cp.log(f'Ookla Server: {s.results.server["sponsor"]}')
        cp.log(f'Ping: {s.results.ping}ms')
        cp.log(f'Download Speed: {download}Mb/s')
        cp.log(f'Upload Speed: {upload} Mb/s')
        cp.log(f'Ookla Results Image: {s.results.share()}')
        text = f'{s.results.client["isp"]}\nDL:{download}Mbps\nUL:{upload}Mbps\nPing:{s.results.ping:.0f}ms'
        return text
    except Exception as e:
        cp.logger.exception(e)

def get_ssid():
    return cp.get('config/wlan/radio/1/bss/0/ssid')

def get_config(name):
    appdata = cp.get('config/system/sdk/appdata')
    try:
        password = [x["value"] for x in appdata if x["name"] == name][0]
        if not password:
            password = cp.get('status/product_info/manufacturing/serial_num')
    except:
        cp.post('config/system/sdk/appdata', {"name": name, "value": ""})
        password = cp.get('status/product_info/manufacturing/serial_num')
    return password

def open_firewall():
    app_fwd = {"dst_zone_id": "00000001-695c-3d87-95cb-d0ee2029d0b5", "enabled": True, "filter_policy_id": "00000000-77db-3b20-980e-2de482869073", "src_zone_id": "00000003-695c-3d87-95cb-d0ee2029d0b5"}
    forwardings = cp.get('config/security/zfw/forwardings')
    for forwarding in forwardings:
        if forwarding['src_zone_id'] == app_fwd['src_zone_id'] and forwarding['dst_zone_id'] == app_fwd['dst_zone_id']:
            return
    cp.post('config/security/zfw/forwardings', app_fwd)
    cp.log('Forwarded Primary LAN Zone to Router Zone with Default Allow All policy')

if __name__ == '__main__':
    cp = EventingCSClient('Installer_UI')
    cp.log('Starting... edit Installer Password under System > SDK Data.')
    get_config('installer_password')
    open_firewall()
    application = tornado.web.Application([
        (r"/save", SaveHandler),
        (r"/speedtest", SpeedtestHandler),
        (r"/", MainHandler),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": "./"})
    ])
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
