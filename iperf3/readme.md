# User Manual for iPerf3 Application

## Overview
The iPerf3 application is designed to test network performance by measuring the bandwidth between your device and a specified server. This application automates the process of downloading the iPerf3 tool, configuring the server, and running tests. Results are logged, alerted, and stored in the asset identifier for easy access.

## Initial Setup
1. **Download iPerf3**: When the application is first executed, it will automatically download the iPerf3 tool if it is not already present on your device.
2. **Configure Server**: The application will create an entry in the SDK Appdata named `iperf3_server`. You need to enter the server hostname or IP address in this entry to specify where the tests should be directed.

## Running the Application
- **Automatic Testing**: If a server is configured in the SDK Appdata, the application will automatically run a test to that server upon startup.
- **Results Handling**: The results of the test, including download and upload speeds, are:
  - Stored in the `asset_id` field.
  - Written to the router logs.
  - Sent as an alert.
  
  You can modify how results are processed by editing the `process_results()` function at the top of the application code.

## Accessing Results
- **NCM Device Grid**: Test results can be viewed in the NCM (Network Configuration Manager) under the devices grid, specifically in the asset identifier column.
- **NCM API**: Results can also be retrieved programmatically from the `asset_id` field using the NCM API v2 `/routers/` endpoint.

## Triggering a New Test
- To initiate a new test, you can clear the `asset_id` in two ways:
  - **NCM Device Grid**: Clear the `asset_id` directly in the devices grid within NCM.
  - **NCM API**: Set the `asset_id` to an empty string (`""`) using the `/routers/` endpoint in the NCM API v2.

## Customization
- You can customize the behavior of the application, such as how results are processed or where they are stored, by modifying the relevant sections in the code, particularly the `process_results()` function.

This manual provides a basic understanding of how to set up and use the iPerf3 application for network performance testing. For further customization or troubleshooting, refer to the application code and comments.