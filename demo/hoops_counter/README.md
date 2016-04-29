# directory: ./demo/hoops_counter
## Router App/SDK sample applications

Runs a few sub-demos.

A web server is run as a sub-task:

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
which will be run by main.py

## File: power_loss.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code:

In section [power_loss]:

* check_input_delay=5 sec, how often to query the router status tree.
Polling too fast will impact router performance - possibly even prevent
operation. So select a reasonable value: a few seconds for DEMO purposes,
likely '30 sec' or '1 min' for normal operations.
The routine 'parse_duration' is used, so supported time tags include
"x sec", "x min", "x hr" and so on.
