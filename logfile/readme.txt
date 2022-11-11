Application Name
================
logfile


Application Version
===================
v0.1


NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
SDK Application that writes log to files on flash available for download via HTTP/Remote Connect.

Never lose another log!  Remote Syslog!
No more logs rolling over, no more physical USB flash drives,
and you can recover logs after a reboot.  Via Remote Connect!

Log files will be created with filenames containing the router MAC address and timestamp.  Example:
Log - 0030443B3877.2022-11-11 09:52:25.txt

When the log file reaches the maximum file size (Default 10MB) it will start a new log file.
When the number of backup logs exceeds the backup count (default 10) it will delete the oldest log.

Use Remote Connect LAN Manager to connect to 127.0.0.1 port 8000 HTTP.
Or forward the LAN zone to the ROUTER zone for local access on http://{ROUTER IP}:8000.
