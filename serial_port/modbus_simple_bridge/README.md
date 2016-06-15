# directory: ./serial_port/modbus_simple_bridge
## Router App/SDK sample applications

Act as a very simple single-client Modbus/TCP to RTU bridge. It uses
'select' to allow a client to connect.

TODO - warning:
- this 'simple' code assumes the full Modbus/TCP request arrives as a single
  TCP segment, which is generally true - but not always!
- Note that you'll need to manually enable the server IP/port in the router's
  Zone forwarding config
- It does use the idle_

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: modbus_tcp_bridge.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [modbus_serial]:

These are the settings for the serial/to-slave side of the bridge.

* port_name=???, define the serial port to use. Commonly this will be 
/dev/ttyS1 or /dev/ttyUSB0

* baud_rate=9600, allows you to define a different baud rate. This sample
assumes the other settings are fixed at: bytesize=8, parity='N', stopbits=1, 
and all flow control (XonXOff and HW) is off/disabled. 
Edit the code if you need to change this.

* protocol=mbrtu, allows changing the protocol used on the slave/serial side. 
Supported protocols are in (mbrtu, mbasc), default = mbrtu

In section [modbus_ip]:

These are the settings for the network/from-master/client side of the bridge.

* host_ip= - interface to bind on. Normally do NOT set, and then will be 
active on all interfaces (so == ''). Else can be customized to any valid
interface IP to limit it. 

* host_port=8502 - the TCP port to use. This CANNOT be the normal Modbus/TCP
well-defined (and IANA assigned) port of 502, as the SDK does not have 
permission to open TCP ports below 1024 

idle_timeout=30 sec

* protocol=mbtcp, allows changing the protocol used on the master/network 
side. Supported protocols are in (mbrtu, mbasc, mbtcp), default = mbtcp. 
Note that 'mbrtu' means raw serial Modbus/RTU packets encapsulated in 
a normal TCP socket.
