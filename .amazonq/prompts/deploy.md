# Deploy SDK App

Deploy the SDK app to the router using deploy.sh:

```bash
bash deploy.sh {app_name}
```

This will:
1. Purge all apps from router
2. Build the app package
3. Install to router
4. Show recent logs filtered by app name

After deployment, verify the app started successfully by checking the logs.
