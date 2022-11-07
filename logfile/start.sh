#!/bin/bash
cppython logfile.py &
cd logs
cppython -m http.server 8000
