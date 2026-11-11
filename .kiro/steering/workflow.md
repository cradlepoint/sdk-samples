# Cradlepoint SDK Development Workflow

All commands run through the venv interpreter: `.venv/bin/python3` (Mac/Linux) or
`.venv\Scripts\python` (Windows). The examples below use the Mac/Linux form.

## Use Specs for New Apps

For a new SDK app (not a quick script), use a Kiro Spec to plan before coding:

1. Requirements — what APIs, what UI, what data
2. Design — break into tasks, identify the API paths needed
3. Verify — run the API Verification Workflow (`api-reference.md`) on every path **before**
   implementation
4. Implement — work through tasks step by step

This prevents the code-first/debug-later cycle. Start with: "Create a spec for [app description]".

## make.py commands

```bash
.venv/bin/python3 make.py create {app_name}      # scaffold from apps/templates/app_template/
.venv/bin/python3 make.py deploy {app_name}      # purge → build → install → start → logs
.venv/bin/python3 make.py status {app_name}
.venv/bin/python3 make.py start {app_name}
.venv/bin/python3 make.py stop {app_name}
.venv/bin/python3 make.py uninstall {app_name}
.venv/bin/python3 make.py clean {app_name}       # remove build artifacts
.venv/bin/python3 make.py contribute {app_name}  # open a PR upstream (interactive)
```

- Omit `{app_name}` and make.py uses `app_name` from `sdk_settings.ini`.
- **Apps are found by name, case-insensitively** — repo root first, then `apps/`. The name you
  type does not have to match the folder's case.
- **`install` and `deploy` also accept a `.tar.gz`** — `make.py install "My_App v1.0.0.tar.gz"`
  installs that exact file with no rebuild. Useful for a package someone sent you, where the
  archive name and extracted folder name differ in case.

## Create App

`make.py create {app_name}` generates every required file into `./apps/{app_name}/` and prints
the path. **Do not move the app afterwards** — that is already where the repo keeps apps and where
CI looks, so it is ready to contribute as-is. Only the user decides when and where to move an app.

After creation, modify only `{app_name}.py` and `readme.md`. The rest is generated correctly.

Before writing any app code: run the API Verification Workflow (`api-reference.md`), and
**ask the user about unknowns** rather than assuming requirements, data formats, or behavior.

## Write the readme for the user, not the developer

`readme.md` is for someone who just wants to **use** the app, not read its source. Write it so a
person who found the app in NCM can install it, configure it, and know what it does — without
opening the code. Do not document the implementation (internal functions, code structure, how the
polling loop works); only what a user needs to operate it.

Follow the house style of the existing app readmes (`5GSpeed`, `client_bandwidth_throttle`):

1. **Title + one-line description** — what the app does, in plain language.
2. **Features** — a short bullet list of what the user gets. Include the web UI URL
   (`http://router_ip:8000`) if the app has one.
3. **Usage / Steps to Use** — numbered steps from deploy to result, in the order the user does
   them. Include a screenshot for web apps if one exists.
4. **Settings** — how to configure it (web Settings panel, NCM SDK Data field, etc.) in user terms.
5. **Appdata Fields** — a table with columns `Field | Required | Description` (add `Values` when
   helpful). **Document every appdata field and mark which are required** — this is mandatory per
   `api-reference.md`. Note the in-code default for optional fields.
6. **Sample output / results** — show what the user will see, when the app produces output.

Keep it concise and task-oriented. A short "Technical Details" footnote (which APIs it reads,
where state is stored) is fine at the end, but it is the last thing, not the readme's focus.

## Test locally before deploying (fast iteration)

An app can run **on your computer** against the dev router in `sdk_settings.ini` — `cp.py`
detects it is off-router and uses HTTP REST. This is the fastest way to shake out API reads,
data processing, and business logic without a build/install cycle, and it does **not** require
Developer Mode (REST works regardless; some users develop this way exclusively).

```bash
.venv/bin/python3 my_app/my_app.py      # run from apps/, NOT from inside the app folder
```

- **Run from `apps/`** so `cp.py` can find `sdk_settings.ini` (it only looks in the cwd and its
  parent). Interrupt with Ctrl-C when done.
- **Works locally**: `cp.get/put/post/delete` (real reads and writes hit the router) and
  `cp.log()` (prints to stdout). A local run really does publish to `status/...` and change
  config on the dev router — the effects are live.
