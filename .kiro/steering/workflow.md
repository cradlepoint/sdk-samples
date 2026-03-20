---
inclusion: auto
description: "Cradlepoint SDK development workflow and prompt shortcuts"
---
# Cradlepoint SDK Development Workflow

## Use Specs for New Apps

When building a new SDK app (not a quick script), use a Kiro Spec to plan before coding:
1. Define requirements — what APIs, what UI, what data
2. Design — break into tasks, identify API paths needed
3. RTFM — verify all API paths exist before implementation tasks
4. Implement — work through tasks step by step

This prevents the "code first, debug later" cycle. Start a spec with: "Create a spec for [app description]".

## Python Environment

Use `python3` for all commands.

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

```text
app_name/
├── package.ini          # Metadata with uuid, version, vendor
├── cp.py               # CP module copy
├── {app_name}.py       # Main logic
├── start.sh            # Uses cppython
├── readme.md           # Usage and appdata fields
├── static/             # Web assets (if applicable)
└── mylib/              # Subdirectories with Python modules work fine
```

- **Multi-file apps work** - apps can have subdirectories with Python modules (e.g., `taky/taky/cot/`). Imports work normally. Include `__init__.py` in each package directory

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
- Cleaning old build artifacts
- Building the app package
- Stopping the old version
- Installing the new version
- Starting the app
- Showing status and logs

**Just run `bash deploy.sh {app_name}`** - no need to run `make.py clean` or remove old tar.gz files first. deploy.sh handles everything. The app auto-starts after install (auto_start=true in package.ini), so there's no need to run `make.py start` either.

**NEVER use make.py install directly** - always use deploy.sh for deployment.

**deploy.sh output is sufficient** - if logs show app started successfully (e.g., "Starting app_name", "Web server started"), DO NOT run status or logs commands again. The deployment verification is already complete.

**ALWAYS check log timestamps after deploy** - deploy.sh shows timestamps (HH:MM:SS) on each log line. Only trust logs with timestamps AFTER you ran the deploy. The router log buffer contains old entries from previous deploys — if you see logs without recent timestamps, they are stale and do not reflect the current deploy.

## Other Commands

```bash
python3 make.py status {app_name}     # Check app status
python3 make.py start {app_name}      # Start app
python3 make.py stop {app_name}       # Stop app
python3 make.py uninstall {app_name}  # Remove app
python3 make.py clean {app_name}      # Remove build artifacts
```
