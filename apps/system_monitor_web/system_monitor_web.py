#!/usr/bin/env python3
"""
System Monitor for Cradlepoint Router
Comprehensive memory and CPU usage tracking with web interface on port 8000
"""

import cp
import time
import json
import threading
import os
from datetime import datetime
import http.server
import socketserver

# Global variables for data storage
memory_data = []
cpu_data = []
data_lock = threading.Lock()

# File storage configuration
DATA_DIR = "/tmp/system_monitor_data"
MEMORY_FILE = f"{DATA_DIR}/memory_data.json"
CPU_FILE = f"{DATA_DIR}/cpu_data.json"
STATS_FILE = f"{DATA_DIR}/stats.json"

# Data retention settings
MAX_DATA_POINTS = 43200  # 30 days worth of data (43200 = 30 days * 24 hours * 60 measurements per hour)
IN_MEMORY_POINTS = 1440  # Keep last 24 hours worth of data in memory (1440 = 24 hours * 60 minutes)

# Global variables for min/max memory tracking
min_memory_usage = None
max_memory_usage = None
min_memory_timestamp = None
max_memory_timestamp = None

# Global variables for min/max CPU tracking
min_cpu_usage = None
max_cpu_usage = None
min_cpu_timestamp = None
max_cpu_timestamp = None

measurements_discarded = 0

# Alert thresholds (customizable)
memory_threshold = 80.0  # Alert when memory usage exceeds 80%
cpu_threshold = 70.0     # Alert when CPU usage exceeds 70%

# Alert state tracking (to prevent spam)
memory_alert_sent = False
cpu_alert_sent = False

def get_memory_info():
    """Get current memory information from router"""
    try:
        memfree = cp.get('status/system/memory/memfree')
        memtotal = cp.get('status/system/memory/memtotal')
        
        if memfree and memtotal:
            memused = memtotal - memfree
            usage_percent = (memused / memtotal) * 100 if memtotal > 0 else 0
            
            return {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'total_mb': memtotal / (1024 * 1024),
                'used_mb': memused / (1024 * 1024),
                'free_mb': memfree / (1024 * 1024),
                'usage_percent': usage_percent
            }
        else:
            cp.log("Could not get memory info from router")
            return None
            
    except Exception as e:
        cp.log(f"Error getting memory info: {e}")
        return None

def get_cpu_info():
    """Get current CPU information from router"""
    try:
        cpu_data = cp.get('status/system/cpu/')
        
        if cpu_data:
            # Calculate total CPU usage (user + system + nice)
            total_usage = cpu_data.get('user', 0) + cpu_data.get('system', 0) + cpu_data.get('nice', 0)
            usage_percent = total_usage * 100  # Convert to percentage
            
            return {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'user_percent': cpu_data.get('user', 0) * 100,
                'system_percent': cpu_data.get('system', 0) * 100,
                'nice_percent': cpu_data.get('nice', 0) * 100,
                'total_percent': usage_percent
            }
        else:
            cp.log("Could not get CPU info from router")
            return None
            
    except Exception as e:
        cp.log(f"Error getting CPU info: {e}")
        return None

def ensure_data_directory():
    """Ensure the data directory exists"""
    try:
        import os
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            cp.log(f"Created data directory: {DATA_DIR}")
    except Exception as e:
        cp.log(f"Error creating data directory: {e}")

def load_data_from_file(filename):
    """Load data from JSON file"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        cp.log(f"Error loading data from {filename}: {e}")
        return []

def save_data_to_file(data, filename):
    """Save data to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        cp.log(f"Error saving data to {filename}: {e}")

