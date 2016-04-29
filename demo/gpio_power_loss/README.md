# directory: ./demo/gpio_power_loss
## Router App/SDK sample applications

This demo includes a thread (task) to allow it to be combined with other
demos. The demo runs on an IBR1100, reading the digital input on the 2x2
power connector. sample application creates 3 sub-tasks (so four total). 
The main application starts 3 sub-tasks, which loop, sleeping with a random
delay before printing out a logger INFO message.  

The first 2 sub-tasks will run 'forever' - or on a PC, when you do a ^C or
keyboard interrupt, the main task will abort, using an event() to stop
all three sub-tasks.

The third task will exit after each loop, and the main task will re-run it
when it notices that it is not running.

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
* loss_delay=2 sec, after seeing the first POWER LOSS value, we delay and
recheck, confirming it is still lost before sending the alert. 
The routine 'parse_duration' is used, so tags like 'sec' and 'min' are 
supported.
* restore_delay=2 sec, after seeing the first POWER RESTORE value, we delay 
and recheck, confirming it is still restored before sending the alert. 
The routine 'parse_duration' is used, so tags like 'sec' and 'min' are 
supported.
* match_on_power_loss=False, the 2x2 power connector input is read and 
compared to this value. If it matches, then the condition is deemed
to be "Power Loss == True". 
False and 0 are interchangeable, as are True and 1. 
* led_on_power_loss=False, defines if and how the 2x2 power connector 
output is handled. Set to 'null' or 'None' to disable out.
If True or False, that value to set when "Power Loss == True"
* site_name=Quick Serve Restaurant #278A, any user defined name, which is
included in the alert.

Also in the section [power_loss], see cp_lib.cp_email.py: 

* username, password, smtp_url, smtp_port, email_to

## Alert Forms

The general form will be {condition}{setting: site_name}

### Example when Power is Lost:

* Bad News! AC Power lost at site: Quick Serve Restaurant #278A
 at time: 2016-04-20 19:36:26 -0500

### Example when Power is Restored:

* Good News! AC Power restored at site: Quick Serve Restaurant #278A
 at time: 2016-04-20 19:54:47 -0500

