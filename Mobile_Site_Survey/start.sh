#!/bin/bash
cppython Mobile_Site_Survey.py &
mkdir -p results
cd results
cppython -m http.server 8001
