# directory: ./config
## Router App/SDK sample applications

This directory holds global things shared by most Router Apps

## File: main.py

This Python script is the default "Router App" start up routine, which make.py
will copy
into your build archive - unless you have your own 'main.py' file in your
application project directory.

This main.py does a variety of start-up chores, including:

* locate your settings.json, which make.py should place in the root of your
archive.
* delay until time.time() is valid (or a max delay has pasted)
* delay until WAN connection is true (or a max delay has pasted)
* locate, import, and run your RouterApp module (start your code)
* if your code exits, then it uses an optional delay to prevent rapid
task trashing. For example, it might delay until 30 seconds past the
time your app started.

## File: settings.ini

Holds common shared settings, such as how logging is handled, the IP and user
credentials for your local router, and main.py startup behavior.

This file is required by make.py

## File: settings.json

A temporary file used by tools - do not edit, as any edits will be lost.
If it exists, it will have been created from various other settings.ini files.

## File: target.ini

An optional settings file use by the tools/target.py script, which is
designed to simplify testing on a PC with more than one router or interface.
It allows you to map a name (like IBR1100 or CBA850) to select one of N
interfaces, assign IP, and so on.
