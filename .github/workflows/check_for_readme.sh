#!/bin/bash
#Every app should have a readme.
shopt -s extglob
for folder in ./!(built_apps|tools)/
do
	if ! find $folder -iname 'readme.txt' -o -iname 'readme.md' | grep -q .;
	then
       		echo "The app "$folder" is missing a readme. Please ensure it's named "readme.txt" or "readme.md"."
       		exit 1
	fi
done
