# directory: ./network/simple_jsonrpc
## Router App/SDK sample applications

A most basic JSON RPC server, using the standard Python 3 SocketServer

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: jsonrpc_server.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [jsonrpc]:

* host_port=9001, define the listening port, which on Cradlepoint Router
SDK must be greater than 1024 due to permissions. 
Also, avoid 8001 or 8080, as router may be using already. 

## File: images

* The ones named "digit_1.jpg" (etc) are 550x985

* are 190x380 (to fit in 200x400 cell?
