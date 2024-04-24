daily_speedtest  
===============

This SDK Application runs Ookla speedtests at configurable times (on the hour) each day.  

> Default hours are 8am, 12pm, 4pm.

You can edit the hours under System > SDK Data.  

Edit the "daily_speedtest" entry and set the value of "hours" accordingly.  

> It uses 24-hour format and just the hour number (integer).  For example 5pm = 17.  


The app puts the results in the **asset_id** field which is visible in the NCM devices grid.  

You can change the path (field) that the results go into in the same SDK Data entry.  


**Example log output:**

06:51:18 PM INFO daily_speedtest Daily speedtest scheduled for 12:00 -- Running now...  
06:51:41 PM INFO daily_speedtest 51.48Mbps Down / 10.61Mbps Up / 105ms latency
