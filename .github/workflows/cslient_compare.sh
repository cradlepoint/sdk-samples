#!/bin/bash
file2="hello_world/csclient.py"
for folder in .;
do
        if test -f $folder/csclient.py; then
                file1=$folder/csclient.py
                if !(cmp "$file1" "$file2"); then
                        echo "The csclient.py file in "$folder" is not the correct version"
                        exit 1
                fi
        fi
done
