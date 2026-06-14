# System Monitor Web Application

![Python](https://img.shields.io/badge/Python-3.8-yellow) ![Web App](https://img.shields.io/badge/Interface-Web_App-blue)

A comprehensive real-time system monitoring application for Cradlepoint routers that tracks both memory and CPU usage with customizable alert thresholds and a professional web interface.

![image](https://github.com/user-attachments/assets/0d27b139-5550-4c57-a204-d65f78327ec3)
![image](https://github.com/user-attachments/assets/3f7db1ce-1139-47e5-80f0-0981dd3fc351)
![image](https://github.com/user-attachments/assets/3cab8d51-0ead-499d-b5e4-f736fa8b7b81)

## Features

### 📊 **Real-time Monitoring**
- **Memory Usage**: Total, used, and free memory tracking
- **CPU Usage**: Total, user, system, and nice process CPU utilization
- **Historical Data**: Min/max values with timestamps
- **Data Visualization**: Interactive charts with time-based axes
- **Data Retention**: 24 hours in memory, 30 days on disk

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
- **Data Range**: 24 hours of data displayed with smooth scrolling

### 📋 **Data Table**
- **Recent Measurements**: Last 10 data points
- **Combined View**: Memory and CPU data in one table
- **Detailed Metrics**: Memory usage, CPU breakdown, timestamps
- **Data Coverage**: 24 hours of data available instantly in memory

## Configuration

### Alert Thresholds
- **Memory Alert**: Triggers when memory usage exceeds threshold
- **CPU Alert**: Triggers when CPU usage exceeds threshold
- **Anti-spam Logic**: Alerts reset when usage drops below 90% of threshold

### Data Collection
- **Collection Interval**: 60 seconds (1 minute) between measurements
- **In-Memory Data**: Last 24 hours (1,440 data points) kept in memory for fast access
- **File Storage**: 30 days (43,200 data points) stored on disk for long-term analysis
- **Initial Delay**: First 2 measurements discarded for accurate baseline
- **File Writes**: Data saved to disk every 10 minutes (10 measurements)

