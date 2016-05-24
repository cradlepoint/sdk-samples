# directory: ./serial_port/serial_echo
## Router App/SDK sample applications

Wait for data to enter the serial port, then echo back out. 
Data will be processed byte by byte, although you could edit the 
sample code to wait for an end-of-line character. 

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: serial_echo.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [serial_echo]:

* port_name=???, define the serial port to use. Commonly this will be 
/dev/ttyS1 or /dev/ttyUSB0

* baud_rate=9600, allows you to define a different baud rate. This sample
assumes the other settings are fixed at: bytesize=8, parity='N', stopbits=1, 
and all flow control (XonXOff and HW) is off/disabled. 
Edit the code if you need to change this.
