# directory: ./gps/gps_localhost
## Router App/SDK sample applications

Received GPS, assuming the router's GPS function sends new data (sentences)
to a localhost port

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: gps_localhost.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [gps]:

* host_port=9999, define the listening port, which on Cradlepoint Router
SDK must be greater than 1024 due to permissions.
