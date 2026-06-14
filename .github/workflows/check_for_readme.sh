#!/bin/bash
# Every app should have a readme.
# Searches recursively under apps/ and archive/ for dirs with package.ini
find_errors=0

while IFS= read -r -d '' ini_file; do
    folder=$(dirname "$ini_file")
    if ! find "$folder" -maxdepth 1 -iname 'readme.txt' -o -iname 'readme.md' | grep -q .; then
        echo "The app \"$folder\" is missing a readme. Please ensure it's named \"readme.txt\" or \"readme.md\"."
        find_errors=1
    fi
done < <(find ./apps -path ./apps/templates -prune -o -name 'package.ini' -print0 2>/dev/null)

if [ $find_errors -eq 1 ]; then
    exit 1
fi
echo "All apps have readmes."
