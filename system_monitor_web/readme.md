# System Monitor Web Application

A comprehensive real-time system monitoring application for Cradlepoint routers that tracks both memory and CPU usage with customizable alert thresholds and a professional web interface.

## Features

### 📊 **Real-time Monitoring**
- **Memory Usage**: Total, used, and free memory tracking
- **CPU Usage**: Total, user, system, and nice process CPU utilization
- **Historical Data**: Min/max values with timestamps
- **Data Visualization**: Interactive charts with time-based axes

### 🚨 **Alert System**
- **Customizable Thresholds**: Set memory and CPU alert levels
- **Smart Alerting**: Prevents alert spam with intelligent reset logic
- **System Integration**: Uses Cradlepoint's native `cp.alert()` system

### 🎨 **Professional Web Interface**
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Auto-refreshes every 10 seconds
- **Loading Indicators**: Shows data collection progress
- **Export Functionality**: Download data as JSON

## Installation

1. **Upload Application**: Upload the `system_monitor_web.tar.gz` file to the Tools page in NetCloud Manager
2. **Assign to Groups**: Assign the application to the desired router groups
3. **Application Deployment**: The application will automatically deploy and start on assigned routers

## Access Methods

### Local Access
- **Direct Browser**: Navigate to `http://[router-ip-address]:8000` in your web browser
- **PrimaryLAN Zone Forwarding**: Forward the PrimaryLAN zone to the Router zone to enable local network access

### Remote Access - NetCloud Manager
- **Remote Connect LAN Manager**: 
  - **Protocol**: HTTP
  - **Host**: 127.0.0.1
  - **Port**: 8000

## Dashboard Overview

### 📈 **Statistics Tiles**
- **Current Memory Usage**: Real-time memory percentage
- **Total Memory**: Total available system memory
- **Free Memory**: Available free memory
- **Current CPU Usage**: Real-time CPU percentage
- **CPU User**: User process CPU utilization
- **CPU System**: System process CPU utilization
- **Data Points**: Number of collected measurements
- **Min/Max Values**: Historical extremes with timestamps

### ⚙️ **Alert Configuration**
- **Memory Threshold**: Default 80% (customizable 1-100%)
- **CPU Threshold**: Default 70% (customizable 1-100%)
- **Real-time Updates**: Threshold changes apply immediately

### 📊 **Charts**
- **Memory Usage Chart**: Blue-themed line chart showing memory usage over time
- **CPU Usage Chart**: Red-themed line chart showing CPU usage over time
- **Time-based Axes**: Proper time formatting with hover tooltips

### 📋 **Data Table**
- **Recent Measurements**: Last 10 data points
- **Combined View**: Memory and CPU data in one table
- **Detailed Metrics**: Memory usage, CPU breakdown, timestamps

## Configuration

### Alert Thresholds
- **Memory Alert**: Triggers when memory usage exceeds threshold
- **CPU Alert**: Triggers when CPU usage exceeds threshold
- **Anti-spam Logic**: Alerts reset when usage drops below 90% of threshold

### Data Collection
- **Collection Interval**: 30 seconds between measurements
- **Data Retention**: Last 100 data points (prevents memory bloat)
- **Initial Delay**: First 2 measurements discarded for accurate baseline
