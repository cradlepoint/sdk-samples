Application Name
================
ibr1700_obdII


Application Version
===================
1.0


NCOS Devices Supported
======================
IBR1700


External Requirements
=====================
- OBD-II Adapter Kit Part #: 170758-000
- Connect the IBR1700 to the OBD port on a car
  or use an OBD-II simulator
- Enable OBD-II and PIDs in the IBR1700
    System > Administration > OBD-II


Application Purpose
===================
Demonstrates how to use MQTT to subscribe to the OBD-II PIDs. Callback
functions will be invoked based on the configured PID update interval.


Expected Output
===============
Logs will be generated based on the PID update interval and will
show the PID name along with the associated data. Below are log
examples for the ENGINE_SPEED and VEHICLE_SPEED PIDs.

02:04:52 PM INFO ibr1700_obdII Published msg received. topic: OBDII/PIDS/ENGINE_SPEED, msg: b'8464'
02:04:53 PM INFO ibr1700_obdII Published msg received. topic: OBDII/PIDS/VEHICLE_SPEED, msg: b'80.78'