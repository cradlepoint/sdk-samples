#!/bin/bash
#Every app should have a built app (tar.gz) in built_apps/.
shopt -s extglob
for folder in ./!(built_apps|tools|app_template_csclient)/
do
	if [ ! -f built_apps/${folder:2:-1}.tar.gz ]
	then
		echo "The app built app (.tar.gz) for "$folder" is missing from /built_apps."
       		exit 1
	fi
done
