timezone_via_gnss
================
Automatically set device timezone using GNSS and TimezoneDB


Application Version
===================
0.1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
TimezoneDB account and API key

GNSS

timezone_api_key confgiured at group or device level under System -> SDK Data

*optional timezone_notify configured at group or device level under System -> SDK Data using values 'desc', 'asset_id' and / or 'alert'


Application Purpose
===================
Use GNSS data to query TimezoneDB and request a UTC offset value which will be applied to the device config under System -> Administration -> System Clock
