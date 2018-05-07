Application Name
================
app_template


Application Version
===================
1.0


NCOS Devices Supported
======================
ALL


External Requirements
=====================
None


Application Purpose
===================
This application can be used as a template to create a new application. Instructions for
creating a new application are:

1. Copy the app_template and paste in the same directory.
2. Rename the directory to your application name. I'll use
   'new_app_name' as an example in these instructions.
3. Rename the app_template.py file to new_app_name.py.
4. Edit start.sh and stop.sh. Replace all 'app_template'
   occurrences with 'new_app_name'.
5. Edit package.ini and replace 'app_template' with 'new_app_name'. Also,
   delete the UUID so that the entry is 'uuid ='. When the application is
   built, a new UUID will be created.
6. Update the readme.txt file in the new_app_name application if required.

Your 'new_app_name' is now ready for your new code.


Expected Output
===============
Logs will be output indicating that the application has been started
or stopped.