def load_stats_from_file():
    """Load min/max stats from file"""
    global min_memory_usage, max_memory_usage, min_memory_timestamp, max_memory_timestamp
    global min_cpu_usage, max_cpu_usage, min_cpu_timestamp, max_cpu_timestamp
    
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
                min_memory_usage = stats.get('min_memory_usage')
                max_memory_usage = stats.get('max_memory_usage')
                min_memory_timestamp = stats.get('min_memory_timestamp')
                max_memory_timestamp = stats.get('max_memory_timestamp')
                min_cpu_usage = stats.get('min_cpu_usage')
                max_cpu_usage = stats.get('max_cpu_usage')
                min_cpu_timestamp = stats.get('min_cpu_timestamp')
                max_cpu_timestamp = stats.get('max_cpu_timestamp')
                cp.log("Loaded stats from file")
    except Exception as e:
        cp.log(f"Error loading stats from file: {e}")

def save_stats_to_file():
    """Save min/max stats to file"""
    try:
        stats = {
            'min_memory_usage': min_memory_usage,
            'max_memory_usage': max_memory_usage,
            'min_memory_timestamp': min_memory_timestamp,
            'max_memory_timestamp': max_memory_timestamp,
            'min_cpu_usage': min_cpu_usage,
            'max_cpu_usage': max_cpu_usage,
            'min_cpu_timestamp': min_cpu_timestamp,
            'max_cpu_timestamp': max_cpu_timestamp
        }
        save_data_to_file(stats, STATS_FILE)
    except Exception as e:
        cp.log(f"Error saving stats to file: {e}")

def check_and_send_alerts(memory_info, cpu_info):
    """Check thresholds and send alerts if needed"""
    global memory_alert_sent, cpu_alert_sent
    
    try:
        # Check memory threshold
        if memory_info and memory_info['usage_percent'] > memory_threshold:
            if not memory_alert_sent:
                cp.alert(f"Memory usage alert: {memory_info['usage_percent']:.1f}% exceeds threshold of {memory_threshold}%")
                memory_alert_sent = True
                cp.log(f"Memory alert sent: {memory_info['usage_percent']:.1f}% > {memory_threshold}%")
        elif memory_info and memory_info['usage_percent'] <= memory_threshold * 0.9:  # Reset when below 90% of threshold
            memory_alert_sent = False
        
        # Check CPU threshold
        if cpu_info and cpu_info['total_percent'] > cpu_threshold:
            if not cpu_alert_sent:
                cp.alert(f"CPU usage alert: {cpu_info['total_percent']:.1f}% exceeds threshold of {cpu_threshold}%")
                cpu_alert_sent = True
                cp.log(f"CPU alert sent: {cpu_info['total_percent']:.1f}% > {cpu_threshold}%")
        elif cpu_info and cpu_info['total_percent'] <= cpu_threshold * 0.9:  # Reset when below 90% of threshold
            cpu_alert_sent = False
            
    except Exception as e:
        cp.log(f"Error checking alerts: {e}")

