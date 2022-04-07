#!/bin/bash
file2="../hello_world/csclient.py"
for folder in ../*/;
do
	if test -f $folder/csclient.py; then
		file1=$folder/csclient.py
		cmp "$file1" "$file2" 
	fi
done
