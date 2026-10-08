# Cradlepoint NCOS SDK — AI Coding Conventions

This repo builds SDK apps that run on Ericsson Cradlepoint routers (NCOS) under `cppython`, a
**Python 3.8** interpreter on **ARM64/musl**. Apps live in `apps/{app_name}/`.

## Read these — they are the source of truth

This file is a short entry point, not a copy. The full conventions live in `.kiro/steering/`,
which is shared with Kiro and kept current. **Read the files relevant to your task before
writing code.** Do not work from this summary alone.

| Read this | For |
|---|---|
| `.kiro/steering/core.md` | the non-negotiables (also summarized below) |
| `.kiro/steering/api-reference.md` | **API verification workflow**, `cp` module, gotcha index |
| `.kiro/steering/coding-standards.md` | Python 3.8/cppython limits, libraries, memory, app lifecycle, local runs |
| `.kiro/steering/workflow.md` | `make.py`, create/deploy/contribute, `sdk_settings.ini`, layout |
| `.kiro/steering/web-standards.md` | `http.server`, ports, the web app template and design system |
| `.kiro/steering/gps-standards.md` | GPS, NMEA, GNSS, RTK |
| `.kiro/steering/speedtest-standards.md` | netperf, iPerf3, Ookla BYOB |
| `.kiro/steering/container-standards.md` | Docker/containers (read before proposing one) |
| `.kiro/steering/windows-notes.md` | Windows: exit code 1 is not a failure |

Reference documentation, grep it rather than guessing:

- `docs/ncos-api/` — API paths, response structures, `PATHS.md`, and **`gotchas.md`** (verified
  surprises worth reading before debugging anything)
- `docs/cp_methods_reference.md` — every `cp` helper signature
- `docs/NCOS_SDK_Developer_Guide.md` — SDK concepts, app lifecycle, packaging

Task procedures are in `.kiro/skills/{deploy,rtfm,learn,setup}/SKILL.md`. Read the matching one
when the user asks to deploy, verify an API path, record a learning, or set up the environment.

## Non-negotiables

- **Python 3.8 only** — no `str | None` (use `Optional[str]`), no `match`/`case`.
- **Never `print()`** — use `cp.log()`. The router has no screen, no keyboard, no `input()`.
- **Catch, never raise** — wrap API calls in `try/except Exception` and log. No bare `except:`.
- **Relative paths only** — `tmp/`, never `/tmp`. `os.makedirs('tmp', exist_ok=True)` first.
- **Never modify a packaged file** — apps are signed (`MANIFEST.json`); the router deletes the app
  if a packaged file changes. Write to new files only.
- **Never overwrite `package.ini`, `start.sh`, or `cp.py`** — `make.py create` generates them.
- **Never invent an API path or field.** Run the verification workflow in `api-reference.md`:
  grep `docs/ncos-api/` → read the doc → check `/api/dtd/config/<path>` → test the live endpoint
  with `curl -u admin:pass` → only use fields seen in a real response → then write code.
  **Always REST with basic auth, never SSH for API validation.**
- **Never invent a `cp` function name** — read `cp.py` or `docs/cp_methods_reference.md`.
- **Never use random or placeholder data** — real data from router APIs, or `None`.
- **Never write defaults to appdata** — that overrides NCM group config. Default in code instead.
- **Never commit `sdk_settings.ini`**, and never print the router password.
- **Never build or deploy a container without explicit user confirmation** — containers need an
  Advanced license. Prefer an SDK app; a pure-Python dependency is not a reason to use a container.

## Deploy after every change

```bash
.venv/bin/python3 make.py deploy {app_name}      # Mac/Linux
.venv\Scripts\python make.py deploy {app_name}   # Windows
```

Do not ask first. `deploy` purges, builds, installs, and starts the app — never call
`make.py install` directly. Omit the name to use `app_name` from `sdk_settings.ini`. Every repo
command runs through the venv interpreter. Other subcommands: `create`, `status`, `start`, `stop`,
`uninstall`, `clean`, `contribute`, `setup`.

Judge success by printed output and **check log timestamps** — the router's log buffer holds
entries from earlier deploys, so only lines stamped after this deploy mean anything.

## Easy things to get wrong

These are the summary versions. Each has fuller detail in the file named.

- **Statically linked ARM64 binaries ARE supported** — the "pure Python only" rule is about `.pyc`
  and `.so`, not bundled executables. Binaries lose the execute bit during tar extraction on the
  router, so `os.chmod(path, 0o755)` before first use. (`coding-standards.md`)
- **`restart = true` in `package.ini` makes the router relaunch the app whenever the process
  exits** — a run-once app becomes a hot restart loop every ~2 seconds. One-shot apps must never
  fall off the end of `main()`; park in `while True: time.sleep(...)`. (`coding-standards.md`)
- **`requests` is pre-installed on cppython — do not bundle it.** `pkg_resources`, `decimal`, and
  `csv` are missing and need shims; `redis` is unavailable. Install libraries with
  `pip3 install -t path/to/app_folder name`. (`coding-standards.md`)
- **Never fetch large API trees in a polling loop** — use the most specific sub-path, and always
  `time.sleep()`. Routers have limited RAM. (`coding-standards.md`)
- **`cp.get()` returns data directly**; raw REST wraps it in `{"success": ..., "data": ...}`.
  `cp.put()` returns a *different* envelope locally than on-router — check both `status` and
  `success`. (`api-reference.md`, `coding-standards.md`)
- **A config PUT can return `ok` and apply nothing** — partial dict PUTs merge rather than replace,
  and unsupported paths can report success. Read the value back before trusting a write.
  (`docs/ncos-api/gotchas.md`)
- **Which modem signal keys exist depends on the live radio technology, not the modem** — 5G SA
  reports only `RSRP_5G`/`RSRQ_5G`/`SINR_5G` with no `DBM`; LTE reports only the LTE set; 5G NSA
  reports both. Re-read the available keys each poll. (`docs/ncos-api/gotchas.md`)
- **`status/lan/clients` has no byte counters** — use `status/client_usage`. (`api-reference.md`)
- **Container deploys are form-encoded, not a JSON body** — `-d 'data={...}'`. Named volumes need
  `driver: local`. Use Compose `"2.4"`. (`container-standards.md`)
- **Developer Mode is enabled in NetCloud Manager**, under Tools → Developer Mode Devices — never
  in the router's local admin UI. (`workflow.md`)

## Web apps

Use Python's built-in `http.server` — never Flask, Bottle, or any third-party framework. Copy
`your_web_app.html` and the `static/` folder from `apps/templates/web_app_template` rather than
writing HTML or CSS from scratch. Default port 8000, set `SO_REUSEADDR`, run the server in a
daemon thread. LAN clients reaching a router port requires firewall zone forwarding. Full rules and
the template's known traps are in `web-standards.md`.

## Project layout

```text
apps/{app_name}/
├── package.ini          # Metadata with uuid, version, vendor, tags
├── cp.py                # CP module copy (never modify)
├── {app_name}.py        # Main logic
├── start.sh             # Uses cppython (never modify)
├── readme.md            # Usage and appdata fields (document every field)
├── static/              # Web assets, if applicable
└── METADATA/            # Build signatures (auto-generated)
```

Subdirectories with Python modules work; include `__init__.py` in each package. Do not move an app
after `make.py create` — that path is where CI looks.
