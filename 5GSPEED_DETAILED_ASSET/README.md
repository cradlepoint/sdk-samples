Application Name
================
5GSPEED_DETAILED_ASSET

Application Purpose
===================
5GSPEED_DETAILED is an improved version of the 5GSPEED SDK. It uses Ookla Speedtest python library and designed to perform Ookla speedtest from a Cradlepoint Endpoint which will enable comprehensive and end-to-end speedtest result.
This python SDK application bring the Ookla speedtest.net functionality that is normally performed by users in the LAN behind the Cradlepoint endpoint.
This will provide uniformity of speedtest between the users and the Cradlepoint endpoint devices.

For any questions, please reach out to developer jon.campo@cradlepoint.com

Application Version
===================
0.1

NCOS Devices Supported
======================
ALL


External Requirements

Once downloaded to PC, folder name needs to be renamed to 5GSPEED_DETAILED and in .tar.gz format. 

Installation:
======================

1. Download and unzip file - 
   
https://github.com/joncampo-cradlepoint/5GSPEED_DETAILED/archive/main.zip

2. Important! Rename unzipped folder to 5GSPEED_DETAILED

3.a. For MAC and linux, open console, cd to downloads, then create .tar.gz using terminal command
   
tar -czvf 5GSPEED_DETAILED.tar.gz 5GSPEED_DETAILED/*

b. For Windows, use the python make.py build found in https://customer.cradlepoint.com/s/article/NCOS-SDK-v3

---
NCM Deployment

4. In NCM, upload 5GSPEED_DETAILED_ASSET.tar.gz to NCM via TOOLS tab
   
5. After that, go to Groups > Commands > Manage SDK applications and add the application


Usage:
======================

1. Speedtest will automatically run if Asset ID  in NCM > Devices is blank. It will populate Asset ID with speedtest result and URL.

2. Use NCM API to run.
Use NCM API PUT router request to clear the asset ID and to run the SDK speedtest. Wait for 1 min, and run NCM API Get router request to get the result.


3. You can also run 5GSPEED_DETAILED through cli console

a. Go to Devices > select Device > Remote Connect > Console

b. Enter the following command:

put status/5GSPEED 1

c. Run log command to view output:

log -f

4. You can also see the result in NCM > Devices > Asset ID column of the device



Expected Output
===============
Info level log message of ookla speedtest.net results including Timestamp, Client ISP, Ookla Speedtest.net Server, Ping, Download speed, upload speed and the URL link of the test result.


Sample output:


DL:52.54Mbps - UL:16.55Mbps - Ping:9.715ms - Server:Telstra - ISP:Vocus Communications - TimeGMT:2023-04-11T01:06:43.758382Z - URL:http://www.speedtest.net/result/14595594656.png

---
NCM > Devices > Asset ID:

DL:26.81Mbps UL:9.09Mbps - https://www.speedtest.net/result/10690043282.png



Changelog:
===============

version 1.1
1. Improved bootup blank asset id detection

2. Notification in asset id that speedtest is running

3. @speedtest.py module libary:
#11-April-2021 JWC: added to fix the speedtest cli module issue - https://github.com/sivel/speedtest-cli/pull/769
        ignore_servers = list(
            #map(int, server_config['ignoreids'].split(','))
            map(int, [server_no for server_no in server_config['ignoreids'].split(',') if server_no]) #11-April-2021 JWC: added to fix the speedtest cli module issue - https://github.com/sivel/speedtest-cli/pull/769
        )


DISCLAIMER
===============

Please note: This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use. You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.
