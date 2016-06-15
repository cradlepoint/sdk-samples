# Router App/SDK sample applications - SIMPLE single function samples

## Directory hello_world

Shows how to use your own MAIN.PY, which is run as the main app of the SDK.
The code loops, sending a "Hello World" message to a Syslog server.

Because you control the full application, you must manage the Syslog output
and settings yourself.

## Directory hello_world_app

Expands the function in "hello_world" sample, using the stock 
CradlepointAppBase class, which adds the following services:
* self.logger = a Syslog logging module
* self.settings = finds/loads your settings.json (made from settings.ini)
* self.cs_client = read/write the Cradlepoint status/config trees

## Directory hello_world_1task

Expands the function in "hello_world_app" sample, adding a sub-task
to do the "Hello World" Syslog message. 
Shows how to spawn, as well as stop (kill/join) the sub-task.

## Directory hello_world_3task

Expands the function in "hello_world_1task" sample, 
adding three (3) sub-tasks, including one which exits and must be restarted

## Directory send_alert

Sends a message to router, which is treated as an ECM alert.
