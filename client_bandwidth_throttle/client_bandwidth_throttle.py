import cp
import json
import socket
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

DEFAULT_LIMIT_MBPS = 10
PORT = 8000
LIMITS_FILE = 'tmp/client_limits.json'

# Store previous usage data for rate calculation
previous_usage = {}
rate_history = {}  # Store last 3 rate samples per client

def load_saved_limits():
    try:
        if os.path.exists(LIMITS_FILE):
            with open(LIMITS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        cp.log(f'Error loading limits: {e}')
    return {}

def save_limit(mac, limit_mbps):
    try:
        os.makedirs('tmp', exist_ok=True)
        limits = load_saved_limits()
        if limit_mbps == DEFAULT_LIMIT_MBPS:
            limits.pop(mac, None)  # Remove default limits
        else:
            limits[mac] = limit_mbps
        with open(LIMITS_FILE, 'w') as f:
            json.dump(limits, f)
    except Exception as e:
        cp.log(f'Error saving limit: {e}')

class BandwidthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/api/clients':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = get_clients_with_limits()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/set_limit':
            length = int(self.headers['Content-Length'])
            body = self.rfile.read(length).decode()
            params = parse_qs(body)
            mac = params.get('mac', [''])[0]
            limit = int(params.get('limit', [DEFAULT_LIMIT_MBPS])[0])
            
            success = set_client_limit(mac, limit)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success}).encode())
        else:
            self.send_error(404)

def get_clients_with_limits():
    global previous_usage, rate_history
    clients = []
    current_time = time.time()
    
    try:
        # Get IPv4 clients from status/lan/clients
        lan_data = cp.get('status/lan/clients') or []
        ipv4_clients = [c for c in lan_data if not c.get('ip_address', '').startswith('fe80::')]
        
        # Get usage data for these clients
        usage_data = cp.get('status/client_usage') or {}
        usage_stats = {stat['mac']: stat for stat in usage_data.get('stats', [])}
        
        qos = cp.get('config/qos') or {}
        queues = {q['name']: q for q in qos.get('queues', [])}
        
        for c in ipv4_clients:
            mac = c.get('mac', '')
            ip = c.get('ip_address', '')
            queue_name = f'CBT-{mac}'
            queue = queues.get(queue_name, {})
            
            # Check saved limits first, then queue config
            saved_limits = load_saved_limits()
            if mac in saved_limits:
                limit = saved_limits[mac]
            else:
                limit = queue.get('download_bw', DEFAULT_LIMIT_MBPS * 1000) // 1000
            
            # Get usage stats for this client
            usage = usage_stats.get(mac, {})
            up_bytes = usage.get('up_bytes', 0)
            down_bytes = usage.get('down_bytes', 0)
            
            # Calculate rates based on previous measurement
            up_rate = 0
            down_rate = 0
            if mac in previous_usage:
                prev = previous_usage[mac]
                time_diff = current_time - prev['time']
                if time_diff > 0:
                    up_rate = max(0, (up_bytes - prev['up_bytes']) / time_diff)
                    down_rate = max(0, (down_bytes - prev['down_bytes']) / time_diff)
            
            # Store rate in history (keep last 5 samples)
            if mac not in rate_history:
                rate_history[mac] = {'up': [], 'down': []}
            
            rate_history[mac]['up'].append(up_rate)
            rate_history[mac]['down'].append(down_rate)
            
            # Keep only last 3 samples
            if len(rate_history[mac]['up']) > 3:
                rate_history[mac]['up'] = rate_history[mac]['up'][-3:]
                rate_history[mac]['down'] = rate_history[mac]['down'][-3:]
            
            # Calculate 95th percentile rates
            up_rates = sorted(rate_history[mac]['up'])
            down_rates = sorted(rate_history[mac]['down'])
            
            # 95th percentile calculation
            up_95th = up_rates[int(len(up_rates) * 0.95)] if up_rates else 0
            down_95th = down_rates[int(len(down_rates) * 0.95)] if down_rates else 0
            
            # Store current usage for next calculation
            previous_usage[mac] = {
                'up_bytes': up_bytes,
                'down_bytes': down_bytes,
                'time': current_time
            }
            
            clients.append({
                'mac': mac,
                'ip': ip,
                'hostname': usage.get('name') or c.get('hostname', 'Unknown'),
                'limit_mbps': limit,
                'up_bytes': up_bytes,
                'down_bytes': down_bytes,
                'up_rate': int(up_95th),
                'down_rate': int(down_95th)
            })
    except Exception as e:
        cp.log(f'Error getting clients: {e}')
    return clients

