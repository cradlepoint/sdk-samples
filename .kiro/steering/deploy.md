---
inclusion: manual
description: "Deploy SDK app to Cradlepoint router via deploy.sh"
---
# Deploy SDK App

Deploy the SDK app to the router using deploy.sh:

```bash
bash deploy.sh {app_name}
```

This will:
1. Update app_name in sdk_settings.ini to match the app being deployed
2. Purge all apps from router
3. Build the app package
4. Install to router
5. Show recent logs filtered by app name

After deployment, verify the app started successfully by checking the logs.

**Note:** Ensure sdk_settings.ini has correct router IP and credentials before deploying.
