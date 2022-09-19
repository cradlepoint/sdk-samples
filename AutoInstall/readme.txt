Application Name
================
AutoInstall


Application Version
===================
2.0

NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
“AutoInstall” is a SIM Speedtest app designed to test TCP throughput on multiple SIMs, supporting multiple modems, and prioritize them based on download speed, including the following configurable options:

•	MIN_DOWNLOAD_SPD – If no SIM download speed meets minimum, a FAILURE report is sent.  SIMs are still prioritized and slowest SIMs are disabled according to NUM_ACTIVE_SIMS.
Default Value = 0.0
•	MIN_UPLOAD_SPD – If no SIM upload speed meets minimum, a FAILURE report is sent.  SIMs are still prioritized and slowest SIMs are disabled according to NUM_ACTIVE_SIMS
Default Value = 0.0
•	SCHEDULE – Minutes between runs. 0=Only run at boot; 60=hourly; 1440=daily
Default Value = 0
•	NUM_ACTIVE_SIMS – Number of fastest SIMs to keep active. 0=all; do not disable any SIMs.
Default Value = 0
•	ONLY_RUN_ONCE – True means do not run if Boot2 has run on this device before. (common for install usage).
Default Value = False

Overwrites "description" field with results

Expected Output
===============
AutoInstall will perform a netperf speedtest on all SIMs and prioritize by TCP download speed.  It does not delete WAN profiles, but will clone profiles if multiple SIMs match a profile.

AutoInstall will send custom NCM alerts when it starts, when a SIM test times out, and when it completes.

Results will be put into the description field to sync to devices grid in NCM.

Example Results:

AutoInstall Complete! Results: 11/15/19 11:59:04 | Internal 600M (SIM2) AT&T Band 2 RSRP:-100 DL:12.82Mbps UL:8.84Mbps | Internal 600M (SIM1) Verizon Band 13 RSRP:-88 DL:10.80Mbps UL:8.81Mbps | MC400LP6 (SIM1) Verizon Band 13 RSRP:-68 DL:9.59Mbps UL:19.46Mbps

