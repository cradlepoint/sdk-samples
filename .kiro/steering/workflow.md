---
inclusion: auto
description: "Cradlepoint SDK development workflow and prompt shortcuts"
---
# Cradlepoint SDK Development Workflow

## Python Environment

Use the venv Python for all commands: `/Users/eareelt/environments/sdk/bin/python3.12`

## Saved Prompt Shortcuts

- **When user says "rtfm"** - Load `.kiro/steering/rtfm.md` (Read The Fantastic Manual - API verification workflow)
- **When user says "learn"** - Load `.kiro/steering/learn.md` (Update rules and docs based on what was learned)
- **When user says "deploy"** - Load `.kiro/steering/deploy.md` (Deploy app to router workflow)

## Configuration Files

- **NEVER make up configuration formats** - always reference actual files like @sdk_settings.ini
- **ALWAYS check sdk_settings.ini before deploying** - if it contains default password (mypassword), warn the user to update it first

### sdk_settings.ini format:
```ini
[sdk]
app_name=your_app_name
dev_client_ip=192.168.1.4
dev_client_username=admin
dev_client_password=your_password
```

Default/placeholder values that indicate unconfigured settings:
- dev_client_password=mypassword

## Project Structure

```
app_name/
├── package.ini          # Metadata with uuid, version, vendor
├── cp.py               # CP module copy
├── {app_name}.py       # Main logic
├── start.sh            # Uses cppython
├── readme.md           # Usage and appdata fields
└── static/             # Web assets (if applicable)
```

## Create App

```bash
python3 make.py create {app_name}
```

This generates all required files from app_template (package.ini, start.sh, cp.py, {app_name}.py, readme.md).

**CRITICAL: Before writing ANY app code:**
1. **RTFM FIRST** - Use `#rtfm.md` steering file to verify API paths, fields, and structures
2. **ASK USER for unknowns** - Never assume requirements, data formats, or behavior
3. **VERIFY with curl/DTD** - Test API endpoints before coding
4. **THEN code** - Only write code after verification

**NEVER:**
- Assume API fields exist without testing
- Make up data structures or formats
- Guess at user requirements
- Write code before verifying APIs

**After creation, only modify the main {app_name}.py file and readme.md** - all other files are generated correctly.

**NEVER overwrite package.ini, start.sh, or cp.py after creation** - these are auto-generated and correct.

**ALWAYS deploy after creating or modifying an app** - use `bash deploy.sh {app_name}` immediately after code changes.

## Deploy to Router

**ALWAYS use deploy.sh script** - `bash deploy.sh {app_name}`

This script handles:
- Building the app package
- Stopping the old version
- Installing the new version
- Starting the app
- Showing status and logs

**NEVER use make.py install directly** - always use deploy.sh for deployment.

**deploy.sh output is sufficient** - if logs show app started successfully (e.g., "Starting app_name", "Web server started"), DO NOT run status or logs commands again. The deployment verification is already complete.

**ALWAYS check log timestamps after deploy** - log entries include Unix epoch timestamps. Only consider logs with timestamps AFTER the deploy started. Old log entries from previous deploys will still be in the buffer.

## Other Commands

```bash
python3 make.py status {app_name}     # Check app status
python3 make.py start {app_name}      # Start app
python3 make.py stop {app_name}       # Stop app
python3 make.py uninstall {app_name}  # Remove app
python3 make.py clean {app_name}      # Remove build artifacts
```
