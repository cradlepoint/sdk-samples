#!/bin/bash
declare -a commands=("python3 make.py build" "python3 make.py build all" "cp *.tar.gz built_apps" "python3 make.py clean" "python3 make.py clean all")
for cmds in "${commands[@]}";
do
	echo $cmds
	result=$($cmds 2>&1 > output.txt)
	if [ -n "$result" ]
	then
		echo "Error with app: $result"
		cat output.txt
		exit 1
	else
		cat output.txt
		
	fi
done
