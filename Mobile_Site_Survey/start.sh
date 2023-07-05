#!/bin/bash
cppython Mobile_Site_Survey.py &
mkdir -p results
chmod +x miniserve
./miniserve -p 8001 results/
