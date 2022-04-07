#!/bin/bash
declare -a commands=("python3 make.py build" "python3 make.py build all" "python3 make.py clean" "python3 make.py clean all")
for cmds in "${commands[@]}";
do
	echo $cmds
	result=$($cmds 2>&1 > /dev/null)
	if [ -n "$result" ]
	then
		echo "Error with app: $result"
		exit 1
	fi
done
