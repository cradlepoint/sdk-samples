REM curl -s --digest --insecure -u admin:441b1702 -H "Accept: application/json" -X PUT http://192.168.1.1/api/control/system/sdk/action -d "stop 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"
REM {"data": {"exception": "key", "key": "data"}, "success": false}
REM curl -s --digest --insecure -u admin:441b1702 -H "Accept: application/json" -X PUT http://192.168.1.1/api/control/system/sdk/action -d data="stop 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"
REM curl -s --digest --insecure -u admin:441b1702 -H "Accept: application/json" -X PUT http://192.168.1.1/api/control/system/sdk/action -d data='"stop 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"'

curl -s --digest --insecure -u admin:441b1702 -X PUT http://192.168.1.1/api/control/system/sdk/action -d data='{"data:"stop 7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c"}'
