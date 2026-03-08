import cp
import socket
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

cp.log('Starting Client Session Monitor...')

sessions = {}
session_history = []
monitored_urls = {}
ip_to_url = {}
conn_tracker = {}
mac_to_ip = {}  # {mac: ip}
lock = threading.Lock()

def get_appdata(key, default):
    try:
        return cp.get_appdata(key) or default
    except:
        return default

def resolve_domain(url):
    try:
        domain = url.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
        result = socket.getaddrinfo(domain, None, socket.AF_INET)
        ips = list(set([r[4][0] for r in result]))
        return ips
    except Exception as e:
        cp.log(f'DNS resolution failed for {url}: {e}')
        return []

def get_client_info(ip, mac):
    try:
        dhcpd = cp.get('status/dhcpd') or {}
        for lease in dhcpd.get('leases', []):
            if lease.get('ip_address') == ip or lease.get('mac') == mac:
                return {
                    'hostname': lease.get('hostname', 'unknown'),
                    'network': lease.get('network', 'unknown'),
                    'ssid': lease.get('ssid', '')
                }
    except:
        pass
    return {'hostname': 'unknown', 'network': 'unknown', 'ssid': ''}

def get_client_total_usage(mac):
    try:
        cu = cp.get('status/client_usage') or {}
        if not cu.get('enabled'):
            cp.put('config/stats/client_usage/enabled', True)
            cp.log('Enabled client usage monitoring')
            return None
        for stat in cu.get('stats', []):
            if stat.get('mac') == mac:
                return {
                    'up_bytes': stat.get('up_bytes', 0),
                    'down_bytes': stat.get('down_bytes', 0),
                    'total_bytes': stat.get('up_bytes', 0) + stat.get('down_bytes', 0)
                }
    except:
        pass
    return None

def find_client_mac(ip):
    try:
        clients = cp.get('status/lan/clients') or []
        for client in clients:
            if client.get('ip_address') == ip:
                return client.get('mac')
    except:
        pass
    return None

