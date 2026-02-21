#!/bin/bash
mkdir -p built_apps
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

# Format the README file
regex_pattern="## Sample Application Descriptions"
file_path="README.md"

cat << EOF > built_apps/README.md
These files are sample SDK Applications that are ready to use for testing and do not require modification or "building" of the app from source files.  

## How to use these files: ##
Download the .tar.gz file, then upload to your NetCloud Manager account and assign to groups.

Additional documentation:
https://customer.cradlepoint.com/s/article/NetCloud-Manager-Tools-Tab#sdk_apps

----------
EOF

sed -n "/$regex_pattern/,\$p" "$file_path" >> built_apps/README.md