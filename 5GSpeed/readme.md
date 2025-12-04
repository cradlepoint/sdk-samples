Application Name
================
5GSpeed  

[Download the built app from our releases page!](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)


Application Purpose
===================
5GSpeed runs Ookla speedtests and puts results into configurable field.  Designed to enable NCM API support for Ookla speedtests.

Steps to use:
=============
The app will create an entry in the router configuration under System > SDK Data named "5GSpeed" with the path for the results field.
Default is "config/system/asset_id"  

Clear the results by performing any of the following:  

1. Use NCM API PUT router request to clear the results field and to run the SDK speedtest. Wait for 1 min, and run NCM API Get router request to get the result.  

2. Clear the results in NCM > Devices tab (if using description or asset_id)  

3. Go to device console and clear results field:  
put {results_path} ""  

Sample result:  
DL:52.54Mbps - UL:16.55Mbps - Ping:9.715ms - Server:Telstra - ISP:Vocus Communications - TimeGMT:2023-04-11T01:06:43.758382Z - URL:http://www.speedtest.net/result/14595594656.png  

Retrieve Results via NCM API:
=============================
- Generate NCM API v2 API Keys on the Tools page > NetCloud API tab in NCM.  
- Use those keys in the headers of an HTTP GET request to https://www.cradlepointecm.com/api/v2/routers/{router_id/  
- router_id can be found in NCM or at CLI: get status/ecm/client_id  
- The results are in the field defined in SDK Data (default is asset_id)  

Clear results and run new test via NCM API:
===========================================
- Use API keys in headers of an HTTP PUT request to https://www.cradlepointecm.com/api/v2/routers/{router_id/  
- Content-Type: application/json  
- Body contains blank field defined in SDK Data (default is asset_id):  
{"asset_id": ""}  

In a few minutes, new results should populate.
