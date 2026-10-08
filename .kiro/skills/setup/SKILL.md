---
name: setup
description: Run the full dev environment setup for this repo via setup_env.py - rebuild .venv, install requirements, configure the dev router IP and credentials in sdk_settings.ini, and check the router connection and Developer Mode status. Use when the user says "setup", asks to configure or change the router, reports that imports or deploys are failing, or when the session-start environment check reported a problem.
---

# Set up the dev environment

Get this repo ready to build and deploy NCOS SDK apps by chatting.

The **Check Environment** session-start hook already creates `.venv` and installs dependencies
automatically. This is the full pass — run it when the user asks for setup, when the session-start
hook reported `kiro-env: PROBLEM`, or when router settings need to change. Run the steps even if
the environment looks fine; the router connection and Developer Mode check are the point.

## Steps

1. Run the setup script from the repo root, non-interactively:
   - Mac/Linux: `python3 setup_env.py -y`
   - Windows: `python setup_env.py -y`

   If that command is not found, try the other one. The script creates `.venv`, installs
   `requirements.txt`, points the IDE interpreter at `.venv`, and checks the router connection
   and Developer Mode status.

2. Report what the script found in a couple of sentences. If the venv or dependency install
   failed, fix that before moving on.

3. Check `sdk_settings.ini`. If `dev_client_password` is still a placeholder (`mypassword`,
   `your_password`, empty), or the router check reported bad credentials or no response, ask the
   user for:
   - dev-mode router IP address
   - router username
   - router password

   Tell them they can reply "skip" and set it later by editing `sdk_settings.ini` or running
   `python setup_env.py --configure`. Do not nag if they skip.

4. If they give the values, write them into the `[sdk]` section of `sdk_settings.ini` with
   `str_replace`, keeping `key=value` format (no spaces around `=`). **Never echo the password
   back.** Verify with `.venv/bin/python3 setup_env.py -y` (Mac/Linux) or
   `.venv\Scripts\python setup_env.py -y` (Windows).

5. If SDK mode is `standard` instead of `devmode`, tell the user Developer Mode is enabled in
   NetCloud Manager under **Tools > Developer Mode Devices** — never in the router's local UI.

6. Close with a short summary and three example asks:
   - "Build a web app that shows WAN status and signal strength for all modems"
   - "Create an app that runs a speedtest every hour and logs results to CSV"
   - "Explain how #5GSpeed works"

Keep it brief. Do not create files beyond what `setup_env.py` creates.

## Useful flags

`-y` (no prompts) · `--quiet` (only report problems) · `--configure` (router settings only) ·
`--skip-router` (venv only) · `--no-check` (skip the router connection test) ·
`--router-ip` / `--router-username` / `--router-password` (set settings without prompting).

`setup_env.py -y` is also the fastest way to verify the router is reachable and in Developer Mode
before deploying.
