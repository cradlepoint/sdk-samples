Application Name
================
cpu_usage


Application Version
===================
1.10


NCOS Devices Supported
======================
ALL with usb support and FW 7.0.0 and higher.


External Requirements
=====================
1. NCOS 7.0.0 and higher.
2. The USB drive must be formatted in fat32.
3. The drive must be plugged in to write to a csv file.


Application Purpose
===================
Writes cpu and memory information to logs and a csv file. On the first pass
will create the csv file and header. After that it will append the cpu and
memory information to the csv file.


Expected Output
===============
usage_info.csv will look like the example below:

Hostname: IBR900-e44

Time: Fri Apr 12 15:58:25 2019

Memory Available: 43 MB

Memory Free: 6 MB

Memory Total: 231 MB

Load 15 Min: 0.14

Load 1 Min: 0.08

Load 5 Min: 0.11

CPU Usage: 6%
