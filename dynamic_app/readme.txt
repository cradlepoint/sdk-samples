# Dynamic App
This SDK app drives the downloading of an SDK from a specified URL into the app_holder app. This overcomes the size limitation of NCM, as well as makes it easier to build and test SDK apps without having the router in DEV mode.

# Usage
1) Install both this application as well as the app_holder app onto the router through NCM.
2) Develop the target app as desired and package it through the normal process so you have a tar.gz file of the app (as if to upload to NCM). 
3) Host the tar.gz file via http (for example using miniserve https://github.com/svenstaro/miniserve).
4) Configure the dynamic app using System -> SDK Data in group/indi router configuration using these name value pairs:

| Name            | Value                                                     |
| --------------- | --------------------------------------------------------- |
| dynamic.url     | The url the app is hosted at e.g. http://192.168.0.5:8080 |
| dynamic.name    | The name of the app                                       |
| dynamic.version | Optional, but allows for easy triggering of app updates   |

5) Check the logs to make sure your app is running correctly.

# Notes
This app automatically downloads from the dynamic.url + dynamic.name + .tar.gz. The name of the .tar.gz file must match the name of the app folder it extracts to. This is typically the default when building apps using make.py.
