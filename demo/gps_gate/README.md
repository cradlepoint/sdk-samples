# directory: ./demo/gps_gate
## Router App/SDK sample applications

Received GPS data on 'localhost' port (as configured in CP Router GPS)
settings, then forward to GpsGate public servers. Only the TCP transport
is used (UDP and HTTP/XML is NOT coded/included - yet).

To use this, you will need to have arranged a GpsGate server, from which
you are given the URL to use. The code relies upon the IMEI ALREADY existing
in the server - it does not device registration, etc.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: gps_gate.py

The main files of the application.

## File: gps_gate_nmea.py

A custom state-machine for a NMEA stream designed for GpsGate, including the
unit-of-measure and delta-filters they handle. The cp_lib.gps_nema.py 
module is also used, but mainly for the NMEA sentence cleanup & creation.

## File: gps_gate_protocol.py

A custom state-machine for GpsGate 'TCP' server. It maintains a state,
and returns next-requests as expected by the protocol. Note that it does NOT
do the actual data comm. This code CREATES requests, and PARSES responses,
changing its internal state & settings as appropriate.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [gps_gate]:

* gps_gate_url=64.46.40.178, defines the URL assigned to you by the
GpsGate people. This is treated as string, so can be IP or FQDN

* gps_gate_port=30175, is the default TCP port to use. Change if needed.

* host_ip=192.168.1.6 - ONLY include to ignore Router API value!
Define which 'localhost' port the code waits on for incoming GPS sentences. 
This must match what is configured in the CP Router 

* host_port=9999  - ONLY include to ignore Router API value!
Define the listening port, which on Cradlepoint Router
SDK must be greater than 1024 due to permissions.


## TODO - 

* have the code fetch the IP/port info from the router config tree. This would
eliminate the need for the host_ip/host_port settings.
