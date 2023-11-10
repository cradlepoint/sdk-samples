# Installer_UI - simple UI for installers to configure WiFi
from csclient import EventingCSClient
from flask import Flask, render_template, request, jsonify, send_from_directory
import time
import os
from speedtest import Speedtest

cp = EventingCSClient('Installer_UI')
cp.log('Starting... edit Installer Password under System > SDK Data.')
app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
@app.route('/')
def index():
    current_ssid = get_ssid()
    return render_template('index.html', current_ssid=current_ssid)

@app.route('/save', methods=['POST'])
def save():
    installer_password = get_config('installer_password')
    wifi_ssid = request.form['wifi_ssid']
    wifi_password = request.form['wifi_password']
    password_entered = request.form['password_entered']
    if not all([wifi_ssid, wifi_password, password_entered]):
        return jsonify({
            'success': False,
            'result': 'Please enter all fields!'
        })
    if password_entered == installer_password:
        cp.log(f'Installer changed WiFi SSID to {wifi_ssid} and password to {wifi_password}')
        cp.put(f'config/wlan/radio/0/bss/0/ssid', wifi_ssid)
        cp.put(f'config/wlan/radio/1/bss/0/ssid', wifi_ssid)
        cp.put(f'config/wlan/radio/0/bss/0/wpapsk', wifi_password)
        cp.put(f'config/wlan/radio/1/bss/0/wpapsk', wifi_password)
        return jsonify({
            'success': True,
            'result': 'Success!\nRestarting WiFi...',
            'current_ssid': wifi_ssid
        })
    else:
        cp.log('Incorrect password entered')
        return jsonify({
            'success': False,
            'result': 'Incorrect Password!'
        })

@app.route('/speedtest', methods=['POST'])
def speedtest():
    installer_password = get_config('installer_password')
    password_entered = request.form['password_entered']
    if password_entered == installer_password:
        result = run_speedtest()
        return jsonify({
            'success': True,
            'result': result
        })
    else:
        cp.log('Incorrect password entered')
        return jsonify({
            'success': False,
            'result': 'Incorrect Password!'
        })

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
    except:
        password = cp.get('status/product_info/manufacturing/serial_num')
        cp.post('config/system/sdk/appdata', {"name": name, "value": password})
    return password

def open_firewall():
    app_fwd = {"dst_zone_id": "00000001-695c-3d87-95cb-d0ee2029d0b5", "enabled": True, "filter_policy_id": "00000000-77db-3b20-980e-2de482869073", "src_zone_id": "00000003-695c-3d87-95cb-d0ee2029d0b5"}
    forwardings = cp.get('config/security/zfw/forwardings')
    for forwarding in forwardings:
        if forwarding['src_zone_id'] == app_fwd['src_zone_id'] and forwarding['dst_zone_id'] == app_fwd['dst_zone_id']:
            return
    cp.post('config/security/zfw/forwardings', app_fwd)
    cp.log('Forwarded Primary LAN Zone to Router Zone with Default Allow All policy')

get_config('installer_password')
open_firewall()
while True:
    try:
        app.run(host='0.0.0.0', port=8000)
    except UnicodeError as e:
        cp.logger.exception(e)
        cp.log('Error starting webserver!  Ensure hostname meets requirements for a valid hostname: (A-Z, 0-9 and -)')
        cp.log('Restarting server in 60 seconds...')
        time.sleep(60)