def system_monitor():
    """Background thread to monitor memory and CPU usage"""
    global min_memory_usage, max_memory_usage, min_memory_timestamp, max_memory_timestamp
    global min_cpu_usage, max_cpu_usage, min_cpu_timestamp, max_cpu_timestamp, measurements_discarded
    global memory_data, cpu_data
    
    cp.log("Starting system monitoring thread...")
    
    # Ensure data directory exists
    ensure_data_directory()
    
    # Load existing data and stats
    memory_data = load_data_from_file(MEMORY_FILE)
    cpu_data = load_data_from_file(CPU_FILE)
    load_stats_from_file()
    
    cp.log(f"Loaded {len(memory_data)} memory data points and {len(cpu_data)} CPU data points")
    
    while True:
        try:
            memory_info = get_memory_info()
            cpu_info = get_cpu_info()
            
            if memory_info and cpu_info:
                with data_lock:
                    # Discard the first 2 measurements as they're before the app consumes resources
                    if measurements_discarded < 2:
                        measurements_discarded += 1
                        cp.log(f"Discarding measurement {measurements_discarded}/2 (before app resource consumption)")
                        time.sleep(60)  # Wait for next measurement
                        continue
                    
                    # Store memory data
                    memory_data.append(memory_info)
                    
                    # Store CPU data
                    cpu_data.append(cpu_info)
                    
                    # Keep only recent data in memory for fast access
                    if len(memory_data) > IN_MEMORY_POINTS:
                        memory_data = memory_data[-IN_MEMORY_POINTS:]
                    
                    if len(cpu_data) > IN_MEMORY_POINTS:
                        cpu_data = cpu_data[-IN_MEMORY_POINTS:]
                    
                    # Save all data to files periodically (every 10 measurements = 10 minutes)
                    if len(memory_data) % 10 == 0:
                        # Load full data from files
                        full_memory_data = load_data_from_file(MEMORY_FILE)
                        full_cpu_data = load_data_from_file(CPU_FILE)
                        
                        # Add new data
                        full_memory_data.append(memory_info)
                        full_cpu_data.append(cpu_info)
                        
                        # Limit to MAX_DATA_POINTS (30 days worth)
                        if len(full_memory_data) > MAX_DATA_POINTS:
                            full_memory_data = full_memory_data[-MAX_DATA_POINTS:]
                        if len(full_cpu_data) > MAX_DATA_POINTS:
                            full_cpu_data = full_cpu_data[-MAX_DATA_POINTS:]
                        
                        # Save to files
                        save_data_to_file(full_memory_data, MEMORY_FILE)
                        save_data_to_file(full_cpu_data, CPU_FILE)
                        cp.log(f"Saved data to files. Memory: {len(full_memory_data)} points, CPU: {len(full_cpu_data)} points")
                    
                    # Update memory min/max tracking
                    current_memory_usage = memory_info['usage_percent']
                    current_timestamp = memory_info['timestamp']
                    
                    if min_memory_usage is None or current_memory_usage < min_memory_usage:
                        min_memory_usage = current_memory_usage
                        min_memory_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    if max_memory_usage is None or current_memory_usage > max_memory_usage:
                        max_memory_usage = current_memory_usage
                        max_memory_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    # Update CPU min/max tracking
                    current_cpu_usage = cpu_info['total_percent']
                    
                    if min_cpu_usage is None or current_cpu_usage < min_cpu_usage:
                        min_cpu_usage = current_cpu_usage
                        min_cpu_timestamp = current_timestamp
                        save_stats_to_file()
                    
                    if max_cpu_usage is None or current_cpu_usage > max_cpu_usage:
                        max_cpu_usage = current_cpu_usage
                        max_cpu_timestamp = current_timestamp
                        save_stats_to_file()
                
                cp.log(f"Memory: {memory_info['usage_percent']:.1f}% used ({memory_info['used_mb']:.1f}MB / {memory_info['total_mb']:.1f}MB)")
                cp.log(f"CPU: {cpu_info['total_percent']:.1f}% total (User: {cpu_info['user_percent']:.1f}%, System: {cpu_info['system_percent']:.1f}%, Nice: {cpu_info['nice_percent']:.1f}%)")
                
                # Check and send alerts
                check_and_send_alerts(memory_info, cpu_info)
            
            time.sleep(60)  # Check every 60 seconds (1 minute)
            
        except Exception as e:
            cp.log(f"Error in system monitor: {e}")
            time.sleep(60)

