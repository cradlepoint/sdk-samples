#!/bin/bash
cppython Mobile_Site_Survey.py &
mkdir -p results
./miniserve -p 8001 results/
