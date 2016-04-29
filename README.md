# Router App/SDK sample application design tools.

## Running Make.py

- Check **status** of SDK on local router, queries Router API "/status/system/sdk"

    	python make.py -m status

- **Build** the SDK tar.gzip archive, where {app module name} is your project directory, so for example is "network.tcpecho" for the directory "./network/tcpecho/". The resulting file will in the build directory, such as "**./build/tcpecho.tar.gz**".

    	python make.py -m build {app module name}

- **Install** the last built SDK archive to the local router using Secure Copy. The router must already be in SDK DEV mode via registration and licensing in ECM.

    	python make.py -m install {app module name}


 start:
    Desc: Start the application on the locally connected router.

 stop:
    Desc: Stop the application on the locally connected router.

 uninstall:
    Desc: Uninstall the application from the locally connected router.

 purge:
    Desc: Purge all applications from the locally connected router.


HOW-TO Steps for running the reference application on your router.
==================================================================

1.  Register your router with ECM.

2.  Put your router into SDK DEV mode via ECM.

3.  Export the following variables in your environment:

        DEV_CLIENT_MAC - The mac address of your router
        DEV_CLIENT_IP  - The lan ip address of your router

    Example:

        $ export DEV_CLIENT_MAC=441dbbec
        $ export DEV_CLIENT_IP=192.168.0.1

4.  Build the SDK environment.

        $ make

5.  Test connectivity with your router via the 'status' target.

        $ make status
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X GET http://192.168.0.1/api/status/system/sdk | \
                        /home/sfresk/dev/sdk/tools/bin/python -m json.tool
        {
            "data": {},
            "success": true
        }

6.  Build, test and install the reference application on your router.

        $ make install
        scp /home/sfresk/dev/sdk/RouterSDKDemo.tar.gz admin@192.168.0.1:/app_upload
        admin@192.168.0.1's password: 
        RouterSDKDemo.tar.gz                          100% 1439     1.4KB/s   00:00    
        Received disconnect from 192.168.0.1: 11: Bye Bye
        lost connection

7.  Get application execution status from your router.

        $ make status
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X GET http://192.168.0.1/api/status/system/sdk | \
                        /home/sfresk/dev/sdk/tools/bin/python -m json.tool
        {
            "data": {
                "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c": {
                    "app": {
                        "date": "2015-12-04T09:30:39.656151",
                        "name": "RouterSDKDemo",
                        "restart": true,
                        "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                        "vendor": "Cradlebox",
                        "version_major": 1,
                        "version_minor": 1
                    },
                    "base_directory": "/var/mnt/sdk/apps/7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
                    "directory": "RouterSDKDemo",
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
                        /home/sfresk/dev/sdk/tools/bin/python -m json.tool
        {
            "data": "uninstall 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
            "success": true
        }
