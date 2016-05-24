# directory: ./serial_port/modbus_poll
## Router App/SDK sample applications

Poll a single range of Modbus registers from an attached serial 
Modbus/RTU PLC or slave device. The poll is repeated, in a loop.
The only output you'll see if via Syslog.

If you need such a device, do an internet search for "modbus simulator', as
there are many available for free or low (shareware) cost. These run on a
computer, serving up data by direct or USB serial port.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: modbus_poll.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [modbus]:

* port_name=???, define the serial port to use. Commonly this will be 
/dev/ttyS1 or /dev/ttyUSB0

* baud_rate=9600, allows you to define a different baud rate. This sample
assumes the other settings are fixed at: bytesize=8, parity='N', stopbits=1, 
and all flow control (XonXOff and HW) is off/disabled. 
Edit the code if you need to change this.

* register_start=0, the raw Modbus offset, so '0' and NOT 40001. 
Permitted range is 0 to 65535

* register_count=4, the number of Holding Register to read. 
The request function is fixed to 3, so read multiple holding registers.
The permitted count is 1 to 125 registers (16-bit words)

* slave_address=1, the Modbus slave address, which must be in the range
from 1 to 255. Since Modbus/RTU is a multi-drop line, the slave
address is used to select 1 of many slaves. 
For example, if a device is assigned the address 7, it will ignore all
requests with slave addresses other than 7.

* poll_delay=15 sec, how often to repoll the device. A lone number (like 60)
 is interpreted as seconds. However, it uses the CP library module 
 "parse_duration", so time tags such as 'sec', 'min, 'hr' can be used.
