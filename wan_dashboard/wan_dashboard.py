#!/usr/bin/env python3
"""
WAN Dashboard - Cradlepoint SDK Application

A web application that displays WAN interface utilization with real-time graphs.
Features:
- Cumulative traffic graph for all WAN interfaces
- Individual graphs for each WAN interface
- Configurable update interval via appdata
- Auto-refresh every 3 seconds (or user-defined interval)

Author: Cradlepoint SDK
"""

import cp
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
DEFAULT_UPDATE_INTERVAL = 3  # seconds
MAX_DATA_POINTS = 100  # Maximum number of data points to keep in memory

class WANDashboard:
    """Main WAN Dashboard application class."""
    
    def __init__(self):
        """Initialize the WAN Dashboard application."""
        self.cp = cp
        self.cp.log('Starting WAN Dashboard...')
        
        # Data storage
        self.timestamps: List[str] = []
        self.cumulative_data: Dict[str, List[float]] = {
            'in': [],
            'out': []
        }
        self.interface_data: Dict[str, Dict[str, List[float]]] = {}
        self.previous_bytes: Dict[str, Dict[str, int]] = {}
        self.interface_info: Dict[str, str] = {}  # Store interface display names
        
        # Server configuration
        self.server_port = self._get_server_port()
        self.server = None
        self.collection_thread = None
        self.running = False
        
        # Get configuration from appdata
        self.update_interval = self._get_update_interval()
        
    def _get_update_interval(self) -> int:
        """Get update interval from appdata or use default."""
        try:
            interval_str = self.cp.get_appdata('wan_dashboard_interval')
            if interval_str:
                interval = int(interval_str)
                if interval > 0:
                    self.cp.log(f'Using configured update interval: {interval} seconds')
                    return interval
        except (ValueError, TypeError) as e:
            self.cp.log(f'Error parsing wan_dashboard_interval from appdata: {e}')
        
        self.cp.log(f'Using default update interval: {DEFAULT_UPDATE_INTERVAL} seconds')
        return DEFAULT_UPDATE_INTERVAL
    
    def _get_server_port(self) -> int:
        """Get server port from appdata or use default."""
        try:
            port_str = self.cp.get_appdata('wan_dashboard_port')
            if port_str:
                port = int(port_str)
                if 1024 <= port <= 65535:  # Valid port range
                    self.cp.log(f'Using configured port: {port}')
                    return port
        except (ValueError, TypeError) as e:
            self.cp.log(f'Error parsing wan_dashboard_port from appdata: {e}')
        
        self.cp.log('Using default port: 8000')
        return 8000
    
    def _get_wan_status(self) -> Optional[Dict[str, Any]]:
        """Get WAN status from the router."""
        try:
            wan_status = self.cp.get_wan_status()
            return wan_status
        except Exception as e:
            self.cp.log(f'Error getting WAN status: {e}')
            return None
    
    def _calculate_traffic_delta(self, current_bytes: int, previous_bytes: int) -> float:
        """Calculate traffic delta and handle counter rollover."""
        if previous_bytes is None:
            return 0.0
        
        # Handle counter rollover (32-bit counter)
        if current_bytes < previous_bytes:
            # Counter rolled over
            delta = (2**32 - previous_bytes) + current_bytes
        else:
            delta = current_bytes - previous_bytes
        
        # Convert bytes to Mbps (assuming 1 second interval)
        return (delta * 8) / (1024 * 1024)  # Convert to Mbps
    
    def _collect_wan_data(self) -> None:
        """Collect WAN interface data."""
        wan_status = self.cp.get_wan_status()
        # Only use devices with connection_state == 'connected'
        if not wan_status or 'devices' not in wan_status:
            filtered_devices = []
        else:
            filtered_devices = [
                device for device in wan_status['devices']
                if device.get('connection_state') == 'connected'
            ]
            wan_status['devices'] = filtered_devices
        if not wan_status or 'devices' not in wan_status:
            self.cp.log('No WAN devices found or invalid status')
            return
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self.timestamps.append(current_time)
        
        # Keep only the last MAX_DATA_POINTS
        if len(self.timestamps) > MAX_DATA_POINTS:
            self.timestamps.pop(0)
            for key in self.cumulative_data:
                self.cumulative_data[key].pop(0)
            for interface_name in self.interface_data:
                for direction in self.interface_data[interface_name]:
                    self.interface_data[interface_name][direction].pop(0)
        
        # Ensure all existing interface data arrays match current timestamp length
        for interface_name in self.interface_data:
            while len(self.interface_data[interface_name]['in']) < len(self.timestamps):
                self.interface_data[interface_name]['in'].append(0.0)
                self.interface_data[interface_name]['out'].append(0.0)
            # Trim if too long (shouldn't happen but safety check)
            while len(self.interface_data[interface_name]['in']) > len(self.timestamps):
                self.interface_data[interface_name]['in'].pop()
                self.interface_data[interface_name]['out'].pop()
        
        # Get current active device UIDs
        current_device_uids = set()
        total_in_mbps = 0.0
        total_out_mbps = 0.0
        # Count all connected interfaces reported this cycle
        active_interfaces = len(wan_status['devices'])
        
        # Process each WAN device
        for device in wan_status['devices']:
            stats = device.get('stats')
            device_uid = device.get('uid', 'unknown')
            current_device_uids.add(device_uid)
            
            # Initialize interface data if not exists
            if device_uid not in self.interface_data:
                self.interface_data[device_uid] = {'in': [], 'out': []}
                # Pad with zeros to match current timestamp length
                current_length = len(self.timestamps)
                if current_length > 0:
                    self.interface_data[device_uid]['in'] = [0.0] * current_length
                    self.interface_data[device_uid]['out'] = [0.0] * current_length
                
                # Get interface display name
                display_name = self._get_interface_display_name(device_uid, device)
                self.interface_info[device_uid] = display_name
                self.cp.log(f'New WAN interface detected: {device_uid} ({display_name})')
            
            # If stats are missing (e.g., ethernet devices), attempt to fetch them directly
            if not stats:
                try:
                    fetched_stats = self.cp.get(f'status/wan/devices/{device_uid}/stats') or {}
                    # Normalize keys to match expected structure
                    stats = {
                        'in_bytes': fetched_stats.get('in'),
                        'out_bytes': fetched_stats.get('out')
                    }
                except Exception as e:
                    self.cp.log(f'Error fetching stats for {device_uid}: {e}')
                    stats = {}
            
            # Get current byte counts
            current_in = (stats or {}).get('in_bytes', 0) or 0
            current_out = (stats or {}).get('out_bytes', 0) or 0
            
            # Calculate deltas
            if device_uid in self.previous_bytes:
                in_mbps = self._calculate_traffic_delta(
                    current_in, 
                    self.previous_bytes[device_uid].get('in', 0)
                )
                out_mbps = self._calculate_traffic_delta(
                    current_out, 
                    self.previous_bytes[device_uid].get('out', 0)
                )
            else:
                in_mbps = 0.0
                out_mbps = 0.0
            
            # Store interface data (replace the last zero with actual data)
            if len(self.interface_data[device_uid]['in']) == len(self.timestamps):
                # Replace the last zero with actual data
                self.interface_data[device_uid]['in'][-1] = in_mbps
                self.interface_data[device_uid]['out'][-1] = out_mbps
            else:
                # This shouldn't happen but fallback to append
                self.interface_data[device_uid]['in'].append(in_mbps)
                self.interface_data[device_uid]['out'].append(out_mbps)
            
            # Update cumulative totals
            total_in_mbps += in_mbps
            total_out_mbps += out_mbps
            
            # Store current values for next calculation
            self.previous_bytes[device_uid] = {
                'in': current_in,
                'out': current_out
            }
        
        # Handle disconnected interfaces - add zero values for missing interfaces
        for device_uid in list(self.interface_data.keys()):
            if device_uid not in current_device_uids:
                # Interface disconnected, add zero values
                self.interface_data[device_uid]['in'].append(0.0)
                self.interface_data[device_uid]['out'].append(0.0)
                self.cp.log(f'WAN interface disconnected: {device_uid}')
        
        # Store cumulative data
        self.cumulative_data['in'].append(total_in_mbps)
        self.cumulative_data['out'].append(total_out_mbps)
        
        self.cp.log(f'Data collection: {len(self.timestamps)} points, '
                   f'{active_interfaces} active interfaces, '
                   f'{len(self.interface_data)} total tracked, '
                   f'Total IN: {total_in_mbps:.2f} Mbps, '
                   f'Total OUT: {total_out_mbps:.2f} Mbps')
    
    def _get_interface_display_name(self, device_uid: str, device: Dict[str, Any]) -> str:
        """Get display name for interface based on type."""
        try:
            if device_uid.startswith('mdm'):
                # Get port, SIM slot and carrier info for modems
                port_info = self.cp.get(f'status/wan/devices/{device_uid}/info/port')
                sim_info = self.cp.get(f'status/wan/devices/{device_uid}/info/sim')
                carrier_info = self.cp.get(f'status/wan/devices/{device_uid}/info/carrier_id')
                
                # Handle both dict and string responses for port
                if isinstance(port_info, dict):
                    port = port_info.get('port', 'Unknown')
                else:
                    port = str(port_info) if port_info else 'Unknown'
                
                # Handle both dict and string responses for SIM
                if isinstance(sim_info, dict):
                    sim_slot = sim_info.get('slot', 'Unknown')
                else:
                    sim_slot = str(sim_info) if sim_info else 'Unknown'
                    
                # Handle both dict and string responses for carrier
                if isinstance(carrier_info, dict):
                    carrier = carrier_info.get('carrier_id', 'Unknown')
                else:
                    carrier = str(carrier_info) if carrier_info else 'Unknown'
                
                return f"{device_uid} ({port} {sim_slot}: {carrier})"
                
            elif device_uid.startswith('ethernet'):
                # Get port info for ethernet
                port_info = self.cp.get(f'status/wan/devices/{device_uid}/info/port')
                
                # Handle both dict and string responses
                if isinstance(port_info, dict):
                    port = port_info.get('port', 'Unknown')
                else:
                    port = str(port_info) if port_info else 'Unknown'
                
                return f"{device_uid} - Ethernet (Port {port})"
                
            else:
                # Fallback to device UID
                return device_uid
                
        except Exception as e:
            self.cp.log(f'Error getting interface info for {device_uid}: {e}')
            return device_uid
    
    def _data_collection_loop(self) -> None:
        """Main data collection loop."""
        self.cp.log('Starting data collection loop')
        while self.running:
            try:
                self._collect_wan_data()
                time.sleep(self.update_interval)
            except Exception as e:
                self.cp.log(f'Error in data collection loop: {e}')
                time.sleep(self.update_interval)
        self.cp.log('Data collection loop stopped')
    
    def get_data_for_api(self) -> Dict[str, Any]:
        """Get formatted data for API response."""
        return {
            'timestamps': self.timestamps,
            'cumulative': self.cumulative_data,
            'interfaces': self.interface_data,
            'interface_info': self.interface_info,
            'router_name': self.cp.get_name(),
            'update_interval': self.update_interval,
            'max_points': MAX_DATA_POINTS
        }
    
    def start(self) -> None:
        """Start the WAN Dashboard application."""
        self.cp.log('Starting WAN Dashboard server...')
        
        # Start data collection thread
        self.running = True
        self.collection_thread = threading.Thread(target=self._data_collection_loop)
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
        # Start HTTP server
        handler = self._create_request_handler()
        self.server = HTTPServer(('0.0.0.0', self.server_port), handler)
        
        self.cp.log(f'WAN Dashboard started on port {self.server_port}')
        self.cp.log(f'Update interval: {self.update_interval} seconds')
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self) -> None:
        """Stop the WAN Dashboard application."""
        self.cp.log('Stopping WAN Dashboard...')
        self.running = False
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        self.cp.log('WAN Dashboard stopped')
    
    def _create_request_handler(self):
        """Create HTTP request handler class."""
        dashboard = self
        
        class WANDashboardHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self._serve_html()
                elif self.path == '/api/data':
                    self._serve_api_data()
                else:
                    self.send_error(404)
            
            def _serve_html(self):
                """Serve the main HTML page."""
                html_content = dashboard._get_html_content()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html_content.encode())
            
            def _serve_api_data(self):
                """Serve JSON data for the API."""
                data = dashboard.get_data_for_api()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            
            def log_message(self, format, *args):
                """Override to use cp.log instead of default logging."""
                pass
        
        return WANDashboardHandler
    
    def _get_html_content(self) -> str:
        """Generate the HTML content for the dashboard."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WAN Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }
        /* Make the cumulative chart shorter and fixed-height to prevent growth */
        .cumulative-container {
            height: 35vh; /* about a third of viewport height */
            position: relative;
        }
        #cumulativeChart {
            width: 100% !important;
            height: calc(100% - 28px) !important; /* leave room for title */
            display: block;
        }
        /* Interface area shows at least one full row */
        .interface-grid {
            grid-auto-rows: 25vh; /* each chart card height */
        }
        .interface-chart {
            height: 25vh;
            display: flex;
            flex-direction: column;
        }
        .interface-chart canvas {
            width: 100% !important;
            height: calc(100% - 24px) !important; /* leave room for title */
            display: block;
        }
        .status {
            text-align: center;
            margin: 20px 0;
            padding: 10px;
            background: #e8f5e8;
            border-radius: 4px;
            color: #2d5a2d;
        }
        .interface-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .interface-chart {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .interface-title {
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 id="dashboardTitle">Ericsson Live WAN Interface Dashboard</h1>
            <div class="status" id="status">
                Loading data...
            </div>
        </div>
        
        <div class="chart-container cumulative-container">
            <div class="chart-title">Cumulative WAN Traffic</div>
            <canvas id="cumulativeChart"></canvas>
        </div>
        
        <div class="interface-grid" id="interfaceGrid">
            <!-- Individual interface charts will be added here -->
        </div>
    </div>

    <script>
        let cumulativeChart;
        let interfaceCharts = {};
        let updateInterval;
        
        // Initialize the dashboard
        function initDashboard() {
            createCumulativeChart();
            fetchData();
            
            // Set up auto-refresh
            updateInterval = setInterval(fetchData, 3000); // Default 3 seconds
        }
        
        // Create the cumulative traffic chart
        function createCumulativeChart() {
            const ctx = document.getElementById('cumulativeChart').getContext('2d');
            cumulativeChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Download (Mbps)',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1
                    }, {
                        label: 'Upload (Mbps)',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Mbps'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Time'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true
                        }
                    }
                }
            });
        }
        
        // Fetch data from the API
        async function fetchData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                updateCharts(data);
                updateStatus(`Last updated: ${new Date().toLocaleTimeString()}`);
                
                // Update refresh interval if changed
                if (data.update_interval && data.update_interval !== updateInterval / 1000) {
                    clearInterval(updateInterval);
                    updateInterval = setInterval(fetchData, data.update_interval * 1000);
                }
            } catch (error) {
                console.error('Error fetching data:', error);
                updateStatus('Error fetching data');
            }
        }
        
        // Update all charts with new data
        function updateCharts(data) {
            // Update dashboard title with router name
            if (data.router_name) {
                document.getElementById('dashboardTitle').textContent = 
                    `Ericsson Live WAN Interface Dashboard - ${data.router_name}`;
            }
            
            // Update cumulative chart
            cumulativeChart.data.labels = data.timestamps;
            cumulativeChart.data.datasets[0].data = data.cumulative.in;
            cumulativeChart.data.datasets[1].data = data.cumulative.out;
            cumulativeChart.update('none');
            
            // Update interface charts
            updateInterfaceCharts(data.interfaces, data.timestamps, data.interface_info);
        }
        
        // Update individual interface charts
        function updateInterfaceCharts(interfaces, timestamps, interfaceInfo) {
            const grid = document.getElementById('interfaceGrid');
            
            // Get current interface names
            const currentInterfaceNames = Object.keys(interfaces);
            const existingInterfaceNames = Object.keys(interfaceCharts);
            
            // Remove charts for interfaces that no longer exist
            existingInterfaceNames.forEach(interfaceName => {
                if (!currentInterfaceNames.includes(interfaceName)) {
                    // Remove chart container
                    const chartContainer = document.getElementById(`container_${interfaceName}`);
                    if (chartContainer) {
                        chartContainer.remove();
                    }
                    // Destroy chart instance
                    if (interfaceCharts[interfaceName]) {
                        interfaceCharts[interfaceName].destroy();
                        delete interfaceCharts[interfaceName];
                    }
                }
            });
            
            // Update or create charts for current interfaces
            currentInterfaceNames.forEach(interfaceName => {
                const interfaceData = interfaces[interfaceName];
                
                if (interfaceCharts[interfaceName]) {
                    // Update existing chart
                    interfaceCharts[interfaceName].data.labels = timestamps;
                    interfaceCharts[interfaceName].data.datasets[0].data = interfaceData.in;
                    interfaceCharts[interfaceName].data.datasets[1].data = interfaceData.out;
                    interfaceCharts[interfaceName].update('none');
                } else {
                    // Create new chart container
                    const chartContainer = document.createElement('div');
                    chartContainer.className = 'interface-chart';
                    chartContainer.id = `container_${interfaceName}`;
                const displayName = interfaceInfo[interfaceName] || interfaceName;
                chartContainer.innerHTML = `
                    <div class="interface-title">${displayName}</div>
                    <canvas id="chart_${interfaceName}"></canvas>
                `;
                    grid.appendChild(chartContainer);
                    
                    // Create new chart
                    const ctx = document.getElementById(`chart_${interfaceName}`).getContext('2d');
                    interfaceCharts[interfaceName] = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: timestamps,
                            datasets: [{
                                label: 'Download (Mbps)',
                                data: interfaceData.in,
                                borderColor: 'rgb(75, 192, 192)',
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                tension: 0.1
                            }, {
                                label: 'Upload (Mbps)',
                                data: interfaceData.out,
                                borderColor: 'rgb(255, 99, 132)',
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                tension: 0.1
                            }]
                        },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: {
                                        display: true,
                                        text: 'Mbps'
                                    }
                                },
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Time'
                                    }
                                }
                            },
                            plugins: {
                                legend: {
                                    display: true
                                }
                            }
                        }
                    });
                }
            });
        }
        
        // Update status message
        function updateStatus(message) {
            document.getElementById('status').textContent = message;
        }
        
        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', initDashboard);
    </script>
</body>
</html>
        """


def main():
    """Main application entry point."""
    try:
        dashboard = WANDashboard()
        dashboard.start()
    except Exception as e:
        cp.log(f'Error starting WAN Dashboard: {e}')
        raise


if __name__ == '__main__':
    main()
