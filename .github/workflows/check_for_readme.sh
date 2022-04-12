#!/bin/bash
#Every app should have a readme.
shopt -s extglob
for folder in ./!(built_apps|tools)/
do
	if [ ! -f $folder/readme.txt ]
	then
       		echo "The app "$folder" is missing a readme.txt. Please ensure it's named "readme.txt"."
       		exit 1
	fi
done
