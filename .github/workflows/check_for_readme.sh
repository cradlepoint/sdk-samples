#!/bin/bash
# Every app should have a readme.
# Checks each app dir under apps/ (flat structure, excludes templates/ and archive/)
find_errors=0

for ini_file in ./apps/*/package.ini; do
    [ -f "$ini_file" ] || continue
    folder=$(dirname "$ini_file")
    basename=$(basename "$folder")
    # Skip templates and archive
    if [ "$basename" = "templates" ] || [ "$basename" = "archive" ]; then
        continue
    fi
    if ! find "$folder" -maxdepth 1 -iname 'readme.txt' -o -iname 'readme.md' | grep -q .; then
        echo "The app \"$folder\" is missing a readme. Please ensure it's named \"readme.txt\" or \"readme.md\"."
        find_errors=1
    fi
done

if [ $find_errors -eq 1 ]; then
    exit 1
fi
echo "All apps have readmes."
