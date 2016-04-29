# directory: ./demo/redlion_cub5
## Router App/SDK sample applications

This demo includes ... 

## hardware Device:
The RedLion CUB5 is a small counter/meter, for panel cut outs 1.30 x 2.68 in.
This demo is specifically using it as a counter - to demo counting something
like people entering a door, motion detection, or Mike tossing a basketball
through a hoop.

* http://files.redlion.net/filedepot_download/213/3984
* http://www.redlion.net/products/industrial-automation/hmis-and-panel-meters/panel-meters/cub5-panel-meters 

Pin-outs: 485 with 4-wire JR11:
* Black = D+
* Red = D-
* Green = SG
* Yellow = No Connection

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
with will be run by main.py
