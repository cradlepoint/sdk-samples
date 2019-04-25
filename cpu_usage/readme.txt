Application Name
================
cpu_usage


Application Version
===================
1.0


NCOS Devices Supported
======================
ALL with usb support and FW 7.0.0 and higher.


External Requirements
=====================
The USB drive must be formatted in fat32.


Application Purpose
===================
Gets cpu and memory usage information from the router every 30 seconds and writes a csv file to a usb stick formatted in fat32.


Expected Output
===============
Your USB drive should get populated with usage_info.csv that will look like the example below:

Hostname	  Time	                    Memory Available	Memory Free	Memory Total	Load 15 Min	Load 1 Min	Load 5 Min	CPU Usage
IBR900-e44	Fri Apr 12 15:58:25 2019	43 MB	            6 MB	      231 MB	      0.14	      0.08	      0.11	      6%
