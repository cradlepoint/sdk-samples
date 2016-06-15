# directory: ./simple/hello_world_1task
## Router App/SDK sample applications

The sample application creates 1 sub-tasks (so two total). 
The main application starts 1 sub-task, which loops, sleeping a fixed time, then printing out a Syslog INFO message. 
It shows the proper way to deal with sub-tasks, including standard clean-up when exiting.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
with will be run by the stock main.py

## File: hello_world.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code

