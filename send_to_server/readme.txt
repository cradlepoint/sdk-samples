Application Name
================
send_to_server


Application Version
===================
2.1


NCOS Devices Supported
======================
ALL


External Requirements
=====================
This application uses test server http://httpbin.org/post.


Application Purpose
===================
App uses SDK Appdata to store settings for Server URL, Interval, and Payload.
Payload keys are field names and values are the NCOS path to get the data.
Data is collected and posted to server url every interval seconds.
