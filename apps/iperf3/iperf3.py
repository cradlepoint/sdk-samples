"""iPerf3 Web UI - Run iperf3 tests via a web interface with history tracking."""

import cp
import os
import sys
import json
import time
import socket
import signal
import threading
import subprocess
import http.server
from datetime import datetime

PORT = 8000
HISTORY_FILE = 'tmp/iperf3_history.json'
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')

# Global state
current_process = None
current_output = ''
test_running = False
test_summary = None
test_error = None
output_lock = threading.Lock()


def find_iperf3():
    """Find the iperf3 binary path."""
    for binary in IPERF3_BINARIES:
        if os.path.exists(binary):
            if not os.access(binary, os.X_OK):
                try:
                    os.chmod(binary, 0o755)
                except Exception:
                    pass
            return './' + binary
    return None


def load_history():
    """Load test history from disk."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        cp.log(f'Error loading history: {e}')
    return []


def save_history(history):
    """Save test history to disk."""
    try:
        os.makedirs('tmp', exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)
    except Exception as e:
        cp.log(f'Error saving history: {e}')


def add_history_entry(opts, summary):
    """Add a completed test to history."""
    entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'mode': opts.get('mode', 'client'),
        'server': opts.get('host', '') if opts.get('mode') == 'client' else 'localhost',
        'protocol': opts.get('protocol', 'tcp'),
        'direction': opts.get('direction', 'upload'),
        'transfer': summary.get('transfer', '--'),
        'bandwidth': summary.get('bandwidth_raw', '--'),
        'duration': str(opts.get('duration', '')) + 's'
    }
    history = load_history()
    history.append(entry)
    # Keep last 500 entries
    if len(history) > 500:
        history = history[-500:]
    save_history(history)


def build_client_command(binary, opts):
    """Build iperf3 client command from options."""
    cmd = [binary, '-c', opts['host'], '-J']
    if opts.get('port') and opts['port'] != 5201:
        cmd += ['-p', str(opts['port'])]
    if opts.get('protocol') == 'udp':
        cmd.append('-u')
    elif opts.get('protocol') == 'sctp':
        cmd.append('--sctp')
    if opts.get('direction') == 'download':
        cmd.append('-R')
    elif opts.get('direction') == 'bidirectional':
        cmd.append('--bidir')
    if opts.get('duration'):
        cmd += ['-t', str(opts['duration'])]
    if opts.get('parallel') and opts['parallel'] > 1:
        cmd += ['-P', str(opts['parallel'])]
    if opts.get('interval'):
        cmd += ['-i', str(opts['interval'])]
    if opts.get('bandwidth'):
        cmd += ['-b', opts['bandwidth']]
    if opts.get('window_size'):
        cmd += ['-w', opts['window_size']]
    if opts.get('buffer_length'):
        cmd += ['-l', opts['buffer_length']]
    if opts.get('mss'):
        cmd += ['-M', str(opts['mss'])]
    if opts.get('tos'):
        cmd += ['-S', opts['tos']]
    if opts.get('no_delay'):
        cmd.append('-N')
    if opts.get('zerocopy'):
        cmd.append('-Z')
    if opts.get('omit'):
        cmd += ['-O', str(opts['omit'])]
    return cmd


def build_server_command(binary, opts):
    """Build iperf3 server command from options.
    
    Server runs continuously (no -1 flag) until explicitly stopped.
    """
    cmd = [binary, '-s']
    if opts.get('port') and opts['port'] != 5201:
        cmd += ['-p', str(opts['port'])]
    if opts.get('bind'):
        cmd += ['-B', opts['bind']]
    return cmd


def format_bits(bits_per_second):
    """Format bits/sec to human readable."""
    if bits_per_second is None:
        return '--'
    if bits_per_second >= 1e9:
        return f'{bits_per_second / 1e9:.2f} Gbps'
    elif bits_per_second >= 1e6:
        return f'{bits_per_second / 1e6:.2f} Mbps'
    elif bits_per_second >= 1e3:
        return f'{bits_per_second / 1e3:.2f} Kbps'
    return f'{bits_per_second:.2f} bps'


def format_bytes(byte_count):
    """Format bytes to human readable."""
    if byte_count is None:
        return '--'
    if byte_count >= 1e9:
        return f'{byte_count / 1e9:.2f} GB'
    elif byte_count >= 1e6:
        return f'{byte_count / 1e6:.2f} MB'
    elif byte_count >= 1e3:
        return f'{byte_count / 1e3:.2f} KB'
    return f'{byte_count:.0f} B'


def parse_json_results(json_str):
    """Parse iperf3 JSON output into summary."""
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None

    if 'error' in data:
        return {'error': data['error']}

    summary = {
        'download': '--',
        'upload': '--',
        'jitter': '--',
        'loss': '--',
        'transfer': '--',
        'bandwidth_raw': '--'
    }

    end = data.get('end', {})

    # TCP results
    sum_sent = end.get('sum_sent', {})
    sum_received = end.get('sum_received', {})

    if sum_sent.get('bits_per_second') is not None:
        summary['upload'] = format_bits(sum_sent['bits_per_second'])
        summary['transfer'] = format_bytes(sum_sent.get('bytes', 0))
        summary['bandwidth_raw'] = summary['upload']

    if sum_received.get('bits_per_second') is not None:
        summary['download'] = format_bits(sum_received['bits_per_second'])
        if summary['transfer'] == '--':
            summary['transfer'] = format_bytes(sum_received.get('bytes', 0))
        summary['bandwidth_raw'] = summary['download']

    # UDP results
    sum_udp = end.get('sum', {})
    if sum_udp.get('bits_per_second') is not None:
        bw = format_bits(sum_udp['bits_per_second'])
        summary['upload'] = bw
        summary['bandwidth_raw'] = bw
        summary['transfer'] = format_bytes(sum_udp.get('bytes', 0))

    if sum_udp.get('jitter_ms') is not None:
        summary['jitter'] = f"{sum_udp['jitter_ms']:.3f} ms"

    if sum_udp.get('lost_percent') is not None:
        summary['loss'] = f"{sum_udp['lost_percent']:.2f}%"

    # Bidirectional results
    streams = end.get('streams', [])
    for stream in streams:
        sender = stream.get('sender', {})
        receiver = stream.get('receiver', {})
        if sender.get('bits_per_second') is not None:
            summary['upload'] = format_bits(sender['bits_per_second'])
        if receiver.get('bits_per_second') is not None:
            summary['download'] = format_bits(receiver['bits_per_second'])

    return summary


def run_test(opts):
    """Run an iperf3 test in a background thread."""
    global current_process, current_output, test_running, test_summary, test_error

    binary = find_iperf3()
    if not binary:
        with output_lock:
            test_error = 'No iperf3 binary found in app directory.'
            test_running = False
        return

    mode = opts.get('mode', 'client')
    if mode == 'client':
        cmd = build_client_command(binary, opts)
    else:
        cmd = build_server_command(binary, opts)

    cp.log(f'Running: {" ".join(cmd)}')

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        with output_lock:
            current_process = proc

        if mode == 'server':
            # Server mode: run continuously, stream output line by line
            with output_lock:
                current_output = f'iPerf3 server listening on port {opts.get("port", 5201)}...\n'
                current_output += 'Waiting for client connections...\n\n'

            while proc.poll() is None:
                line = proc.stdout.readline()
                if line:
                    decoded = line.decode('utf-8', errors='replace')
                    with output_lock:
                        current_output += decoded
                        # Cap output buffer at 50KB to prevent memory issues
                        if len(current_output) > 50000:
                            current_output = current_output[-40000:]

            # Process exited (was killed by user via stop)
            with output_lock:
                current_output += '\nServer stopped.\n'
        else:
            # Client mode: collect all output, parse JSON at end
            stdout_data = b''
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    stdout_data += line
                    decoded = line.decode('utf-8', errors='replace')
                    with output_lock:
                        current_output += decoded

            # Get any remaining output
            remaining, stderr = proc.communicate(timeout=5)
            if remaining:
                stdout_data += remaining
                with output_lock:
                    current_output += remaining.decode('utf-8', errors='replace')

            # Parse JSON results
            full_output = stdout_data.decode('utf-8', errors='replace')
            summary = parse_json_results(full_output)

            with output_lock:
                if summary and 'error' in summary:
                    test_error = summary['error']
                    test_summary = None
                    current_output = f"Error: {summary['error']}\n"
                elif summary:
                    test_summary = summary
                    test_error = None
                    lines = []
                    lines.append('=' * 50)
                    lines.append('iPerf3 Test Results')
                    lines.append('=' * 50)
                    if summary['upload'] != '--':
                        lines.append(f"  Upload:    {summary['upload']}")
                    if summary['download'] != '--':
                        lines.append(f"  Download:  {summary['download']}")
                    if summary['transfer'] != '--':
                        lines.append(f"  Transfer:  {summary['transfer']}")
                    if summary['jitter'] != '--':
                        lines.append(f"  Jitter:    {summary['jitter']}")
                    if summary['loss'] != '--':
                        lines.append(f"  Loss:      {summary['loss']}")
                    lines.append('=' * 50)
                    current_output = '\n'.join(lines) + '\n'
                    add_history_entry(opts, summary)
                    cp.log(f"iPerf3 result: {summary.get('bandwidth_raw', '--')}")
                else:
                    test_error = 'Failed to parse iperf3 output.'
                    if stderr:
                        err_text = stderr.decode('utf-8', errors='replace').strip()
                        if err_text:
                            test_error += f' stderr: {err_text}'
                            current_output += f'\nSTDERR: {err_text}\n'

    except subprocess.TimeoutExpired:
        with output_lock:
            test_error = 'Test timed out.'
            if current_process:
                current_process.kill()
    except Exception as e:
        with output_lock:
            test_error = f'Error running iperf3: {e}'
            current_output += f'\nError: {e}\n'
    finally:
        with output_lock:
            test_running = False
            current_process = None


def generate_csv_export():
    """Generate CSV content from history."""
    history = load_history()
    lines = ['Timestamp,Mode,Server,Protocol,Direction,Transfer,Bandwidth,Duration']
    for h in history:
        row = ','.join([
            h.get('timestamp', ''),
            h.get('mode', ''),
            h.get('server', ''),
            h.get('protocol', ''),
            h.get('direction', ''),
            h.get('transfer', ''),
            h.get('bandwidth', ''),
            h.get('duration', '')
        ])
        lines.append(row)
    return '\n'.join(lines)


def generate_html_export():
    """Generate HTML report from history."""
    history = load_history()
    html = []
    html.append('<!DOCTYPE html>')
    html.append('<html><head><meta charset="UTF-8">')
    html.append('<title>iPerf3 Test Report</title>')
    html.append('<style>')
    html.append('body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; }')
    html.append('h1 { color: #4f46e5; }')
    html.append('table { border-collapse: collapse; width: 100%; margin-top: 1rem; }')
    html.append('th, td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }')
    html.append('th { background: #f3f4f6; font-weight: 600; }')
    html.append('tr:nth-child(even) { background: #f9fafb; }')
    html.append('.summary { margin: 1rem 0; padding: 1rem; background: #f0fdf4; border-radius: 8px; }')
    html.append('</style></head><body>')
    html.append(f'<h1>iPerf3 Test Report</h1>')
    html.append(f'<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
    html.append(f'<p>Total tests: {len(history)}</p>')

    if history:
        html.append('<div class="summary">')
        # Calculate averages for bandwidth
        bw_values = []
        for h in history:
            bw = h.get('bandwidth', '')
            try:
                if 'Gbps' in bw:
                    bw_values.append(float(bw.replace(' Gbps', '')) * 1000)
                elif 'Mbps' in bw:
                    bw_values.append(float(bw.replace(' Mbps', '')))
                elif 'Kbps' in bw:
                    bw_values.append(float(bw.replace(' Kbps', '')) / 1000)
            except (ValueError, AttributeError):
                pass
        if bw_values:
            avg = sum(bw_values) / len(bw_values)
            html.append(f'<strong>Average Bandwidth:</strong> {avg:.2f} Mbps')
            html.append(f' | <strong>Max:</strong> {max(bw_values):.2f} Mbps')
            html.append(f' | <strong>Min:</strong> {min(bw_values):.2f} Mbps')
        html.append('</div>')

    html.append('<table>')
    html.append('<thead><tr>')
    html.append('<th>Timestamp</th><th>Mode</th><th>Server</th>')
    html.append('<th>Protocol</th><th>Direction</th><th>Transfer</th>')
    html.append('<th>Bandwidth</th><th>Duration</th>')
    html.append('</tr></thead><tbody>')
    for h in reversed(history):
        html.append('<tr>')
        html.append(f'<td>{h.get("timestamp", "")}</td>')
        html.append(f'<td>{h.get("mode", "")}</td>')
        html.append(f'<td>{h.get("server", "")}</td>')
        html.append(f'<td>{h.get("protocol", "")}</td>')
        html.append(f'<td>{h.get("direction", "")}</td>')
        html.append(f'<td>{h.get("transfer", "")}</td>')
        html.append(f'<td>{h.get("bandwidth", "")}</td>')
        html.append(f'<td>{h.get("duration", "")}</td>')
        html.append('</tr>')
    html.append('</tbody></table>')
    html.append('</body></html>')
    return '\n'.join(html)


class Iperf3Handler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for the iPerf3 web UI."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_file('index.html', 'text/html')
        elif self.path.startswith('/static/'):
            self.serve_static()
        elif self.path == '/api/status':
            self.api_status()
        elif self.path == '/api/history':
            self.api_history()
        elif self.path == '/api/export/csv':
            self.api_export_csv()
        elif self.path == '/api/export/html':
            self.api_export_html()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/start':
            self.api_start()
        elif self.path == '/api/stop':
            self.api_stop()
        elif self.path == '/api/history/clear':
            self.api_clear_history()
        else:
            self.send_error(404)

    def serve_file(self, filename, content_type):
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def serve_static(self):
        path = self.path.lstrip('/')
        if '..' in path:
            self.send_error(403)
            return
        ext_map = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.ico': 'image/x-icon'
        }
        ext = ''
        for e in ext_map:
            if path.endswith(e):
                ext = e
                break
        content_type = ext_map.get(ext, 'application/octet-stream')
        self.serve_file(path, content_type)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 0:
            return self.rfile.read(length)
        return b''

    def api_start(self):
        global test_running, current_output, test_summary, test_error
        if test_running:
            self.send_json({'error': 'A test is already running.'}, 400)
            return
        try:
            body = self.read_body()
            opts = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            self.send_json({'error': 'Invalid JSON.'}, 400)
            return

        with output_lock:
            test_running = True
            current_output = ''
            test_summary = None
            test_error = None

        t = threading.Thread(target=run_test, args=(opts,), daemon=True)
        t.start()
        self.send_json({'status': 'started'})

    def api_stop(self):
        global test_running, current_process
        with output_lock:
            if current_process:
                try:
                    current_process.kill()
                except Exception:
                    pass
            test_running = False
        self.send_json({'status': 'stopped'})

    def api_status(self):
        with output_lock:
            data = {
                'running': test_running,
                'output': current_output,
                'summary': test_summary,
                'error': test_error
            }
        self.send_json(data)

    def api_history(self):
        history = load_history()
        self.send_json({'history': history})

    def api_clear_history(self):
        save_history([])
        self.send_json({'status': 'cleared'})

    def api_export_csv(self):
        csv_content = generate_csv_export()
        body = csv_content.encode('utf-8')
        filename = f'iperf3_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def api_export_html(self):
        html_content = generate_html_export()
        body = html_content.encode('utf-8')
        filename = f'iperf3_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default HTTP logging to keep syslog clean."""
        pass


def start_server():
    """Start the HTTP server."""
    server = http.server.HTTPServer(('', PORT), Iperf3Handler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    cp.log(f'Web server started on port {PORT}')
    server.serve_forever()


cp.log('Starting iPerf3 Web UI...')

# Ensure iperf3 binary exists and is executable
binary = find_iperf3()
if binary:
    cp.log(f'Found iperf3 binary: {binary}')
else:
    cp.log('WARNING: No iperf3 binary found. Tests will fail.')

# Ensure tmp directory exists for history
os.makedirs('tmp', exist_ok=True)

# Start web server in daemon thread
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
cp.log(f'iPerf3 Web UI available at http://0.0.0.0:{PORT}')

# Keep main thread alive
while True:
    time.sleep(1)