def create_html_page():
    """Create the HTML page for the web interface"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>System Monitor</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            color: #333;
            border-bottom: 2px solid #007cba;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .current-time {
            font-size: 1.2em;
            font-weight: bold;
            color: #007cba;
            margin-top: 10px;
            font-family: 'Courier New', monospace;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            border-left: 4px solid #007cba;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #007cba;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .stat-timestamp {
            color: #999;
            font-size: 0.8em;
            margin-top: 3px;
        }
        .loading-indicator {
            background: #e3f2fd;
            border: 2px solid #2196f3;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            display: block;
        }
        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #2196f3;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-text {
            font-size: 1.2em;
            color: #1976d2;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .loading-progress {
            color: #666;
            font-size: 0.9em;
        }
        .chart-container {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            position: relative;
            height: 400px;
            overflow: hidden;
        }
        .chart-container canvas {
            max-height: 100%;
            max-width: 100%;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .data-table th, .data-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .data-table th {
            background-color: #007cba;
            color: white;
        }
        .data-table tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }
        .controls {
            text-align: center;
            margin-bottom: 20px;
        }
        .btn {
            background: #007cba;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 5px;
        }
        .btn:hover {
            background: #005a87;
        }
        .thresholds-section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #28a745;
        }
        .thresholds-section h3 {
            margin-top: 0;
            color: #28a745;
        }
        .threshold-controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        .threshold-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .threshold-item label {
            font-weight: bold;
            color: #333;
            min-width: 150px;
        }
        .threshold-item input {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 80px;
        }
        .btn-small {
            padding: 6px 12px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>System Monitor</h1>
            <p>Real-time memory and CPU monitoring on Cradlepoint Routers</p>
            <div class="current-time" id="current-time">--</div>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="current-memory">--</div>
                <div class="stat-label">Current Memory Usage</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-memory">--</div>
                <div class="stat-label">Total Memory</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="free-memory">--</div>
                <div class="stat-label">Free Memory</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="current-cpu">--</div>
                <div class="stat-label">Current CPU Usage</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="cpu-user">--</div>
                <div class="stat-label">CPU User</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="cpu-system">--</div>
                <div class="stat-label">CPU System</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="data-points">--</div>
                <div class="stat-label">Data Points</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="min-memory">--</div>
                <div class="stat-label">Min Memory Usage</div>
                <div class="stat-timestamp" id="min-timestamp">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="max-memory">--</div>
                <div class="stat-label">Max Memory Usage</div>
                <div class="stat-timestamp" id="max-timestamp">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="min-cpu">--</div>
                <div class="stat-label">Min CPU Usage</div>
                <div class="stat-timestamp" id="min-cpu-timestamp">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="max-cpu">--</div>
                <div class="stat-label">Max CPU Usage</div>
                <div class="stat-timestamp" id="max-cpu-timestamp">--</div>
            </div>
        </div>
        
        <div class="loading-indicator" id="loading-indicator">
            <div class="loading-spinner"></div>
            <div class="loading-text">Collecting initial data... Please wait</div>
            <div class="loading-progress" id="loading-progress">Discarded: 0/2 measurements</div>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="refreshData()">Refresh Data</button>
            <button class="btn" onclick="exportData()">Export Data</button>
        </div>
        
        <div class="thresholds-section">
            <h3>Alert Thresholds</h3>
            <div class="threshold-controls">
                <div class="threshold-item">
                    <label for="memory-threshold">Memory Alert Threshold (%):</label>
                    <input type="number" id="memory-threshold" min="1" max="100" value="80" step="1">
                    <button class="btn btn-small" onclick="updateMemoryThreshold()">Update</button>
                </div>
                <div class="threshold-item">
                    <label for="cpu-threshold">CPU Alert Threshold (%):</label>
                    <input type="number" id="cpu-threshold" min="1" max="100" value="70" step="1">
                    <button class="btn btn-small" onclick="updateCpuThreshold()">Update</button>
                </div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Memory Usage Over Time</h3>
            <canvas id="memoryChart"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>CPU Usage Over Time</h3>
            <canvas id="cpuChart"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>Recent System Data</h3>
            <table class="data-table" id="dataTable">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Memory %</th>
                        <th>Memory Used (MB)</th>
                        <th>CPU Total %</th>
                        <th>CPU User %</th>
                        <th>CPU System %</th>
                    </tr>
                </thead>
                <tbody id="dataTableBody">
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>System Monitor Web Application | Last updated: <span id="last-update">--</span></p>
        </div>
    </div>

    <script>
        let memoryChart;
        let cpuChart;
        
        // Initialize memory chart
        function initMemoryChart() {
            const canvas = document.getElementById('memoryChart');
            const ctx = canvas.getContext('2d');
            
            // Create gradient
            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, 'rgba(0, 124, 186, 0.8)');
            gradient.addColorStop(1, 'rgba(0, 124, 186, 0.1)');
            
            memoryChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Memory Usage (%)',
                        data: [],
                        borderColor: '#007cba',
                        backgroundColor: gradient,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                displayFormats: {
                                    second: 'HH:mm:ss',
                                    minute: 'HH:mm',
                                    hour: 'HH:mm'
                                },
                                tooltipFormat: 'HH:mm:ss'
                            },
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                maxTicksLimit: 10,
                                maxRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Memory Usage (%)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    return 'Time: ' + context[0].label;
                                },
                                label: function(context) {
                                    return 'Memory Usage: ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    layout: {
                        padding: {
                            top: 10,
                            bottom: 10
                        }
                    }
                }
            });
        }
        
        // Initialize CPU chart
        function initCpuChart() {
            const canvas = document.getElementById('cpuChart');
            const ctx = canvas.getContext('2d');
            
            // Create gradient
            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, 'rgba(220, 53, 69, 0.8)');
            gradient.addColorStop(1, 'rgba(220, 53, 69, 0.1)');
            
            cpuChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU Usage (%)',
                        data: [],
                        borderColor: '#dc3545',
                        backgroundColor: gradient,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                displayFormats: {
                                    second: 'HH:mm:ss',
                                    minute: 'HH:mm',
                                    hour: 'HH:mm'
                                },
                                tooltipFormat: 'HH:mm:ss'
                            },
                            title: {
                                display: true,
                                text: 'Time'
                            },
                            ticks: {
                                maxTicksLimit: 10,
                                maxRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: 'CPU Usage (%)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    return 'Time: ' + context[0].label;
                                },
                                label: function(context) {
                                    return 'CPU Usage: ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    layout: {
                        padding: {
                            top: 10,
                            bottom: 10
                        }
                    }
                }
            });
        }
        
        // Update memory chart with data
        function updateMemoryChart(data) {
            const chartData = data.map(item => ({
                x: new Date('2024-01-01 ' + item.timestamp),
                y: item.usage_percent
            }));
            
            memoryChart.data.datasets[0].data = chartData;
            memoryChart.update();
        }
        
        // Update CPU chart with data
        function updateCpuChart(data) {
            const chartData = data.map(item => ({
                x: new Date('2024-01-01 ' + item.timestamp),
                y: item.total_percent
            }));
            
            cpuChart.data.datasets[0].data = chartData;
            cpuChart.update();
        }
        
        // Update statistics
        function updateStats(memoryData, cpuData, minMemoryUsage, maxMemoryUsage, minMemoryTimestamp, maxMemoryTimestamp, minCpuUsage, maxCpuUsage, minCpuTimestamp, maxCpuTimestamp) {
            if (memoryData.length > 0) {
                const latestMemory = memoryData[memoryData.length - 1];
                document.getElementById('current-memory').textContent = latestMemory.usage_percent.toFixed(1) + '%';
                document.getElementById('total-memory').textContent = (latestMemory.total_mb / 1024).toFixed(1) + ' GB';
                document.getElementById('free-memory').textContent = (latestMemory.free_mb / 1024).toFixed(1) + ' GB';
                document.getElementById('data-points').textContent = memoryData.length;
                document.getElementById('last-update').textContent = latestMemory.timestamp;
                
                // Update memory min/max values
                if (minMemoryUsage !== null) {
                    document.getElementById('min-memory').textContent = minMemoryUsage.toFixed(1) + '%';
                    document.getElementById('min-timestamp').textContent = minMemoryTimestamp || '--';
                }
                if (maxMemoryUsage !== null) {
                    document.getElementById('max-memory').textContent = maxMemoryUsage.toFixed(1) + '%';
                    document.getElementById('max-timestamp').textContent = maxMemoryTimestamp || '--';
                }
            }
            
            if (cpuData.length > 0) {
                const latestCpu = cpuData[cpuData.length - 1];
                document.getElementById('current-cpu').textContent = latestCpu.total_percent.toFixed(1) + '%';
                document.getElementById('cpu-user').textContent = latestCpu.user_percent.toFixed(1) + '%';
                document.getElementById('cpu-system').textContent = latestCpu.system_percent.toFixed(1) + '%';
                
                // Update CPU min/max values
                if (minCpuUsage !== null) {
                    document.getElementById('min-cpu').textContent = minCpuUsage.toFixed(1) + '%';
                    document.getElementById('min-cpu-timestamp').textContent = minCpuTimestamp || '--';
                }
                if (maxCpuUsage !== null) {
                    document.getElementById('max-cpu').textContent = maxCpuUsage.toFixed(1) + '%';
                    document.getElementById('max-cpu-timestamp').textContent = maxCpuTimestamp || '--';
                }
            }
        }
        
        // Update current time
        function updateTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', { 
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            const dateString = now.toLocaleDateString('en-US', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });
            document.getElementById('current-time').textContent = `${dateString} ${timeString}`;
        }
        
        // Update loading indicator
        function updateLoadingIndicator(isLoading, measurementsDiscarded) {
            const loadingIndicator = document.getElementById('loading-indicator');
            const loadingProgress = document.getElementById('loading-progress');
            
            if (isLoading) {
                loadingIndicator.style.display = 'block';
                loadingProgress.textContent = `Discarded: ${measurementsDiscarded}/2 measurements`;
            } else {
                loadingIndicator.style.display = 'none';
            }
        }
        
        // Update data table
        function updateTable(memoryData, cpuData) {
            const tbody = document.getElementById('dataTableBody');
            tbody.innerHTML = '';
            
            // Show last 10 data points
            const recentMemoryData = memoryData.slice(-10).reverse();
            const recentCpuData = cpuData.slice(-10).reverse();
            
            // Use the shorter array length to avoid mismatched data
            const maxLength = Math.min(recentMemoryData.length, recentCpuData.length);
            
            for (let i = 0; i < maxLength; i++) {
                const memoryItem = recentMemoryData[i];
                const cpuItem = recentCpuData[i];
                
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${memoryItem.timestamp}</td>
                    <td>${memoryItem.usage_percent.toFixed(1)}%</td>
                    <td>${memoryItem.used_mb.toFixed(1)}</td>
                    <td>${cpuItem.total_percent.toFixed(1)}%</td>
                    <td>${cpuItem.user_percent.toFixed(1)}%</td>
                    <td>${cpuItem.system_percent.toFixed(1)}%</td>
                `;
            }
        }
        
        // Fetch data from server
        async function fetchData() {
            try {
                const response = await fetch('/api/system-data');
                const data = await response.json();
                
                // Update loading indicator
                updateLoadingIndicator(data.is_loading, data.measurements_discarded);
                
                if (!data.is_loading) {
                    updateMemoryChart(data.memory_data);
                    updateCpuChart(data.cpu_data);
                    updateStats(data.memory_data, data.cpu_data, data.min_memory_usage, data.max_memory_usage, data.min_memory_timestamp, data.max_memory_timestamp, data.min_cpu_usage, data.max_cpu_usage, data.min_cpu_timestamp, data.max_cpu_timestamp);
                    updateTable(data.memory_data, data.cpu_data);
                }
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        
        // Refresh data
        function refreshData() {
            fetchData();
        }
        
        // Export data
        function exportData() {
            fetch('/api/export-data')
                .then(response => response.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'memory_data.json';
                    a.click();
                    window.URL.revokeObjectURL(url);
                });
        }
        
        // Update memory threshold
        function updateMemoryThreshold() {
            const threshold = document.getElementById('memory-threshold').value;
            fetch(`/api/update-threshold?memory=${threshold}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert(`Memory threshold updated to ${threshold}%`);
                    } else {
                        alert('Error updating memory threshold: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error updating memory threshold: ' + error);
                });
        }
        
        // Update CPU threshold
        function updateCpuThreshold() {
            const threshold = document.getElementById('cpu-threshold').value;
            fetch(`/api/update-threshold?cpu=${threshold}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert(`CPU threshold updated to ${threshold}%`);
                    } else {
                        alert('Error updating CPU threshold: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error updating CPU threshold: ' + error);
                });
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            // Show loading indicator immediately
            document.getElementById('loading-indicator').style.display = 'block';
            
            // Initialize time display
            updateTime();
            setInterval(updateTime, 1000); // Update time every second
            
            // Fetch data immediately to check loading state
            fetchData();
            
            // Load Chart.js and time adapter from CDN
            const chartScript = document.createElement('script');
            chartScript.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            chartScript.onload = function() {
                const timeAdapterScript = document.createElement('script');
                timeAdapterScript.src = 'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns';
                timeAdapterScript.onload = function() {
                    initMemoryChart();
                    initCpuChart();
                    // Auto-refresh every 60 seconds (1 minute)
                    setInterval(fetchData, 60000);
                };
                document.head.appendChild(timeAdapterScript);
            };
            document.head.appendChild(chartScript);
        });
    </script>
</body>
</html>
    """
    return html

