---
inclusion: manual
description: "Deploy SDK app to Cradlepoint router via make.py deploy (cross-platform)"
---
# Deploy SDK App

Deploy the SDK app to the router:

1. Read `sdk_settings.ini` to get the `app_name`
2. Run the deploy command:

- Windows: `.venv\Scripts\python make.py deploy {app_name}`
- Mac/Linux: `.venv/bin/python make.py deploy {app_name}`

This will:
1. Purge all apps from router
2. Build the app package
3. Install to router
4. Show recent logs filtered by app name

After deployment, verify the app started successfully by checking the logs.

**Note:** Before deploying, read `sdk_settings.ini` and check that `dev_client_password` is not the default `mypassword`. If it is, open `sdk_settings.ini` and tell the user to update it with their router credentials before proceeding.
