# directory: ./demo/gps_replay
## Router App/SDK sample applications

These samples are best run on a PC/notebook, for while one CAN save a file
in the router flash, there is NO way to access that file.

## File: __init__.py

Is empty!

## File: gps_save_replay.py

Run this directly! It probes your router, obtains the configured GPS-to-IP
server settings, and waits on the configured IP/port. It saves the data like
this:

[
 {"offset":1, "data":$GPGGA,094013.0,4334.784909,N,11612.766448,W,1 (...) *60},
 {"offset":3, "data":$GPGGA,094023.0,4334.784913,N,11612.766463,W,1 (...) *61},
 {"offset":13, "data":$GPGGA,094034.0,4334.784922,N,11612.766471,W, (...) *67},


## File: settings.ini

The Router App settings, including a few required by this code:

In section [gps]:

* host_port=9999, define the listening port, which on Cradlepoint Router
SDK must be greater than 1024 due to permissions.
