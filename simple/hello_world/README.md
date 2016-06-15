# directory: ./simple/hello_world
## Router App/SDK sample applications

The sample application shows how to create your own MAIN function.

The stock MAKE.PY will detect the existence of this 'main.py' file, 
using it instead of the stock cp_lib/make.py. 
The downside is that your application must handle setup of syslog, 
finding app settings, and so on.
(see ./simple/hello_world_app for a version using the stock main and settings design)

The actual application sends a "Hello SDK World" message to Syslog at an
'INFO' priority.

## File: __init__.py

{ an EMPTY file - used to define Python modules }

## File: main.py

The main files of the application.

## File: settings.ini

The Router App settings, required by MAKE.PY

