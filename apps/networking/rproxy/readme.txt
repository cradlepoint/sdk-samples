Application Name
================
rproxy


NCOS Devices Supported
======================
ALL


Application Purpose
===================
A reverse proxy similar to port forwarding, except traffic forwarded to a
udp/tcp target will be sourced from the router's IP. This reverse proxy can
be dynamically added to clients as they connect. 


Usage
=====
Configure config/system/sdk/appdata with entries for each port your want to proxy
and the target IP/port in the form local_addr:local_port:remote_addr:remote_port:proto
For example:

| Name | Value | Notes |
| ---- | ----- | ----- |
| rproxy.0 | 80:192.168.0.5:80 | Listens on 127.0.0.1:80 and forwards tcp to 192.168.0.5:80
| rproxy.1 | 127.0.0.1:80:192.168.0.5:80:tcp | Same as above except explicit
| rproxy.2 | 192.168.0.1:53:192.168.0.5:53:udp | Listens on 192.168.0.1 udp port 53 and forwards to 192.168.0.5:53

For dynamic clients, add a client entry to config/system/sdk/appdata with rproxy.auto in the form
local_host:local_port_ranges:remote_port:protocol. Each client that connects on the LAN network
will get a port in the range specified and traffic will be forwarded to the remote port.
For example:

| Name | Value | Notes |
| ---- | ----- | ----- |
| rproxy.auto.0 | 20020-20030:22 | Listens on a port in the range 20020-20030 and forwards to port 22 on each lan client
| rproxy.auto.1 | 127.0.0.1:20020-20030:22:tcp | Same as above except explicit
| rpxoxy.auto.2 | 80,8000-8010:80:tcp | ranges can be specified with commas
