# directory: ./simple/hello_world_app
## Router App/SDK sample applications

The sample application shows how to use the CradlepointAppBase to make
an ultra-simple application. 
The CradlepointAppBase adds the following services:
* self.logger = a Syslog logging module
* self.settings = finds/loads your settings.json (made from settings.ini)
* self.cs_client = read/write the Cradlepoint status/config trees

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
with will be run by the stock main.py

## File: hello_world.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code

