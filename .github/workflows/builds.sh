#!/bin/bash
mkdir -p built_apps

run_cmd() {
	echo "$1"
	result=$(eval "$1" 2>&1 > output.txt)
	if [ -n "$result" ]; then
		echo "Error with app: $result"
		cat output.txt
		exit 1
	else
		cat output.txt
	fi
}

run_cmd "python3 make.py build"
run_cmd "python3 make.py build all"

# Copy tar.gz files handling spaces in filenames
echo "Copying tar.gz files to built_apps/"
find . -maxdepth 1 -name '*.tar.gz' -exec cp {} built_apps/ \;

run_cmd "python3 make.py clean"
run_cmd "python3 make.py clean all"

# Release body (built_apps/README.md) is created by workflow after update_readme_links runs