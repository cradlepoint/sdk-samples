import json
import subprocess

def cs_get(path):
    p = subprocess.run(["csclient", "-m", "get", "-b", path], capture_output=True, check=True, text=True)
    return json.loads(p.stdout.strip())

def get_appdata(key):
    appdata = cs_get("/config/system/sdk/appdata")
    return next((j['value'] for j in appdata if j['name'] == key), None)