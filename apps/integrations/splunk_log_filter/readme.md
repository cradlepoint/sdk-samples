# splunk_log_filter
 
Ericsson Cradlepoint -> Splunk Log Filtering Application

![image](https://github.com/user-attachments/assets/353000e8-607f-4782-93b8-42e837236ff3)

## Overview

This Cradlepoint SDK application monitors the router's system logs and forwards filtered log entries to Splunk via HTTP Event Collector (HEC) for centralized log analysis and monitoring.

The application continuously monitors router logs for specific filter patterns (configurable via SDK data parameters) and sends matching log entries to your Splunk instance. This enables real-time log monitoring, alerting, and analysis of critical router events such as SSH session starts/ends, authentication events, and other system activities.

## SDK Data Requirements

Configure the following parameters under **System > SDK Data**:

| Name           | Value |
|----------------|-------|
| `splunk_url`   | `https://your-splunk-instance.splunkcloud.com:8088/services/collector` |
| `splunk_token` | `your-hec-token-here` |
| `splunk_filter` | `Client SSH session started` |
| `splunk_filter2` | `Client session ended` |

## Output

Application status and error messages are written to the router logs. Check the router console for startup messages and any configuration or connectivity issues.
