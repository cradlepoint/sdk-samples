# directory: ./simple/hello_world_3tasks
## Router App/SDK sample applications

The sample application creates 3 sub-tasks (so four total). 
The main application starts 3 sub-tasks, which loop, sleeping with a random
delay before printing out a logger INFO message.  

The first 2 sub-tasks will run 'forever' - or on a PC, when you do a ^C or
keyboard interrupt, the main task will abort, using an event() to stop
all three sub-tasks.

The third task will exit after each loop, and the main task will re-run it
when it notices that it is not running.

## File: __init__.py

The Python script with the class RouterApp(CradlepointAppBase) instance,
with will be run by main.py

## File: hello_world.py

The main files of the application.

## File: settings.ini

The Router App settings, including a few required by this code

