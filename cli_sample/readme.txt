Application Name
================
cli_sample


Application Version
===================
1.0


NCOS Devices Supported
======================
All


External Requirements
=====================
None


Application Purpose
===================
Includes cppxssh module that enables SSH access to local CLI to send commands and return output.  Example sends "arpdump".

Expected Output
===============
09:22:40 AM INFO cli_sample Output:
	Type     Interface   State     Link Address      IP Address
	ethernet primarylan1 REACHABLE 14:b1:c8:01:59:09 192.168.0.93
	ethernet primarylan1 FAILED    0/0/0             192.168.0.134
	ethernet primarylan1 FAILED    0/0/0             fe80::311b:39e5:8306:d926
	ethernet primarylan1 STALE     14:b1:c8:01:59:09 fe80::1cd1:9ffa:135:3ed4
	ethernet primarylan1 STALE     14:b1:c8:01:59:09 fe80::18d5:408e:d760:2e39


