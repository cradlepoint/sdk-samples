Application Name
================
serial_vibration_test


Application Version
===================
1.0


NCOS Devices Supported
======================
All


External Requirements
=====================
A zone forwarding rule must be added to the firewall to open up router port 5556; during 
test, router should not be connected to WAN, so allow all can be used to run test


Application Purpose
===================
This is a test developed for the Cradlepoint Serial Device (CSD) to be used during vibration
testing of the CSD.  The application is a simple serial echo server that opens a port on
the router.  Data is sent to the application and is echoed back to the client over the serial
port.  A LAN device is connected and communicates with the router via port 5556.  When the
vibration test is running, the LAN client will be notified if the serial cable is disconnected
or connected.

Expected Output
===============
LAN client should see:
Found that the uart port is <connected/disconnected>

The device that is sending serial data will echo all sent data
