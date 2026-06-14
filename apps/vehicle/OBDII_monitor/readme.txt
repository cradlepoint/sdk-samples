Application Name
================
OBDII_monitor

External Requirements
=====================
OBDII Streamer


Application Purpose
===================
Monitor OBD-II values, put latest values in asset_id, and alert on conditions defined in SDK AppData.

 The app will create an entry in SDK AppData for "OBDII_monitor".
 Set the polling interval in seconds from 1-50.  Higher than 50 can miss historical values.
 Define the PID names you want to monitor and any conditions for alerting (optional):

 Example for just monitoring odometer with no alert conditions:
 "ODOMETER": {"condition": "", "value": ""}
 This will put ODOMETER value in the asset_id field but not send alerts.

 For alerting, set condition and value.  Conditions:
 ">" greater than, "<" less than, "=" equal to, "!=" not equal to

 Example for monitoring speed with alerting:
 "VEHICLE_SPEED": {"condition": ">", "value": 80}

 Example for alerting if fuel system monitor not complete:
 "FUEL_SYSTEM_MONITOR": {"condition": "!=", "value": "COMPLETE"}