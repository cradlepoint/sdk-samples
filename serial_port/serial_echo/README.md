# directory: ./serial_port/serial_echo
## Router App/SDK sample applications

Wait for data to enter the serial port, then echo back out.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: serial_echo.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [serial_echo]:

* port_name=???, define the serial
