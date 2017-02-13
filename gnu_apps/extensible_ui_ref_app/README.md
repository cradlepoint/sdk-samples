##Router SDK Dynamic UI reference application and development tools. ##
#### NOTE: This folder contains an SDK app that uses GNU make to build and install. The SDK python tools cannot be used this application. ####

Available GNU make targets:

**default:**
    Build and test the router SDK reference app and create the archive
          file suitable for deployment to a router DEV mode or for uploading
          to ECM.

 **clean:**
    Clean all project artifacts.  Entails execution of all "-clean"
          make targets.

 **build:**
    PEP8 and PEP257 validation of all python source.

 **package:**
    Create the application archive tar.gz file.

 **status:**
    Fetch and print current SDK app status from the locally connected
          router.

 **install:**
    Secure copy the application archive to a locally connected router.
          The router must already be in SDK DEV mode via registration and
          licensing in ECM.

 **start:**
    Start the application on the locally connected router.

 **stop:**
    Stop the application on the locally connected router.

 **uninstall:**
    Uninstall the application from the locally connected router.

 **purge:**
    Purge all applications from the locally connected router.


# HOW-TO Steps for running the reference application on your router. #

*The Dynamic UI is supported in Firmware Version: 6.3.0 and above*

1.  Register your router with ECM.

2.  Put your router into SDK DEV mode via ECM.

3.  Export the following variables in your environment:

        DEV_CLIENT_MAC - The mac address of your router
        DEV_CLIENT_IP  - The lan ip address of your router

    Example:

        $ export DEV_CLIENT_MAC=44224267
        $ export DEV_CLIENT_IP=192.168.20.1

4.  Build the SDK environment.

        $ make

5.  Test connectivity with your router via the 'status' target.

        $ make status
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X GET http://192.168.0.1/api/status/system/sdk | \
                        /usr/bin/env python3 -m json.tool
        {
            "data": {},
            "success": true
        }

6.  Build, test and install the reference application on your router.

        $ make install
        scp /home/sfisher/dev/sdk/hspt.tar.gz admin@192.168.0.1:/app_upload
        admin@192.168.0.1's password: 
        hspt.tar.gz                          100% 1439     1.4KB/s   00:00    
        Received disconnect from 192.168.0.1: 11: Bye Bye
        lost connection

7.  Get application execution status from your router.

        $ make status
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X GET http://192.168.0.1/api/status/system/sdk | \
                        /usr/bin/env python3 -m json.tool
        {
            "data": {
                "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c": {
                    "app": {
                        "date": "2015-12-04T09:30:39.656151",
                        "name": "hspt",
                        "restart": true,
                        "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                        "vendor": "Cradlebox",
                        "version_major": 1,
                        "version_minor": 1
                    },
                    "base_directory": "/var/mnt/sdk/apps/7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                    "directory": hspt",
                    "filename": "dist/tmp_znv2t",
                    "state": "started",
                    "summary": "Package started successfully",
                    "type": "development",
                    "url": "file:///var/tmp/tmpg1385l",
                    "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"
                }
            },
            "success": true
        }

8.  Uninstall the reference application from your router.

        $ make uninstall
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X PUT http://192.168.0.1/api/control/system/sdk/action \
                        -d data='"uninstall 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"' | \
                        /usr/bin/env python3 -m json.tool
        {
            "data": "uninstall 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
            "success": true
        }
