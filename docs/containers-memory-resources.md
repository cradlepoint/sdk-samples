# Adjusting Memory Resources for NetCloud Container Orchestrator

Source: https://docs.cradlepoint.com/r/Adjusting-Memory-Resources-for-NetCloud-Container-Orchestrator

## Overview

This document provides the memory limits imposed on NetCloud Container Orchestrator across various Ericsson Cradlepoint router models.

---

## Memory Resources

The memory resources available for containers vary for different endpoints to allow key services enough memory to run without significant impact to performance. The key services include:
- 
Wi-Fi connectivity
- 
Analytics, intrusion detection systems/intrusion prevention systems (IPS/IDS) such as Trend Engine
If these key services are not being utilized on the endpoint in its deployment, they may be disabled to allow NetCloud Container Orchestrator to use that memory instead. The following tables illustrate the available memory on Ericsson Cradlepoint endpoints that support NetCloud Orchestrator with and without key services enabled.Table 1. Available Memory with and Without Key Services Enabled

Service
Router Models

 |  | 
AER2200 | 
IBR1700 | 
E300/E3000 | 
R1900 | 
R2100 | 
R920 | 
R980
 | 
No key services enabled | 
460 MB | 
460 MB | 
921 MB/1.84 GB | 
1.80 GB | 
1.80 GB | 
921 MB | 
921 MB
 | 
All key services enabled | 
135 MB | 
135 MB | 
371 MB/1.29 GB | 
1.45 GB | 
1.45 GB | 
371 MB | 
371 MB
 | 
Wi-Fi-enabled only | 
260 MB | 
260 MB | 
621 MB/1.54 GB | 
1.66 GB | 
1.66 GB | 
621 MB | 
621 MB
 | 
IDS/IPS enabled only | 
335 MB | 
335 MB | 
671 MB/1.59 GB | 
1.58 GB | 
1.58 GB | 
671 MB | 
671 MBTable 2. Available Flash Storage per Router

Router Models

 | 
AER2200 | 
IBR1700 | 
E300 | 
E3000 | 
R1900 | 
R2100 | 
R920 | 
R980
 | 
6 GB | 
6 GB | 
6 GB | 
14 GB | 
6 GB | 
8 GB | 
8 GB | 
8 GB

---

## Adjusting Memory Resources

The following describes how to disable key services on an endpoint if they are not going to be used in a deployment.

---

## Disabling Wi-Fi

Wi-Fi service may be disabled by disabling all radios and rebooting the endpoint. Use the following syntax on the router command-line interface (CLI) to disable Wi-Fi service only:
put/config/wlan/radio/0/enabled false  
put/config/wlan/radio/1/enabled false
For IBR1700 only:
put/config/wlan/radio/2/enabled false
Reboot the router when done.

---

## Disabling IDS/IPS

To disable intrusion detection systems/intrusion prevention systems (IDS/IPS), ensure that Analytics for the device is disabled in Ericsson NetCloud Manager first. Then, access the router command-line interface (CLI) and enter the following syntax:
put/config/security/ips/mode "off"
Reboot the router when done.

---