- **Does NOT work locally**: `cp.alert()` (never reaches NCM), `cp.register()`/`cp.unregister()`
  (needs the router's internal socket), `cp.decrypt()`, serial, and GPIO. A web UI binds to your
  machine, so LAN clients behind the router can't reach it.
- **Then deploy** to test the pieces that only work on-router (alerts, events, register, web UI
  for LAN clients, serial, GPIO) and to confirm it runs under cppython.

Full mechanics, caveats, and the `cp.put()` envelope difference are in `coding-standards.md`
(*Local Development*).

## Deploy

**Always deploy after creating or modifying an app. Do not ask — just run it.**

```bash
.venv/bin/python3 make.py deploy {app_name}
```

`deploy` purges old apps, builds the package, installs it, and starts the app
(`auto_start=true` in `package.ini`). No need to run `clean`, `install`, or `start` separately,
and no need to delete old `.tar.gz` files first.

- **Never use `make.py install` directly** — always `deploy`.
- **`deploy` output is sufficient verification** — if the logs show the app started (e.g.
  "Starting app_name", "Web server started"), do not re-run `status` or `logs`.
- **Check log timestamps.** `deploy` prints `HH:MM:SS` on each log line. The router's log buffer
  holds entries from previous deploys, so only trust lines timestamped *after* you ran the deploy.
  Lines without recent timestamps are stale.
- An SCP "lost connection" during install is normal — the router drops the SSH connection once it
  has the file.

**On Windows, `Exit Code: 1` is reported for EVERY command and is never a failure signal.** Judge
success only by printed output (`Purge successful`, `Package ... created`, `"state": "started"`).
Never retry, re-diagnose, or ask the user for guidance because of exit code 1. Full explanation
and the per-operation success strings are in `windows-notes.md` (load on request).

## Developer Mode

**Developer Mode is enabled in NetCloud Manager, NOT on the router's local admin UI.**
NCM → Tools → Developer Mode Devices → add the device.

Never tell users to enable Developer Mode on the router itself — there is no such setting there.

## Configuration Files

`sdk_settings.ini` holds the dev router credentials:

```ini
[sdk]
app_name=your_app_name
dev_client_ip=192.168.1.4
dev_client_username=admin
dev_client_password=your_password
```

- **Never make up a config format** — read the actual file (`@sdk_settings.ini`).
- **Check it before deploying.** If `dev_client_password` is still `mypassword` (or empty), tell
  the user to update it first.
- **It is git-ignored** and must never be committed. `setup_env.py` and `make.py` create it from
  `sdk_settings.ini.example` automatically, so never tell the user to copy the example by hand.
- **Edit in place** with `str_replace`, keeping `key=value` (no spaces around `=`), and change
  only `[sdk]` values. Never print or echo the password.

If `.venv` is missing, imports fail, or settings are still placeholders, use the `setup` skill
rather than fixing things by hand. `setup_env.py -y` is also the fastest way to confirm the router
is reachable and in Developer Mode before deploying.

## Project Structure

```text
apps/{app_name}/
├── package.ini          # Metadata with uuid, version, vendor, tags
├── cp.py                # CP module copy
├── {app_name}.py        # Main logic
├── start.sh             # Uses cppython
├── readme.md            # User-facing: usage, settings, appdata fields (see readme section above)
├── static/              # Web assets (if applicable)
└── mylib/               # Subdirectories with Python modules work fine
```

**Multi-file apps work** — subdirectories with Python modules (e.g. `taky/taky/cot/`) import
normally. Include `__init__.py` in each package directory.

`package.ini` tags: connectivity, monitoring, networking, integrations, gpio, vehicle, security,
web, tools, examples, speedtest, mqtt, etc.

## Contribute an App Upstream

`make.py contribute {app_name}` submits one app to `cradlepoint/sdk-samples` as a pull request:
CI preflight, branch off upstream, staged-file confirmation, commit, fork, push, PR.

- **Clone the canonical repo directly, do not fork first** — `origin` stays pointed at
  `cradlepoint/sdk-samples` so `git pull` never needs a fork sync. `contribute` creates the fork
  on demand and adds it as a *second* remote named `fork`.
- **It is interactive** — prompts for confirmation, a commit message, and PR text. Do not run it
  unattended or from a hook.
- **Never suggest committing an app by hand unless the user asks** — `contribute` stages only the
  app folder, where a manual `git add -A` would sweep in unrelated working-tree changes.
- **It needs the GitHub CLI** — offers to download it into `.gh/` (git-ignored) on first run,
  then `gh auth login --web`. Falls back to a browser-driven fork and PR if the user declines.
