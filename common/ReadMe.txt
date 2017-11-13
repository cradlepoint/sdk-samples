Common Directory Contents
=========================
cs.py
-----
A wrapper for the TCP interface to the router config store. Includes
functions for log generation, get, put, delete, and append items to config store,
and a function for sending alerts to the ECM. Copy this file to your application 
directory and import into your application.

app_logging.py
--------------
Contains a singleton object that provides the ability to generated
different level logging to the NCOS device syslogs. See the comments in the file
itself for more details.

settings.py
-----------
The app_logging.py file imports the settings as it contains the APP_NAME. It is
a good place to store anything that will be common to files in you application.
