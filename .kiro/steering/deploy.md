---
inclusion: manual
description: "Deploy SDK app to Cradlepoint router via make.py deploy (cross-platform)"
---
# Deploy SDK App

Deploy the SDK app to the router:

```bash
python3 make.py deploy {app_name}
```

This will:
1. Purge all apps from router
2. Build the app package
3. Install to router
4. Show recent logs filtered by app name

After deployment, verify the app started successfully by checking the logs.

**Note:** Ensure sdk_settings.ini has correct router IP and credentials before deploying.
