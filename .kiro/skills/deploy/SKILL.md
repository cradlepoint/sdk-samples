---
name: deploy
description: Build and deploy an SDK app to the dev Cradlepoint router with make.py deploy, then verify it started from the log output. Use when the user says "deploy", asks to push an app to the router, or wants to confirm a deployed app is running. Accepts an app name, e.g. /deploy my_app.
---

# Deploy an SDK app to the router

If the user named an app, deploy that one. Otherwise omit the name and `make.py` falls back to
`app_name` in `sdk_settings.ini`.

## 1. Pre-flight

Read `sdk_settings.ini`. If `dev_client_password` is `mypassword`, `your_password`, or empty, stop
and ask the user for real router credentials — do not deploy with a placeholder, and never echo
the password back.

## 2. Deploy

```bash
.venv/bin/python3 make.py deploy {app_name}      # Mac/Linux
.venv\Scripts\python make.py deploy {app_name}   # Windows
```

This purges old apps, builds the package, installs it, and starts the app (`auto_start=true`).
Do **not** run `clean`, `install`, or `start` separately, and do not delete old `.tar.gz` files
first. Never call `make.py install` directly.

## 3. Verify from the deploy output alone

- **Check timestamps.** Each log line carries `HH:MM:SS`. The router's log buffer holds entries
  from earlier deploys, so only trust lines stamped *after* you started this deploy. Lines without
  a recent timestamp are stale and say nothing about this deployment.
- If recent lines show the app starting (e.g. `Starting {app_name}`, `Web server started`), you
  are done. **Do not** re-run `make.py status` or fetch logs again.
- An SCP "lost connection" during install is normal — the router closes the SSH connection once it
  has the file.
- On Windows, `Exit Code: 1` is reported for every command and is never a failure. Judge only by
  printed output. Full detail in `.kiro/steering/windows-notes.md`.

## 4. If it did not start

Report the actual log lines rather than guessing. Common causes: a syntax error from a Python 3.8
incompatibility, a missing stdlib module on cppython (`csv`, `decimal`, `pkg_resources`), or an
unhandled exception at import time. The app is deleted by the router if any packaged file was
modified after signing.
