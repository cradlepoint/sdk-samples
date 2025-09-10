![image](https://github.com/cradlepoint/sdk-samples/assets/7169690/656231d7-7b60-4670-8bd3-c7b66ae0955e)

# Mobile Site Survey: Cellular Network Drive Testing Application

## Overview

Mobile Site Survey is a comprehensive cellular network assessment platform designed for drive testing and stationary deployment evaluation. The application performs automated network performance measurements, collecting geospatial data, cellular signal diagnostics, and network throughput metrics for comprehensive coverage analysis.

**GPS Requirement**: This application requires active GPS connectivity and location lock for proper operation. All testing functions depend on accurate GPS positioning data.

## System Requirements

- **Hardware**: Cellular modem(s) with active connectivity
- **Positioning**: GPS antenna with location lock capability (required)
- **Network**: Router with web interface access

## Web Interface Configuration

The application provides a web-based management interface accessible via:

- **Local Access**: HTTP service on port 8000
- **Remote Access**: NetCloud Manager Remote Connect to 127.0.0.1:8000 (HTTP only)
- **Network Configuration**: Configure firewall rules to forward Primary LAN Zone to Router Zone with Default Allow All policy

## Core Functionality

### Manual Survey Execution
- **Execute Manual Survey**: Initiate immediate testing via web interface control
- **Browse Surveys**: Access web interface for CSV result downloads
- **Configuration Persistence**: Save Mobile Site Survey configuration to router storage

### Automated Testing Parameters

**Distance-Based Testing**
- **Enabled**: Automatic test execution based on geospatial movement (requires GPS)
- **Distance Threshold**: Configurable minimum distance (meters) between test executions
- **Geospatial Triggering**: Automatic test initiation based on GPS position changes

**Time-Based Testing**
- **Timed Tests**: Configurable time intervals (seconds) between test cycles
- **Scheduled Execution**: Automated testing based on time-based triggers

**Note**: Distance and time-based testing can be enabled simultaneously. New test cycles are queued until current interface diagnostics complete.

## Testing Configuration Options

### Interface Testing
- **Multi-Interface Support**: Test all connected WAN interfaces including Ethernet and Wi-Fi-as-WAN
- **Cellular-Only Mode**: Disable non-cellular interface testing

### Performance Measurement
- **Speed Testing**: Ookla TCP upload/download performance tests
- **Latency Measurement**: ICMP ping to 8.8.8.8 (fallback when speed tests disabled)

### Data Management
- **CSV Export**: Write test results to router flash storage (accessible via HTTP)
- **Debug Logging**: Enhanced diagnostic logging for troubleshooting

## Server Integration

**Powered by 5g-ready.io**

### Data Transmission
- **HTTP POST Integration**: Automated results transmission to remote server
- **Comprehensive Diagnostics**: Optional transmission of full interface diagnostics
- **Log Transmission**: Application logs for server-side troubleshooting

### Authentication
- **Server URL**: Configurable HTTP endpoint (e.g., https://5g-ready.io/injector)
- **Bearer Token Authentication**: Optional server authentication token

## Multi-Router Synchronization

### Surveyor Coordination
- **Synchronized Testing**: Coordinate testing across multiple router instances
- **Network Requirements**: Ensure routers are accessible on port 8000
- **IP Configuration**: Comma-separated list of remote router IP addresses

## Data Collection Schema

The application collects the following metrics by default:
- **Temporal**: Timestamp
- **Geospatial**: Latitude, Longitude (GPS-dependent)
- **Network Identity**: Carrier, Cell ID, Service Display, Band
- **Signal Quality**: RSSI, SINR, RSRP, RSRQ
- **Performance**: Download/Upload speeds, Latency
- **Traffic Statistics**: Bytes Sent, Bytes Received
- **Reference**: Results URL

## Default Configuration

The application operates with the following default parameters:
- **Test Interval**: 50-meter distance threshold
- **Speed Testing**: Enabled
- **Data Export**: CSV format to router flash storage

## Configuration Management

Default settings can be modified in `settings.py` for custom deployment requirements.
