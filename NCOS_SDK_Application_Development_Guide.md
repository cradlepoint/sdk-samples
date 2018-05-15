# **NCOS SDK Application Development Guide** #

----------

## Quick Links ##

#### [Overview](#overview) ####
#### [Developer Community](#community) ####
#### [Cradlepoint Knowledge Base](#knowledge) ####
#### [NCOS Python Environment](#environment) ####
#### [Computer Setup Instructions](#setup) ####
#### [NCOS Development Mode](#devmode) ####
#### [Application Directory Structure](#structure) ####
#### [Application Package Anatomy](#anatomy) ####
#### [SDK Instructions Overview](#sdk) ####
#### [NCOS Syslog for Debugging](#syslog) ####
#### [NCM Application Deployment](#ncm) ####
#### [Sample Application Walk Through](#sample) ####


<a name="overview"></a>
## Overview ##
Cradlepoint’s NCOS device Application Framework provides the ability to add intelligence in the device. Applications written in Python can be securely downloaded to the device via [Network Cloud Manager](https://cradlepoint.com/ecm) (NCM). This allows for extended device features, FOG Computing, and IoT management.

At a high level, the Cradlepoint NCOS Device Apps/SDK is a mechanism to package a collection of files – including executable files – in an archive, which can be transferred securely via NCM, hidden within a Cradlepoint device, and executed as an extension to normal firmware.

### What is Supported? ###
For the scope of this document, NCOS Apps are limited to the non-privileged Python scripts. Supported functionality:

- Standard TCP/UDP/SSL socket servers function on ports higher than 1024.
- Standard TCP/UDP/SSL socket client to other devices (or the device as 127.0.0.1/localhost).
- Access to serial ports via the PySerial module, including native and USB-serial ports.
- Ability to PING external devices.
- UI Extensibility (i.e. Hot Spot splash page or other UI WEB pages)
- Access to the NCOS API (aka: status and control tree data).
- USB Memory device file access.

### What is not Supported? ###
- Any form of natively compiled or kernel linked code.
- Any function requiring privileged (or root) permissions.
- Access to shared resources (for example: no ability to issue custom AT commands to cell modems).
- Modifications of routing or security behavior.

### Supported NCOS Devices ###
Please refer to the specifications for the device at [www.cradlepoint.com](https://www.cradlepoint.com)

### Application Development ###
During development, an application can be directly installed into a 'DEV Mode' device. This makes it easier to debug and work through the development process. Once the application has been fully debugged and is ready for deployment, it can be installed via NCM at the group level.

### SDK Toolset ###
Cradlepoint has a simplified SDK, written in python, which builds and creates an app package. The SDK, along with sample applications is located [here](https://github.com/cradlepoint/sdk-samples/releases). 

For app development, the SDK is used to install, start, stop, uninstall, and check status of the application in a locally connected development device. The application package is the same for local debugging or for uploading to the NCM for production deployment. Application development can be done on Linux, OS X, and Windows operating systems with the same SDK.

This document is specifically written for SDK version 2.0 and above.


<a name="community"></a>	
## Developer Community ##
Cradlepoint has a [Developer Community Portal](https://dev.cradlepoint.com) to leverage knowledge, share, and collaborate with other developers. This forum is also actively monitored by Cradlepoint to answer questions.


<a name="knowledge"></a>
## Cradlepoint Knowledge Base ##
The existing [Cradlepoint Knowledge Base](http://knowledgebase.cradlepoint.com) also has many articles related to NCOS applications and the SDK.


<a name="environment"></a>	
## NCOS Python Environment ##
Application are written in python. However, NCOS only contains a subset of a typical python installation on a computer. The list of python modules in the NCOS device can be obtained by installing sample app python\_module\_list which is included with the SDK. This application will list all of the python modules in the logs.

New python files can be added to your application but their dependencies must also adhere to the NCOS python environment. These new python files/modules can be copied to the main application directory or can be installed using pip. If pip is used, any 'egg' or 'dist' directories can be deleted as they are not required for functionality and will just use up memory unnecessarily when installed into the NCOS device. 

Example pip command:
pip(3) install --ignore-install --target=<path to application directory\> <python module name\>

**note:** Use pip on Windows and pip3 on Linux or OS X.

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
		pip3 install cryptography

1. Useful tools

    PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=linux](https://www.jetbrains.com/pycharm/download/#section=linux).
 

<a name="Mac"></a>
### Mac OS X ###
1. Install python 3.5.1 from [python.org](http://www.python.org).

3. Install HomeBrew for package updates. 

		/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

6. Install required libraries.

		brew install openssl
		brew install http://git.io/sshpass.rb

1. Install python libraries. 

		pip3 install -U pip
		pip3 install requests
		pip3 install pyopenssl
		pip3 install cryptography

1. Useful tools

    PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=macOS](https://www.jetbrains.com/pycharm/download/#section=macOS).
    

<a name="Windows"></a>
### Windows ###
1. Install python 3.5.1 from [https://www.python.org/downloads/release/python-351/](https://www.python.org/downloads/release/python-351/).
3. The SDK requires OpenSSL tools to generate digital signatures. Go here [https://slproweb.com/products/Win32OpenSSL.html](https://slproweb.com/products/Win32OpenSSL.html) and download the 'Light' version based on your machine (i.e. Win64 or Win32). Then run the executable after it is downloaded to install.

4. Open a terminal window and use the following commands to install python libraries.

		python -m pip install -U pip
		python -m pip install pyserial
		python -m pip install requests
		python -m pip install pyopenssl
1. Useful tools
    1. Putty: [http://www.putty.org/](http://www.putty.org/)
    2. PyCharm (community version is free): [https://www.jetbrains.com/pycharm/download/#section=windows](https://www.jetbrains.com/pycharm/download/#section=windows).
    3. 7-zip: [http://www.7-zip.org/](http://www.7-zip.org/)
    4. MarkdownPad: [http://markdownpad.com/](http://markdownpad.com/)
    

<a name="structure"></a>
## SDK/Apps Directory Structure ##
Below is the directory structure for for the SDK and sample applications. The **BOLD** items are modified or created by the developer. The other files are used by the SDK or are referenced by the other files.

- NCOS_Apps (directory)
	- app_template (directory for the application)
		- **package.ini** - App initialization items.
		- **app_name.py** - The app python code. There can be multiple py files based on the app design.
		- cs.py - This is included with every sample app and should be in your app. It contains a CSClient class which is a wrapper for the TCP interface to the device config store (i.e. the NCOS JSON API trees).
		- app_logging.py - If included, this contains a class which can be used to generate NCOS syslogs at different levels (i.e. info, debug, error, etc.). Can be found in the common directory of the SDK.
		- **install.sh** - Runs on app installation. (update with app name) 
		- **start.sh** - Script that starts an app (i.e. cppython app_name.py start).
		- **stop.sh** - Script that stops an app (i.e. cppython app_name.py stop).
	- config (directory)
		- **settings.mk** - Build system config settings (i.e. NCOS Device MAC, IP, Username, Password, etc.).
	- common
		- cs.py - This is included with every sample app and can be copied into your app directory. It contains a CSClient class which is a wrapper for the TCP. 
	- tools (directory)
		- bin (directory)
			- package_application.py - Used by SDK.
			- validate_application.py - Used by SDK.
			- pscp.exe - An executable use on Windows by the SDK.
	- **sdk_setting.ini** - Used by the SDK and contains the settings for building the app and connecting to the local NCOS device.
	- NCOS\_SDK_V2.0\_Application\_Development\_Guide.html 
	- NCOS\_APIs\_for\_Applications.html 
	- GNU\_Make\_README.html 

Based on the sdk\_setting.ini file, the SDK will build all files located in the *app\_name* directory into a *tar.gz* package that can then been installed into the device. This installation is either directly into the device (if in DEV mode) or via NCM for grouped devices.

<a name="anatomy"></a>
## Application Package Anatomy ##
A NCOS application package, which is a *tar.gz* archive, consists of a set of files that includes the python executable, start/stop scripts, initialization files, along with manifest and signature files. This package of files is built by the SDK base on the sdk_settings.ini. Some of these files, like the manifest and signature files, are created by the Make tool. Others are created by the application developer. Below are the example contents for a tar.gz archive created for a NCOS application.
 
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
This initialization file contains information and about the application and items that affect installation and execution. This information will stored in /status/system/sdk within the NCOS config store for installed apps.

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

- **firmware\_major and firmware\_minor**

    This is the required device firmware version for the app. ***Not  implemented at this time.***

- **restart**
    If set to 'true', the application will be restarted if it dies or is not running. If false, the device will not attempt to restart the application.
d
- **reboot**
    If set to 'true', the application will be started following a device reboot. Otherwise, it will not be restarted.

- **version\_major and version\_minor**

    This contains the app version. This must be incremented for any new production app used installed via NCM. It will not re-install the same version that already exist in the device.

- **auto_start**

    If set to 'true', the app will automatically start after installation. 


### install.sh ###
This script is executed when the application is installed in the device. Typically it will just add logs for the installation.

For example:

    #!/bin/bash
    echo "INSTALLATION hello_world on:" >> install.log
    date >> install.log

### start.sh ###
This script is executed to start the application in the device. It contains the command to start the python script and pass any arguments. 

For example:

    #!/bin/bash
    cppython hello_world.py start

### stop.sh ###
This script is executed when the application is stopped in the device. It contains the command to stop the python script. 

For example:

    #!/bin/bash
    cppython hello_world.py stop


<a name="sdk"></a>
## SDK Instructions Overview ##
The SDK includes a python make.py file which is compatible for Windows, Linux and OS X platforms. 

### SDK actions are: ###
**default (i.e. no action given):**
    Print a help file

 **clean:**
    Clean all project artifacts. Entails execution of all "-clean" make targets.

 **build or package:**
    Create the app archive tar.gz file.

 **status:**
    Fetch and print current app status from the locally connected device.

 **install:**
    Secure copy the app archive to a locally connected device. The device must already be in SDK DEV mode via registration and licensing in NCM. **Note:** A 'Connection reset by peer' error will be displayed even when the application is successfully copied to the device. This occurs when the device drops the connections after the file copy is complete.

 **start:**
    Start the app on the locally connected device.

 **stop:**
    Stop the app on the locally connected device.

 **uninstall:**
    Uninstall the app from the locally connected device.

 **purge:**
    Purge all apps from the locally connected device.
    
 **uuid:**
    This will create a new UUID for the app and write it to the package.ini file.

### SDK Usage ###
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

        python(3) make.py build

5.  Test connectivity with your device via the status target.

        python(3) make.py status
        {
            "data": {},
            "success": true
        }

6.  Install the application on your device.

        python(3) make.py install
        admin@192.168.0.1's password: 
        hspt.tar.gz                          100% 1439     1.4KB/s   00:00    
        Received disconnect from 192.168.0.1: 11: Bye Bye
        lost connection

7.  Get the application execution status from your device.

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

8.  Uninstall the application from your device.

        python(3) make.py uninstall
        {
            "data": "uninstall 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c",
            "success": true
        }


<a name="syslog"></a>
## NCOS Syslog for Debugging ##
Application debugging is accomplished with the use of debug syslogs. However, the default logging level in the NCOS device is set to **info** so this will need to be changed to **debug**. It is also possible to send the device logs to a syslog server running on another device. For more information, see the Knowledge Base article ['Understanding Router Log Files'](https://cradlepoint.secure.force.com/kb/articles/Support/NCOS-Understanding-Router-Log-Files-and-Features/?q=debug+logs&l=en_US&fs=Search&pn=2).

You can also view logs via CLI commands when logged into the NCOS device console. This console is available by logging into the device with Secure Shell (i.e. ssh) or by selecting the 'Device Console' from  'System > System Control > Device Options' in the device UI. The logs can be viewed or cleared with the following CLI commands:

	log (displays logs in the terminal window)
	log -s <text> (search for logs that contain <text> and displays them)
	log -s -i <text> (search for logs that contain <text> but case insensitive)
	log clear (clears the log buffer)
	help log (display the log command options)


<a name="devmode"></a>
## NCOS Development Mode ##
In order to install an application directly to the device without using NCM, the NCOS device must be placed in **DEV** mode. One would typically debug and test an application using **DEV** mode prior to using NCM for installation. **DEV** mode allows for quicker and easier testing and debugging. Instructions for setting up an NCOS device for **DEV** mode is in Knowledge Base article ['SDK Enable Developer Mode'](https://dev.cradlepoint.com/s/article/ka1380000000EXqAAM/sdk-enable-development-mode). 


<a name="ncm"></a>
## NCM Application Deployment ##
NCM is used to securely deploy applications to devices at the group level. If an application *tar.gz* package is uploaded to NCM and then assigned to a NCOS device group, NCM will then securely download and install the application to the devices within the group. For security, the application files are not user accessible within NCM or devices. That is, one is not able to download the application from the device or NCM.

 
<a name="sample"></a>
## Sample Application Walk Through ##
Cradlepoint has provided several sample applications with the SDK which is located [here](https://github.com/cradlepoint/sdk-samples/releases). Any of these apps can be used as a starting point for your application. The application data structure is described  [here](#overview). 


When using the SDK make.py file, be sure to invoke the proper python command based on your computer OS.

- Linux or OS X:

		python3

- Windows:

		python

### How to Run the Hello World Sample App ###
1. Download the SDK and sample apps from [here](https://github.com/cradlepoint/sdk-samples/releases).
2. Ensure your computer has been setup. See [Computer Setup Instructions](#setup).
2. Connect the NCOS device to your computer. This can be done by connecting the LAN port of the device to the USB port of your computer via a USB to Ethernet adapter.
3. Ensure the device is in DEV Mode. See [here](https://cradlepoint.secure.force.com/kb/articles/Manual/NCOS-sdk-enable-development-mode/?q=dev+mode&l=en_US&fs=Search&pn=1).
4. Enable Debug logs in the device which is very helpful. See [here](https://cradlepoint.secure.force.com/kb/articles/Support/NCOS-Understanding-Router-Log-Files-and-Features/?q=debug+logs&l=en_US&fs=Search&pn=2)
6. Open a terminal window.
7. Change directory to sample\_apps. Depending on the version of the SDK that was downloaded, this could be 'sample\_apps' or 'sdk\_samples-2.1', etc.
8. Update the sdk_settings.ini to utilize the hello\_world app.

    Example:

		[sdk]
		app_name=hello_world
		dev_client_ip=192.168.0.1
		dev_client_username=admin
		dev_client_password=44224267

11. Verify device connectivity via:

		$ python(3) make.py status

12. Create the application package
 
		$ python(3) make.py build

13. Install the application package. **Note:** A 'Connection reset by peer' error will be displayed even when the application is successfully copied to the device. This occurs when the device drops the connections after the file copy is complete.
 
		$ python(3) make.py install

14. Check the application status to ensure it has started.

		$ python(3) make.py status

15. Also check the logs in the device to ensure the application is creating 'Hello World' logs. In the device console use the 'log' command.



----------

Published Date: 5-15-2018

This article not have what you need? Not find what you were looking for? Think this article can be improved? Please let us know at [suggestions@cradlepoint.com](mailto:suggestions@cradlepoint.com).