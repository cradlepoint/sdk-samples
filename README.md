# Router App/SDK sample application design tools.

Note that the most complete documentation is at present in this wiki:
<http://wikis.iatips.com/index.php?title=CP_MainPage>

Eventually, the info will move to a formal Developer Portal. 
 
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
