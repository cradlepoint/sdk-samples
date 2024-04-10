Application Name
================
appdata_sample


Application Version
===================
0.1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
This is an example of how to use the SDK Appdata fields to store and retrieve data in NCOS configs.
The get_appdata() function will return the value of the appdata entry with the specified name.
If the appdata is not found, it will save the default_appdata to the NCOS Configs and return it.
The app runs a loop that logs the appdata every 10 seconds so you can see user changes.