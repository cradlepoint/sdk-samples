#!/bin/bash
#Every app should have the same version of csclient.py. This test verifies a new app or modified app does not have an out of date csclient.py.
file2="app_template_csclient/csclient.py"
for folder in ./*/;
do
        if test -f $folder/csclient.py; then
                file1=$folder/csclient.py
                if !(cmp "$file1" "$file2"); then
                        echo "The csclient.py file in "$folder" is not the correct version"
                        exit 1
                fi
        fi
done
