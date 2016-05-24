# directory: ./serial_port/list_ports
## Router App/SDK sample applications

This sample code runs through one check, then exits.
Assuming you have 'restart' true in your settings.ini file, then
the code restarts forever.

Based on the model of router you have, it checks to see if the ports below
exist, can be opened, and the name of the port written to it.

Real Physical ports:

* /dev/ttyS1 (only on models such as IBR1100)
* /dev/ttyS2 (normally will fail/not exist)

USB serial ports:

* /dev/ttyUSB0
* /dev/ttyUSB1
* /dev/ttyUSB2
* /dev/ttyUSB3
* /dev/ttyUSB4

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: list_ports.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [list_ports]:

* probe_physical = True, set False to NOT probe real physical serial ports.
On models without physical ports, this setting is ignored.

* probe_usb = True, set False to NOT probe for USB serial ports.

* write_name = True, set False to NOT send out the port name, which is 
sent to help you identify between multiple ports.

## Testing USB-serial devices

Most USB-serial devices with an FTDI-chipset can be used. Some specific
products known to work are shown here:

* <https://cradlepoint.com/sites/default/files/usb_to_serial_console_12.11.14_2.pdf>
* <http://www.usbgear.com/USBG-RS232-F12.html>
* <http://www.dalco.com/p-3062-usb-to-4-port-rs232-serial-adapter-db9.aspx> 
