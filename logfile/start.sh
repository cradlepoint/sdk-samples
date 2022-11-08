#!/bin/bash
cppython logfile.py &
mkdir -p logs
cd logs
cppython -m http.server 8000
