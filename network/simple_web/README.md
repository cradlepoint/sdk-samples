# directory: ./network/simple_web
## Router App/SDK sample applications

A most basic web server, using the standard Python 3 "http.server" module.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: web_server.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [web_server]:

* host_port=9001, define the listening port, which on Cradlepoint Router
SDK must be greater than 1024 due to permissions. 
Also, avoid 8001 or 8080, as router may be using already. 

* host_ip=192.168.0.1, limits the interface used. 
Normally, you can omit and server will work on ALL interfaces - 
host_ip will == "". 
However, you might want to limit to local LAN, which means the interface
your router offers DHCP to local clients.

* message=Hello from Cradlepoint Router!, put any UTF8 message here
