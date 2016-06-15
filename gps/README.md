# Router App/SDK sample applications.

## Directory gps_localhost

Assuming the Cradlepoint router is configured to forward NMEA sentences 
to a localhost port, open the port as a server and receive the streaming
GSP data. This code can be run on either a PC or Router.

## Directory probe_gps

Walk through the router API 'status' and 'config' trees, returning
a list of text strings showing if any GPS source exists, if there is
existing last-seen data, and so on.
