# **Cradlepoint Router Application Development** #

----------

## Quick Links ##

#### [Overview](#overview) ####
#### [Developer Community](#community) ####
#### [Cradlepoint Knowledge Base](#knowledge) ####
#### [Router Python Environment](#environment) ####
#### [Computer Setup Instructions](#setup) ####
#### [Router Development Mode](#devmode) ####
#### [Application Directory Structure](#structure) ####
#### [Application Package Anatomy](#anatomy) ####
#### [SDK Instructions Overview](#sdk) ####
#### [Router Syslog for Debugging](#syslog) ####
#### [ECM Application Deployment](#ecm) ####
#### [Sample Application Walk Through](#sample) ####


<a name="overview"></a>
## Overview ##
Cradlepoint’s Router Application Framework provides the ability to add intelligence in the router. Applications written in Python can be securely downloaded to the router via [Enterprise Cloud Manager](https://cradlepoint.com/ecm) (ECM). This allows for extended router features, FOG Computing, and IoT management.

At a high level, the Cradlepoint Router Apps/SDK is a mechanism to package a collection of files – including executable files – in an archive, which can be transferred securely via ECM, hidden within a Cradlepoint router, and executed as an extension to normal firmware.

### What is Supported? ###
For the scope of this document, Router Apps are limited to the non-privileged Python scripts. Supported functionality:

- Standard TCP/UDP/SSL socket servers function on ports higher than 1024.
- Standard TCP/UDP/SSL socket client to other devices (or the router as 127.0.0.1/localhost).
- Access to serial ports via PySerial module, including native and USB-serial ports.
- Ability to PING external devices.
- UI Extensibility (i.e. Hot Spot splash page or other UI WEB pages)
- Access to the Router API (aka: status and control tree data).
- USB Memory device file access (USB Memory device support varies based on router).

### What is not Supported? ###
- Any form of natively compiled or kernel linked code.
- Any function requiring privileged (or root) permissions.
- Access to shared resources (for example: no ability to issue custom AT commands to cell modems).
- Modifications of routing or security behavior.

### Supported Routers ###
The supported set of routers is:

- AER – 1600/1650, 2100, 3100/3150
- COR – IBR1100/1150, IBR900/IBR950, IBR600B/IBR650B, IBR350
- ARC - CBA850

New routers products will support Python applications unless they are a special low-function, low-cost model.

### Application Development ###
During development, an application can be directly installed into a 'DEV Mode' router. This makes it easier to debug and work through the development process. Once the application has been fully debugged and is ready for deployment, it can be installed via ECM at the group level.

### SDK Toolset ###
Cradlepoint has a simplified SDK, written in python, which builds and creates an app package. The SDK, along with sample applications is located [here](https://github.com/cradlepoint/sdk-samples/releases). 

For app development, the SDK is be used to install, start, stop, uninstall, and check status of the application in a locally connected development router. The application package is the same for local debugging or for uploading to the ECM for production deployment. Application development can be done on Linux, OS X, and Windows operating systems with the same SDK.


<a name="community"></a>	
## Developer Community ##
Cradlepoint has a [Developer Community Portal](https://dev.cradlepoint.com) to leverage knowledge, share, and collaborate with other developers. This forum is also actively monitored by Cradlepoint to answer questions.


<a name="knowledge"></a>
## Cradlepoint Knowledge Base ##
The existing [Cradlepoint Knowledge Base](http://knowledgebase.cradlepoint.com) also has many articles related to router applications and the SDK.


<a name="environment"></a>	
## Router Python Environment ##
Application are written in python. However, the router only contains a subset of a typical python installation on a computer. The list of python modules in the router are listed here: [Router FW 6.1.0 Modules.](https://dev.cradlepoint.com/s/article/ka1380000000EXWAA2/sdk-fw-6-1-0-modules) New python files can be added to you application but they must also adhere to this list.

<a name="setup"></a>
## Computer Setup Instructions ##
The SDK and sample apps can be downloaded from [https://github.com/cradlepoint/sdk-samples](https://github.com/cradlepoint/sdk-samples). Below are the setup instruction for:

- [Linux](#Linux)
- [OS X](#Mac)
- [Windows](#Windows)

<a name="Linux"></a>
### Linux ###
1. Install python 3.5.1 from [python.org](http://www.python.org).

2. Add Linux development libraries.

		sudo apt-get install libffi-dev
		sudo apt-get install libssl-dev
		sudo apt-get install sshpass
		
3. Install python libraries. 

		sudo apt-get install python3-pip
		pip3 install requests
		pip3 install pyopenssl
		pip3 install requests
		pip3 install cryptography

1. Useful tools

    PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=linux](https://www.jetbrains.com/pycharm/download/#section=linux).
 

<a name="Mac"></a>
### Mac OS X ###
1. Install python 3.5.1 from [python.org](http://www.python.org).

3. Install HomeBrew for package updates. 

		/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

6. Install openssl.

		brew install openssl

1. Install python libraries. 

		pip3 install requests
		pip3 install pyopenssl
		pip3 install requests
		pip3 install cryptography

1. Useful tools

    PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=macOS](https://www.jetbrains.com/pycharm/download/#section=macOS).
    

<a name="Windows"></a>
### Windows ###
1. Install python 3.5.1 from [https://www.python.org/downloads/release/python-351/](https://www.python.org/downloads/release/python-351/).
3. The SDK requires some OpenSSL tools to generate digital signatures.
	- For 64bit OS: [https://slproweb.com/download/Win64OpenSSL\\_Light-1\\_1_0f.exe](https://slproweb.com/download/Win64OpenSSL_Light-1_1_0f.exe)
	- For 32bit OS: [https://slproweb.com/download/Win32OpenSSL\\_Light-1\\_1_0f.exe](https://slproweb.com/download/Win32OpenSSL_Light-1_1_0f.exe)
4. Open a terminal window and use the following commands to install python libraries.

		python -m pip install -U pip
		python -m pip install -U pyserial
		python -m pip install -U requests
		python -m pip install -U pyopenssl
1. Useful tools
    1. Putty: [http://www.putty.org/](http://www.putty.org/)
    2. PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=windows](https://www.jetbrains.com/pycharm/download/#section=windows).
    3. 7-zip: [http://www.7-zip.org/](http://www.7-zip.org/)
    4. MarkdownPad: [http://markdownpad.com/](http://markdownpad.com/)
    

<a name="structure"></a>
## SDK/Apps Directory Structure ##
Below is the directory structure for for the SDK and sample applications. The **BOLD** items are modified or created by the developer. The other files are used by the SDK or are referenced by the other files.

- Router_Apps (directory)
	- app_name (directory)
		- **package.ini** - App initialization items.
		- **app_name.py** - The app python code. There can be multiple py files based on the app design.
		- cs.py - This is included with every sample app and should be in your app. It contains a CSClient class which is a wrapper for the TCP interface to the router config store (i.e. the router trees). 
		- **install.sh** - Runs on app installation. (update with app name) 
		- **start.sh** - Script that starts an app (i.e. cppython app_name.py start).
		- **stop.sh** - Script that stops an app (i.e. cppython app_name.py stop).
	- config (directory)
		- **settings.mk** - Build system config settings (i.e. Router MAC, IP, Username, Password, etc.).
	- common
		- cs.py - This is included with every sample app and can be copied into your app directory. It contains a CSClient class which is a wrapper for the TCP. 
	- tools (directory)
		- bin (directory)
			- package_application.py - Used by SDK.
			- validate_application.py - Used by SDK.
			- pscp.exe - An executable use on Windows by the SDK.
	- **sdk_setting.ini** - Used by the SDK and contains the settings for building the app and connecting to the local router.
	- Router\_Application\_Development\_Guide.md 
	- Router\_APIs\_for\_Applications.md 
	- Makefile\_README.md 

Based on the sdk\_setting.ini file, the SDK will build all files located in the *app\_name* directory into a *tar.gz* package that can then been installed into the router. This installation is either directly into the router (if in DEV mode) or via ECM for grouped routers.

<a name="anatomy"></a>
## Application Package Anatomy ##
A router application package, which is a *tar.gz* archive, consists of a set of files that includes the python executable, start/stop scripts, initialization files, along with manifest and signature files. This package of files is built by the SDK base on the sdk_settings.ini. Some of these files, like the manifest and signature files, are created by the Make tool. Others are created by the application developer. Below are the example contents for a tar.gz archive created for a router application.
 
- app_name (directory)
	- METADATA (directory)
		- MANIFEST.json - Contains a file list along with hash signatures and other app the package initialization data.
		- SIGNATURE.DS - A signature file for the app package.
	- app_name.py - The application python executable file.
	- cs.py - Another python file used by the app. There could be multiple python files depending on the application design.
	- package.ini - The package initialization data.
	- install.sh - The script run during installation.
	- start.sh - The script run when the app is started.
	- stop.sh - The script run when the app is stopped

### package.ini ###
This initialization file contains information and about the application and items that affect installation and execution. This information will stored in /status/system/sdk within the router config store for installed apps.

For example:

    [hello_world]
    uuid=7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c
    vendor=Cradlepoint
    notes=Hello World Demo Application
    firmware_major=6
    firmware_minor=1
    restart=false
    reboot=true
    version_major=1
    version_minor=6
    auto_start=true

- **[hello_world]** 

    This must contain the name of the application. In this example, hello_world is the application name.
    
- **uuid**  
      
    Every app must contain a universally unique identifier (UUID).

- **vendor**

    This is the vendor name for the app.

- **notes**

    Add notes to describe the app or anything else.

- **firmware\_major and firmware\_minor **

    This is the required router firmware version for the app. ***Not  implemented at this time.***

- **restart**
    If set to 'true', then the application will be restarted if it dies or is not running. If false, the router will not attempt to restart the application.

- **reboot**
    If set to 'true', the router will restart the application following a router reboot. Otherwise, it will not be restarted.

- **version\_major and version\_minor**

    This contains the app version. This must be incremented for any new production app used installed via ECM. It will not re-install the same version that already exist in the router.

- **auto_start**

    If set to 'true', the app will automatically start after installation. 


### install.sh ###
This script is executed when the application is installed in the router. Typically it will just add logs for the installation.

For example:

    #!/bin/bash
    echo "INSTALLATION hello_world on:" >> install.log
    date >> install.log

### start.sh ###
This script is executed when the application is started in the router. It contains the command to start the python script and pass any arguments. 

For example:

    #!/bin/bash
    cppython hello_world.py start

### stop.sh ###
This script is executed when the application is stopped in the router. It contains the command to stop the python script. 

For example:

    #!/bin/bash
    cppython hello_world.py stop


<a name="sdk"></a>
## SDK Instructions Overview ##
The SDK includes a python make.py file which is compatible for all supported platforms. There is also a GNU Makefile which can only be used with Linux or OS X. Both perform the same actions which are noted below. However, there are minor setup differences between the two. Developers can choose the one they prefer. For usage instructions, see:

- [Python SDK Usage](#python_usage)
- [GNU Make SDK Usage](gnu_make_usage)

### SDK actions are: ###
**default (i.e. no action given):**
    Build and test the router reference app and create the archive file suitable for deployment to a router DEV mode or for uploading to ECM.

 **clean:**
    Clean all project artifacts. Entails execution of all "-clean" make targets.

 **package:**
    Create the app archive tar.gz file.

 **status:**
    Fetch and print current app status from the locally connected router.

 **install:**
    Secure copy the app archive to a locally connected router. The router must already be in SDK DEV mode via registration and licensing in ECM.

 **start:**
    Start the app on the locally connected router.

 **stop:**
    Stop the app on the locally connected router.

 **uninstall:**
    Uninstall the app from the locally connected router.

 **purge:**
    Purge all apps from the locally connected router.


<a name="python_usage"></a>
### Python SDK Usage ###
All SDK functions are contained in the make.py python file. While this executable is the same regardless of the workstation platform, the python command is not. Use the following python command based on your platform:

- Linux or OS X:

		python3

- Windows:

		python

The command structure is: 

	python(3) make.py <action>

The make.py usage is as follows:

1. Update the sdk_setting.ini file based on your needs.

    Example:

		[sdk]
		app_name=ping
		dev_client_ip=192.168.0.1
		dev_client_username=admin
		dev_client_password=44224267

1. Update the UUID in the package.ini file located in the app directory. 

	Example:

		[ping]
		uuid=dd91c8ea-cd95-4d9d-b08b-cf62de19684f

6.  Build the application package.

        python(3) make.py

5.  Test connectivity with your router via the status target.

        python(3) make.py status
        {
            "data": {},
            "success": true
        }

6.  Install the application on your router.

        python(3) make.py install
        admin@192.168.0.1's password: 
        hspt.tar.gz                          100% 1439     1.4KB/s   00:00    
        Received disconnect from 192.168.0.1: 11: Bye Bye
        lost connection

7.  Get the application execution status from your router.

        python(3) make.py status
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

8.  Uninstall the application from your router.

        python(3) make.py uninstall
        {
            "data": "uninstall 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
            "success": true
        }


<a name="gnu_make_usage"></a>
### GNU Make SDK Usage ###
A GNU Makefile, for Linux or OS X, is also included with the SDK which can perform the same functions as the make.py file. The make targets are identical to the make.py actions. However, environment variable will need to be set in lieu of the sdk_setting.ini file. 

The GNU make usage is as follows:

1. Export the following variables in your environment.

		APP_NAME - The name of your application.
		APP_UUID - Each application must have its own UUID.
        DEV_CLIENT_MAC - The mac address of your router.
        DEV_CLIENT_IP  - The lan ip address of your router.

    Example:

		$ export APP_NAME=hello_world
		$ export APP_UUID=616acd0c-0475-479e-a33b-f7054843c973
        $ export DEV_CLIENT_MAC=44224267
        $ export DEV_CLIENT_IP=192.168.20.1
        
6.  Build the application package.

        $ make

5.  Test connectivity with your router via the status target.

        $ make status
        curl -s --digest --insecure -u admin:441dbbec \
                        -H "Accept: application/json" \
                        -X GET http://192.168.0.1/api/status/system/sdk | \
                        /usr/bin/env python3 -m json.tool
        {
            "data": {},
            "success": true
        }

6.  Build, test, and install the application on your router.

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

8.  Uninstall the application from your router.

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


<a name="syslog"></a>
## Router Syslog for Debugging ##
Application debugging is accomplished with the use of debug syslogs. However, the default logging level in the router is set to **info** so this will need to be changed to **debug**. It is also possible to send the router logs to a syslog server running on another device. For more information, see the Knowledge Base article ['Understanding Router Log Files'](http://knowledgebase.cradlepoint.com/articles/Support/fw6-Understanding-Router-Log-Files-and-Features?retURL=%2Fapex%2FknowledgeSearch%3Fc%3DAll_Products%26p%3D2%26k%3Dsyslog%26t%3D%26l%3D%26lang%3Den_US&popup=false&c=All_Products&lang=en_US).

You can also view logs via CLI commands when logged into the router console. This console is available by logging into the router with Secure Shell (i.e. ssh) or by slecting the 'Device Console' from  'System > System Control > Device Options' in the router UI. The logs can be viewed or cleared with the following CLI commands:

	log (displays logs in the terminal window)
	log -s <text> (search for logs that contain <text> and displays them)
	log -s -i <text> (search for logs that contain <text> but case insensitive)
	log clear (clears the log buffer)
	help log (display the log command options)


<a name="devmode"></a>
## Router Development Mode ##
In order to install an application directly to the router without using ECM, the router must be placed in **DEV** mode. One would typically debug and test an application using **DEV** mode prior to using ECM for installation. **DEV** mode allows for quicker and easier testing and debugging. Instructions for setting up a router for **DEV** mode is in Knowledge Base article ['SDK Enable Developer Mode'](https://dev.cradlepoint.com/s/article/ka1380000000EXqAAM/sdk-enable-development-mode). 


<a name="ecm"></a>
## ECM Application Deployment ##
ECM is used to securely deploy applications to routers at the group level. If an application *tar.gz* package is uploaded to ECM and then assigned to a router group, ECM will then securely download and install the application to the routers within the group. For security, the application files are not user accessible within ECM or routers. That is, one is not able to download the application from the router or ECM.

 
<a name="sample"></a>
## Sample Application Walk Through ##
Cradlepoint has provided several sample applications with the SDK which is located [here](https://github.com/cradlepoint/sdk-samples). Any of these apps can be used as a starting point for your application. The application data structure is described  [here](#overview). 


When using the SDK make.py file, be sure to invoke the proper python command based on your computer OS.

- Linux or OS X:

		python3

- Windows:

		python

### How to Run the Hello World Sample App ###
1. Download the SDK and sample apps from [here](https://github.com/cradlepoint/sdk-samples).
2. Ensure your computer has been setup. See [Computer Setup Instructions](#setup).
2. Connect the router to your computer. This can be done by connecting the LAN port of the router to the USB port of your computer via a USB to Ethernet adapter.
3. Ensure the router is in DEV Mode. See [here](#devmode).
4. Enable Debug logs in the router which is very helpful. See [here](http://knowledgebase.cradlepoint.com/articles/Support/fw6-Understanding-Router-Log-Files-and-Features?retURL=%2Fapex%2FknowledgeSearch%3Fc%3DAll_Products%26p%3D3%26k%3Ddebug%2Blogs%26t%3D%26l%3D%26lang%3Den_US&popup=false&c=All_Products&lang=en_US)
6. Open a terminal window.
7. Change directory to 'sample_apps'.
8. Update the sdk_setting.ini file based on your needs and for the sample app you wish to run. The hello\_world is a good app to test.

    Example:

		[sdk]
		app_name=hello_world
		dev_client_ip=192.168.0.1
		dev_client_username=admin
		dev_client_password=44224267

11. Verify router connectivity via:

		$ python(3) make.py status

12. Create the application package
 
		$ python(3) make.py 

13. Install the application package
 
		$ python(3) make.py install

14. Check the application status to ensure it has started.

		$ python(3) make.py status

15. Also check the logs in the router to ensure the application is creating 'Hello World' logs. In the router console use the 'log' command.



----------

Published Date: 6-1-2017

This article not have what you need? Not find what you were looking for? Think this article can be improved? Please let us know at [suggestions@cradlepoint.com](mailto:suggestions@cradlepoint.com).