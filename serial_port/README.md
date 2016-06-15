# Router App/SDK sample applications - SERIAL PORT samples

## Directory list_ports

Shows how to use your own MAIN.PY, which is run as the main app of the SDK.
The code loops, sending a "Hello World" message to a Syslog server.

Because you control the full application, you must manage the Syslog output
and settings yourself.

## Directory modbus_poll

Expands the function in "hello_world" sample, using the stock 
CradlepointAppBase class, which adds the following services:
* self.logger = a Syslog logging module
* self.settings = finds/loads your settings.json (made from settings.ini)
* self.cs_client = read/write the Cradlepoint status/config trees

## Directory modbus_simple_bridge

Expands the function in "hello_world_app" sample, adding a sub-task
to do the "Hello World" Syslog message. 
Shows how to spawn, as well as stop (kill/join) the sub-task.

## Directory serial_echo

Shows basic serial port read/write.
Opens a serial port, as defined in settings.ini 
(can be built-in port on IBR11X0 or USB-Serial)
then echos any bytes seen. 

