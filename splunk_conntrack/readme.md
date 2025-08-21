# splunk_conntrack
 
Cradlepoint Ericsson -> Splunk Connection Tracking Application

![image](https://github.com/user-attachments/assets/16a4ba8e-d179-46af-8435-3d34d40a20c5)

## Overview

This Cradlepoint SDK application monitors the router's connection tracking table (`conntrack`) and forwards new network connections to Splunk via HTTP Event Collector (HEC) for real-time network traffic analysis.

The application polls the conntrack table every 5 seconds, identifies new connections, and sends them to your Splunk instance for monitoring and analysis.

## SDK Data Requirements

Configure the following parameters under **System > SDK Data**:

| Name           | Value |
|----------------|-------|
| `splunk_url`   | `https://your-splunk-instance.splunkcloud.com:8088/services/collector` |
| `splunk_token` | `your-hec-token-here` |


## Output

Application status and error messages are written to the router logs. Check the router console for startup messages and any configuration or connectivity issues.