def start_web_server():
    """Start a simple HTTP server on port 8000"""
    class MemoryTrackerHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(create_html_page().encode())
            elif self.path == '/api/system-data':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with data_lock:
                    data = {
                        'memory_data': memory_data,
                        'cpu_data': cpu_data,
                        'min_memory_usage': min_memory_usage,
                        'max_memory_usage': max_memory_usage,
                        'min_memory_timestamp': min_memory_timestamp,
                        'max_memory_timestamp': max_memory_timestamp,
                        'min_cpu_usage': min_cpu_usage,
                        'max_cpu_usage': max_cpu_usage,
                        'min_cpu_timestamp': min_cpu_timestamp,
                        'max_cpu_timestamp': max_cpu_timestamp,
                        'measurements_discarded': measurements_discarded,
                        'is_loading': measurements_discarded < 2
                    }
                self.wfile.write(json.dumps(data).encode())
            elif self.path == '/api/export-data':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Content-Disposition', 'attachment; filename=memory_data.json')
                self.end_headers()
                with data_lock:
                    data = json.dumps(memory_data, indent=2)
                self.wfile.write(data.encode())
            elif self.path.startswith('/api/update-threshold'):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                # Parse query parameters
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(self.path)
                params = parse_qs(parsed_url.query)
                
                try:
                    if 'memory' in params:
                        global memory_threshold
                        memory_threshold = float(params['memory'][0])
                        cp.log(f"Memory threshold updated to: {memory_threshold}%")
                    elif 'cpu' in params:
                        global cpu_threshold
                        cpu_threshold = float(params['cpu'][0])
                        cp.log(f"CPU threshold updated to: {cpu_threshold}%")
                    
                    response = {'status': 'success'}
                except Exception as e:
                    response = {'status': 'error', 'message': str(e)}
                
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()
    
    try:
        with socketserver.TCPServer(("", 8000), MemoryTrackerHandler) as httpd:
            cp.log("Web server started on port 8000")
            httpd.serve_forever()
    except Exception as e:
        cp.log(f"Error starting web server: {e}")

def main():
    """Main application entry point"""
    cp.log("Starting System Monitor Web Application...")
    
    # Start system monitoring in background thread
    monitor_thread = threading.Thread(target=system_monitor, daemon=True)
    monitor_thread.start()
    
    # Start web server
    start_web_server()

if __name__ == "__main__":
    main()