def set_client_limit(mac, limit_mbps):
    try:
        # Find client IP from LAN clients
        lan_data = cp.get('status/lan/clients') or []
        ipv4_clients = [c for c in lan_data if not c.get('ip_address', '').startswith('fe80::')]
        
        client_ip = next((c['ip_address'] for c in ipv4_clients if c.get('mac') == mac), None)
        if not client_ip:
            cp.log(f'Client {mac} not found')
            return False
        
        qos = cp.get('config/qos') or {}
        queues = list(qos.get('queues', []))
        rules = list(qos.get('rules', []))
        queue_name = f'CBT-{mac}'
        limit_bps = limit_mbps * 1000000
        
        # Find or create queue
        queue_idx = next((i for i, q in enumerate(queues) if q.get('name') == queue_name), None)
        if queue_idx is None:
            queues.append({
                'name': queue_name,
                'ulenabled': True,
                'dlenabled': True,
                'upload_bw': limit_bps // 1000,  # Convert to kbps
                'download_bw': limit_bps // 1000,  # Convert to kbps
                'pri': 3,
                'downpri': 3,
                'ulsharing': False,
                'dlsharing': False,
                'upload': 0,
                'download': 0
            })
            cp.log(f'Created queue {queue_name} with {limit_mbps} Mbps')
        else:
            queues[queue_idx]['upload_bw'] = limit_bps // 1000
            queues[queue_idx]['download_bw'] = limit_bps // 1000
            cp.log(f'Updated queue {queue_name} to {limit_mbps} Mbps')
        
        # Find or create rule
        rule_idx = next((i for i, r in enumerate(rules) if r.get('lipaddr') == client_ip), None)
        if rule_idx is None:
            rules.append({
                'enabled': True,
                'name': f'CBT-{client_ip}',
                'ip_version': 'ip4',
                'lipaddr': client_ip,
                'lmask': '255.255.255.255',
                'lneg': False,
                'lport_start': None,
                'lport_end': None,
                'rneg': False,
                'rport_start': None,
                'rport_end': None,
                'protocol': 'tcp/udp',
                'dscp_neg': False,
                'app_set_uuid': '',
                'queue': queue_name,
                'match_pri': 10
            })
            cp.log(f'Created rule for {client_ip} -> {queue_name}')
        else:
            rules[rule_idx]['queue'] = queue_name
            cp.log(f'Updated rule for {client_ip} -> {queue_name}')
        
        # Apply QoS config
        result = cp.put('config/qos', {'enabled': True, 'queues': queues, 'rules': rules})
        cp.log(f'QoS config result: {result}')
        
        # Check if result indicates success (cp.put returns dict with success field)
        if result and (result.get('success', True) or isinstance(result, dict)):
            cp.log('QoS updated successfully')
            # Save the limit to file
            save_limit(mac, limit_mbps)
            return True
        else:
            cp.log(f'ERROR: QoS update failed - {result}')
            return False
    except Exception as e:
        cp.log(f'Error setting limit: {e}')
        return False

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Client Bandwidth Throttle</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#f5f5f5;padding:20px}
.container{max-width:1600px;margin:0 auto;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);padding:20px}
h1{margin-bottom:20px;color:#333}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd}
th{background:#f8f9fa;font-weight:600;cursor:pointer;user-select:none}
th:hover{background:#e9ecef}
input[type="number"]{width:80px;padding:6px;border:1px solid #ddd;border-radius:4px}
button{padding:6px 16px;background:#007bff;color:#fff;border:none;border-radius:4px;cursor:pointer;margin-left:5px}
button:hover{background:#0056b3}
.status{padding:10px;margin-bottom:20px;border-radius:4px;background:#d4edda;color:#155724}
.usage{font-size:0.9em;color:#666}
.current-limit{font-weight:bold;color:#000}
</style>
</head>
<body>
<div class="container">
<h1>Client Bandwidth Throttle</h1>
<div id="status" class="status" style="display:none"></div>
<table id="clients">
<thead><tr><th>Hostname</th><th>IP</th><th>MAC</th><th>Usage</th><th>Rate</th><th>Current Limit</th><th>New Limit</th></tr></thead>
<tbody></tbody>
</table>
</div>
<script>
var data = [];

function formatBytes(b) {
    if (b === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function render() {
    var tbody = document.getElementById('clients').getElementsByTagName('tbody')[0];
    
    if (tbody.rows.length === 0) {
        data.forEach(function(client) {
            var row = tbody.insertRow();
            row.insertCell(0).textContent = client.hostname || 'Unknown';
            row.insertCell(1).textContent = client.ip;
            row.insertCell(2).textContent = client.mac;
            row.insertCell(3);
            row.insertCell(4);
            row.insertCell(5);
            
            var controlsCell = row.insertCell(6);
            var input = document.createElement('input');
            input.type = 'number';
            input.value = client.limit_mbps;
            input.min = '1';
            input.max = '1000';
            input.id = 'limit-' + client.mac;
            
            var button = document.createElement('button');
            button.textContent = 'Set';
            button.dataset.mac = client.mac;
            button.addEventListener('click', handleSetLimit);
            
            controlsCell.appendChild(input);
            controlsCell.appendChild(document.createTextNode(' '));
            controlsCell.appendChild(button);
        });
    }
    
    for (var i = 0; i < data.length; i++) {
        var client = data[i];
        var row = tbody.rows[i];
        if (row) {
            var usage = '↑' + formatBytes(client.up_bytes) + ' ↓' + formatBytes(client.down_bytes);
            row.cells[3].innerHTML = '<div class="usage">' + usage + '</div>';
            
            var rate = '';
            if (client.up_rate > 0 || client.down_rate > 0) {
                rate = '↑' + formatBytes(client.up_rate) + '/s ↓' + formatBytes(client.down_rate) + '/s';
            }
            row.cells[4].innerHTML = '<div class="usage">' + rate + '</div>';
            row.cells[5].innerHTML = '<span class="current-limit">' + client.limit_mbps + ' Mbps</span>';
        }
    }
}

function handleSetLimit(event) {
    var mac = event.target.dataset.mac;
    var limit = document.getElementById('limit-' + mac).value;
    
    fetch('/api/set_limit', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'mac=' + mac + '&limit=' + limit
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        var status = document.getElementById('status');
        status.textContent = d.success ? 'Limit updated successfully' : 'Failed to update limit';
        status.style.display = 'block';
        setTimeout(function() { status.style.display = 'none'; }, 3000);
        load();
    });
}

function load() {
    fetch('/api/clients')
        .then(function(r) { return r.json(); })
        .then(function(d) {
            data = d;
            render();
        });
}

load();
setInterval(load, 5000);
</script>
</body>
</html>"""

def run_server():
    try:
        server = HTTPServer(('', PORT), BandwidthHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cp.log(f'Server started on port {PORT}')
        server.serve_forever()
    except OSError as e:
        if e.errno == 98:  # Address already in use
            cp.log(f'ERROR: Port {PORT} is busy - {e}')
        else:
            cp.log(f'ERROR: Failed to start server on port {PORT} - {e}')
    except Exception as e:
        cp.log(f'ERROR: Server error - {e}')

if __name__ == '__main__':
    cp.log('Starting Client Bandwidth Throttle')
    
    # Clean up any leftover CBT rules and queues
    try:
        qos = cp.get('config/qos') or {}
        queues = [q for q in qos.get('queues', []) if not q.get('name', '').startswith('CBT-')]
        rules = [r for r in qos.get('rules', []) if not r.get('name', '').startswith('CBT-')]
        
        if len(queues) != len(qos.get('queues', [])) or len(rules) != len(qos.get('rules', [])):
            cp.put('config/qos', {'enabled': qos.get('enabled', False), 'queues': queues, 'rules': rules})
            cp.log('Cleaned up leftover CBT rules and queues')
    except Exception as e:
        cp.log(f'Error cleaning CBT config: {e}')
    
    # Set default limits for all clients on startup
    try:
        saved_limits = load_saved_limits()
        clients_data = get_clients_with_limits()
        for client in clients_data:
            mac = client['mac']
            # Use saved limit if exists, otherwise default
            limit = saved_limits.get(mac, DEFAULT_LIMIT_MBPS)
            set_client_limit(mac, limit)
        cp.log('Applied saved/default limits to all clients')
    except Exception as e:
        cp.log(f'Error setting limits: {e}')
    
    threading.Thread(target=run_server, daemon=True).start()
    while True:
        time.sleep(60)