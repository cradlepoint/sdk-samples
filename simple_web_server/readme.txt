Application Name
================
simple_web_server


Application Version
===================
2.1


NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
Demonstrate a very basic web server using the http
library which is included in NCOS. Port 9001 will
need to be opened in the device firewall for access.

SECURITY > Zone Firewall > Zone Forwarding > Add > \
Source = Primary LAN Zone,
Destination = Router,
Filter Policy = Default Allow All > Save

Expected Output
===============
Message "Hello World from Cradlepoint router!" will be
returned when the server receives a GET request.

