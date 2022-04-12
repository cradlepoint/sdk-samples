#!/bin/bash
#Every app should have an entry in the root readme.txt.
shopt -s extglob
for folder in ./!(built_apps|tools)/
do
	if ! grep -q ${folder:2:-1} README.md
	then
		echo "An entry for the app "$folder" is missing from the root readme."
       		exit 1
	fi
done
