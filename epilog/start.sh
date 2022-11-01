#!/bin/bash
cppython epilog.py &
cd logs
cppython -m http.server 8000