def monitor_connections():
    global sessions, session_history, monitored_urls, ip_to_url, conn_tracker, mac_to_ip
    
    while True:
        try:
            urls_str = get_appdata('monitored_domains', 'example.com')
            urls = [u.strip() for u in urls_str.split(',') if u.strip()]
            session_timeout = int(get_appdata('session_timeout', 60))
            
            new_monitored = {}
            new_ip_to_url = {}
            for url in urls:
                ips = resolve_domain(url)
                for ip in ips:
                    new_monitored[url] = ip
                    new_ip_to_url[ip] = url
            
            monitored_urls = new_monitored
            ip_to_url = new_ip_to_url
            
            fw = cp.get('status/firewall') or {}
            conntrack = fw.get('conntrack', [])
            now = time.time()
            
            client_activity = {}
            
            for conn in conntrack:
                orig_dst = conn.get('orig_dst')
                if not orig_dst or orig_dst not in ip_to_url:
                    continue
                
                orig_src = conn.get('orig_src')
                orig_bytes = conn.get('orig_bytes', 0)
                reply_bytes = conn.get('reply_bytes', 0)
                conn_id = conn.get('id')
                tcp_state = conn.get('tcp_state', '')
                
                if not orig_src or not conn_id:
                    continue
                
                if tcp_state in ['TIME_WAIT', 'CLOSE_WAIT', 'LAST_ACK', 'CLOSING', 'FIN_WAIT1', 'FIN_WAIT2']:
                    continue
                
                if orig_src not in client_activity:
                    client_activity[orig_src] = {'tx': 0, 'rx': 0, 'last_activity': 0, 'url': ip_to_url.get(orig_dst, 'unknown')}
                
                if conn_id not in conn_tracker:
                    conn_tracker[conn_id] = {'tx': 0, 'rx': 0, 'last_seen': now}
                
                delta_tx = max(0, orig_bytes - conn_tracker[conn_id]['tx'])
                delta_rx = max(0, reply_bytes - conn_tracker[conn_id]['rx'])
                
                conn_tracker[conn_id]['tx'] = orig_bytes
                conn_tracker[conn_id]['rx'] = reply_bytes
                conn_tracker[conn_id]['last_seen'] = now
                
                if delta_tx > 0 or delta_rx > 0:
                    client_activity[orig_src]['last_activity'] = now
                
                client_activity[orig_src]['tx'] += delta_tx
                client_activity[orig_src]['rx'] += delta_rx
            
            with lock:
                for client_ip, activity in client_activity.items():
                    mac = find_client_mac(client_ip)
                    if not mac:
                        continue
                    
                    mac_to_ip[mac] = client_ip
                    session_key = f"{mac}_{activity['url']}"
                    
                    if session_key not in sessions:
                        if activity['last_activity'] > 0:
                            info = get_client_info(client_ip, mac)
                            
                            sessions[session_key] = {
                                'ip': client_ip,
                                'mac': mac,
                                'hostname': info['hostname'],
                                'network': info['network'],
                                'ssid': info['ssid'],
                                'url': activity['url'],
                                'start_time': activity['last_activity'],
                                'last_activity': activity['last_activity'],
                                'tx_bytes': activity['tx'],
                                'rx_bytes': activity['rx']
                            }
                            cp.log(f'Session started: {mac} ({info["hostname"]}) -> {activity["url"]}')
                    else:
                        session = sessions[session_key]
                        session['ip'] = client_ip
                        if activity['last_activity'] > session['last_activity']:
                            session['last_activity'] = activity['last_activity']
                        session['tx_bytes'] += activity['tx']
                        session['rx_bytes'] += activity['rx']
                
                ended = []
                for session_key, session in list(sessions.items()):
                    if (now - session['last_activity']) > session_timeout:
                        duration = max(1, int(session['last_activity'] - session['start_time']))
                        
                        history_entry = {
                            'ip': session['ip'],
                            'mac': session['mac'],
                            'hostname': session['hostname'],
                            'network': session['network'],
                            'ssid': session['ssid'],
                            'url': session.get('url', 'unknown'),
                            'start_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['start_time'])),
                            'end_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['last_activity'])),
                            'duration': int(duration),
                            'tx_bytes': session['tx_bytes'],
                            'rx_bytes': session['rx_bytes'],
                            'total_session_bytes': session['tx_bytes'] + session['rx_bytes']
                        }
                        
                        session_history.insert(0, history_entry)
                        if len(session_history) > 100:
                            session_history.pop()
                        
                        log_entry = f"{history_entry['start_time']} - {history_entry['end_time']} | {session['ip']} ({session['hostname']}) | Duration: {int(duration)}s | TX: {session['tx_bytes']} RX: {session['rx_bytes']} Total: {history_entry['total_session_bytes']}"
                        cp.log(f'Session ended: {log_entry}')
                        
                        try:
                            with open('tmp/session_log.txt', 'a') as f:
                                f.write(log_entry + '\n')
                        except:
                            pass
                        
                        try:
                            import os
                            log_size_limit = int(get_appdata('log_size_limit', 104857600))
                            csv_path = 'tmp/sessions.csv'
                            csv_exists = os.path.exists(csv_path)
                            
                            if csv_exists:
                                file_size = os.path.getsize(csv_path)
                                if file_size > log_size_limit:
                                    os.rename(csv_path, f'{csv_path}.old')
                                    csv_exists = False
                            
                            with open(csv_path, 'a') as f:
                                if not csv_exists:
                                    f.write('Start,End,Duration,Client IP,MAC,Hostname,Network,SSID,URL,URL TX,URL RX,URL Total\n')
                                f.write(f"{history_entry['start_time']},{history_entry['end_time']},{int(duration)},{session['ip']},{session['mac']},{session['hostname']},{session['network']},{session['ssid']},{history_entry.get('url','')},{session['tx_bytes']},{session['rx_bytes']},{history_entry['total_session_bytes']}\n")
                        except:
                            pass
                        
                        ended.append(session_key)
                
                for session_key in ended:
                    del sessions[session_key]
        
        except Exception as e:
            cp.log(f'Monitor error: {e}')
        
        time.sleep(5)

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html().encode())
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                urls_str = get_appdata('monitored_domains', 'example.com')
                urls = [u.strip() for u in urls_str.split(',') if u.strip()]
                with lock:
                    data = {
                        'urls': urls,
                        'timeout': get_appdata('session_timeout', 60),
                        'sessions': list(sessions.values()),
                        'history': session_history[:50]
                    }
                self.wfile.write(json.dumps(data).encode())
            except Exception as e:
                cp.log(f'API error: {e}')
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        elif self.path == '/download/sessions.csv':
            try:
                import os
                from datetime import datetime
                os.makedirs('tmp', exist_ok=True)
                csv_path = 'tmp/sessions.csv'
                if not os.path.exists(csv_path):
                    with open(csv_path, 'w') as f:
                        f.write('Start,End,Duration,Client IP,MAC,Hostname,Network,SSID,URL,URL TX,URL RX,URL Total\n')
                with open(csv_path, 'rb') as f:
                    content = f.read()
                
                hostname = cp.get('config/system/system_id') or 'router'
                hostname = hostname.replace(' ', '-').replace('/', '-')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'client-sessions_{hostname}_{timestamp}.csv'
                
                self.send_response(200)
                self.send_header('Content-type', 'text/csv')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                cp.log(f'CSV download error: {e}')
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/save_settings':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                urls_str = ','.join(data.get('urls', []))
                timeout = str(data.get('timeout', 60))
                cp.put_appdata('monitored_domains', urls_str)
                cp.put_appdata('session_timeout', timeout)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
                cp.log(f'Updated settings - URLs: {urls_str}, Timeout: {timeout}s')
            except Exception as e:
                cp.log(f'Save settings error: {e}')
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_html(self):
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Client Session Monitor</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#0f1419;color:#e6edf3}
.header{background:#161b22;padding:16px 24px;border-bottom:1px solid #30363d}
h1{margin:0;font-size:20px;font-weight:600}
.info{color:#8b949e;font-size:14px;margin-top:4px}
.container{padding:24px}
.section{background:#161b22;border:1px solid #30363d;border-radius:6px;margin-bottom:24px;padding:16px}
h2{margin:0 0 16px 0;font-size:16px;font-weight:600}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px;border-bottom:2px solid #30363d;font-size:12px;font-weight:600;color:#8b949e}
td{padding:8px;border-bottom:1px solid #21262d;font-size:13px}
tr:hover{background:#0d1117}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500}
.active{background:#1a7f37;color:#fff}
.bytes{color:#58a6ff}
.time{color:#8b949e}
.btn{display:inline-block;padding:4px 12px;background:#238636;color:#fff;text-decoration:none;border-radius:6px;font-size:12px;font-weight:500}
.btn:hover{background:#2ea043}
.section-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.section-header h2{margin:0}
.collapse{cursor:pointer;user-select:none}
.collapse:after{content:' ▼';font-size:10px}
.collapse.open:after{content:' ▲'}
.url-list{margin:8px 0;padding:8px;background:#0d1117;border-radius:4px;font-size:13px;list-style:none}
.url-list li{padding:4px 0}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000}
.modal.show{display:flex;align-items:center;justify-content:center}
.modal-content{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:24px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto}
.modal-content h2{margin-top:0;font-size:18px;border-bottom:1px solid #30363d;padding-bottom:12px}
.setting-group{margin-bottom:24px}
.setting-label{display:block;font-size:13px;font-weight:600;margin-bottom:8px;color:#8b949e}
.setting-input{width:100%;padding:8px;background:#0d1117;border:1px solid #30363d;border-radius:4px;color:#e6edf3;font-size:13px}
.url-list-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.url-list-header h3{margin:0;font-size:14px;font-weight:600}
.url-items{max-height:300px;overflow-y:auto}
.url-item{display:flex;align-items:center;padding:8px;background:#0d1117;border:1px solid #30363d;border-radius:4px;margin-bottom:8px}
.url-item input{flex:1;background:transparent;border:none;color:#e6edf3;font-size:13px;padding:4px}
.url-item input:focus{outline:none}
.url-item.editing input{background:#161b22;border:1px solid #30363d;border-radius:4px}
.icon-btn{background:none;border:none;color:#8b949e;cursor:pointer;padding:4px 8px;font-size:14px}
.icon-btn:hover{color:#58a6ff}
.icon-btn.delete:hover{color:#da3633}
.gear-btn{background:none;border:none;color:#8b949e;cursor:pointer;padding:4px;font-size:16px;margin-left:8px}
.gear-btn:hover{color:#58a6ff}
.modal-buttons{display:flex;gap:8px;margin-top:24px;padding-top:16px;border-top:1px solid #30363d}
.modal-buttons .btn{flex:1}
</style></head><body>
<div class="header"><h1>Client Session Monitor</h1>
<div class="info"><span>Timeout: <span id="timeout">60</span>s</span> | <span class="collapse" id="urlToggle" onclick="toggleUrls()">Monitored Domains</span><button class="gear-btn" onclick="showSettings()" title="Settings...">⚙</button></div>
<ul class="url-list" id="urlList" style="display:none"></ul></div>
<div class="container">
<div class="section"><div class="section-header"><h2>Active Sessions</h2></div>
<table id="active"><thead><tr><th>Client</th><th>Hostname</th><th>Network / SSID</th><th>Domain</th><th>Start</th><th>Duration</th><th>TX/RX/Total</th></tr></thead>
<tbody></tbody></table></div>
<div class="section"><div class="section-header"><h2>Session History</h2>
<a href="/download/sessions.csv" class="btn">Download</a></div>
<table id="history"><thead><tr><th>Client</th><th>Hostname</th><th>Network / SSID</th><th>Domain</th><th>Start</th><th>End</th><th>Duration</th><th>TX/RX/Total</th></tr></thead>
<tbody></tbody></table></div></div>
<div class="modal" id="settingsModal">
<div class="modal-content">
<h2>Settings</h2>
<div class="setting-group">
<label class="setting-label">Session Timeout (seconds)</label>
<input type="number" id="timeoutInput" class="setting-input" value="60" min="1">
</div>
<div class="setting-group">
<div class="url-list-header">
<h3>Monitored Domains</h3>
<button class="btn btn-small" onclick="addUrl()">Add</button>
</div>
<div class="url-items" id="urlEditor"></div>
</div>
<div class="modal-buttons">
<button class="btn" onclick="saveSettings()">Save</button>
<button class="btn" onclick="closeSettings()">Cancel</button>
</div></div></div>
<script>
var currentUrls=[];
var editingIndex=-1;
function toggleUrls(){var l=document.getElementById('urlList');var t=document.getElementById('urlToggle');if(l.style.display==='none'){l.style.display='block';t.classList.add('open');}else{l.style.display='none';t.classList.remove('open');}}
function showSettings(){fetch('/api/data').then(function(r){return r.json()}).then(function(d){currentUrls=d.urls.slice();document.getElementById('timeoutInput').value=d.timeout;editingIndex=-1;renderEditor();document.getElementById('settingsModal').classList.add('show');});}
function closeSettings(){document.getElementById('settingsModal').classList.remove('show');}
function renderEditor(){var e=document.getElementById('urlEditor');e.innerHTML='';currentUrls.forEach(function(u,i){var d=document.createElement('div');d.className='url-item'+(editingIndex===i?' editing':'');if(editingIndex===i){d.innerHTML='<input type="text" value="'+u+'" id="editInput'+i+'" autofocus><button class="icon-btn" onclick="saveEdit('+i+')" title="Save">✓</button><button class="icon-btn" onclick="cancelEdit()" title="Cancel">✕</button>';}else{d.innerHTML='<input type="text" value="'+u+'" readonly><button class="icon-btn" onclick="startEdit('+i+')" title="Edit">✏</button><button class="icon-btn delete" onclick="removeUrl('+i+')" title="Delete">🗑</button>';}e.appendChild(d);});if(editingIndex>=0){setTimeout(function(){var inp=document.getElementById('editInput'+editingIndex);if(inp){inp.focus();inp.select();}},50);}}
function addUrl(){currentUrls.push('');editingIndex=currentUrls.length-1;renderEditor();}
function startEdit(i){editingIndex=i;renderEditor();}
function saveEdit(i){var inp=document.getElementById('editInput'+i);if(inp){currentUrls[i]=inp.value.trim();}editingIndex=-1;renderEditor();}
function cancelEdit(){editingIndex=-1;renderEditor();}
function removeUrl(i){currentUrls.splice(i,1);if(editingIndex===i){editingIndex=-1;}else if(editingIndex>i){editingIndex--;}renderEditor();}
function saveSettings(){var urls=currentUrls.filter(function(u){return u.trim()!=='';});var timeout=parseInt(document.getElementById('timeoutInput').value)||60;fetch('/api/save_settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({urls:urls,timeout:timeout})}).then(function(r){return r.json()}).then(function(d){if(d.success){closeSettings();update();}});}
function fmt(b){if(b<1024)return b+' B';if(b<1048576)return(b/1024).toFixed(1)+' KB';if(b<1073741824)return(b/1048576).toFixed(1)+' MB';return(b/1073741824).toFixed(2)+' GB'}
function dur(s){var m=Math.floor(s/60);var h=Math.floor(m/60);m=m%60;s=s%60;if(h>0)return h+'h '+m+'m';if(m>0)return m+'m '+s+'s';return s+'s'}
function update(){fetch('/api/data').then(function(r){return r.json()}).then(function(d){
document.getElementById('timeout').textContent=d.timeout;
var ul=document.getElementById('urlList');
ul.innerHTML='';
d.urls.forEach(function(u){var li=document.createElement('li');li.textContent=u;ul.appendChild(li);});
var a=document.getElementById('active').getElementsByTagName('tbody')[0];
a.innerHTML='';
if(d.sessions.length===0){a.innerHTML='<tr><td colspan="7" style="text-align:center;color:#8b949e">No active sessions</td></tr>';}
else{d.sessions.forEach(function(s){var now=Math.floor(Date.now()/1000);var elapsed=now-Math.floor(s.start_time);var st=new Date(s.start_time*1000);var r=a.insertRow();r.innerHTML='<td>'+s.ip+'<br><span class="time">'+s.mac+'</span></td><td>'+s.hostname+'</td><td>'+s.network+(s.ssid?'<br><span class="time">'+s.ssid+'</span>':'')+'</td><td>'+s.url+'</td><td class="time">'+st.toLocaleDateString()+' '+st.toLocaleTimeString()+'</td><td><span class="badge active">'+dur(elapsed)+'</span></td><td class="bytes">↑'+fmt(s.tx_bytes)+' ↓'+fmt(s.rx_bytes)+'<br>'+fmt(s.tx_bytes+s.rx_bytes)+'</td>';});}
var h=document.getElementById('history').getElementsByTagName('tbody')[0];
h.innerHTML='';
if(d.history.length===0){h.innerHTML='<tr><td colspan="8" style="text-align:center;color:#8b949e">No session history</td></tr>';}
else{d.history.forEach(function(s){var r=h.insertRow();r.innerHTML='<td>'+s.ip+'<br><span class="time">'+s.mac+'</span></td><td>'+s.hostname+'</td><td>'+s.network+(s.ssid?'<br><span class="time">'+s.ssid+'</span>':'')+'</td><td>'+s.url+'</td><td class="time">'+s.start_time+'</td><td class="time">'+s.end_time+'</td><td>'+dur(s.duration)+'</td><td class="bytes">↑'+fmt(s.tx_bytes)+' ↓'+fmt(s.rx_bytes)+'<br>'+fmt(s.total_session_bytes)+'</td>';});}
});}
update();setInterval(update,3000);
</script></body></html>'''

def start_web_server():
    port = 8000
    server = HTTPServer(('', port), DashboardHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cp.log(f'Dashboard running on port {port}')
    server.serve_forever()

if __name__ == '__main__':
    import os
    os.makedirs('tmp', exist_ok=True)
    
    urls_str = get_appdata('monitored_domains', 'example.com')
    urls = [u.strip() for u in urls_str.split(',') if u.strip()]
    cp.log(f'Monitoring URLs: {urls}')
    
    for url in urls:
        ips = resolve_domain(url)
        if ips:
            cp.log(f'Resolved {url} to {ips}')
    
    monitor_thread = threading.Thread(target=monitor_connections, daemon=True)
    monitor_thread.start()
    
    try:
        start_web_server()
    except KeyboardInterrupt:
        cp.log('Shutting down...')
