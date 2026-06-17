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

# Build all apps (searches recursively under apps/)
run_cmd "python3 make.py build all"

# Copy tar.gz files handling spaces in filenames
echo "Copying tar.gz files to built_apps/"
find . -maxdepth 1 -name '*.tar.gz' -exec cp {} built_apps/ \;

# Clean all build artifacts
run_cmd "python3 make.py clean all"

# Generate app store catalog
echo "Generating app store catalog..."
python3 docs/generate_catalog.py
