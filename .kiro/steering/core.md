# Cradlepoint SDK Essentials

This repo builds SDK apps that run on Ericsson Cradlepoint routers (NCOS) under
`cppython`, a **Python 3.8** interpreter on **ARM64/musl**. Apps live in `apps/{app_name}/`.

This file holds the rules that are costly to get wrong in any session. The detail behind them
lives in the topic files listed at the bottom.

## Non-negotiables

- **Python 3.8 only** — no `str | None`, no `match`/`case`. Use `Optional[str]`.
- **Never `print()`** — use `cp.log()`. The router has no screen, no keyboard, no `input()`.
- **Catch, never raise** — wrap API calls in `try/except Exception`, log the error. No bare `except:`.
- **Relative paths only** — `tmp/`, never `/tmp`. `os.makedirs('tmp', exist_ok=True)` first.
- **Never modify a packaged file** — apps are signed (`MANIFEST.json`); the router deletes the
  app if a packaged file changes. Write to new files only.
- **Never overwrite `package.ini`, `start.sh`, or `cp.py`** — `make.py create` generates them correctly.
- **Never invent an API path or field** — run the API Verification Workflow in `api-reference` first.
- **Never invent a `cp` function name** — read `cp.py`.
- **Never use random or placeholder data** — real data from router APIs, or `None`.
- **Never write defaults to appdata** — that overrides NCM group config. Default in code instead.
- **Never commit `sdk_settings.ini`**, and never print the router password.

## Always deploy after changing an app

Run this yourself after any code change. Do not ask first.

```bash
.venv/bin/python3 make.py deploy {app_name}      # Mac/Linux
.venv\Scripts\python make.py deploy {app_name}   # Windows
```

Every repo command uses the venv interpreter (`.venv/bin/python3` or `.venv\Scripts\python`).

## Steering layout

**Always in context** — no action needed, these are already loaded:

| File | Covers |
|---|---|
| `core.md` | this file |
| `api-reference.md` | API verification workflow, `cp` module, docs map, gotcha index |
| `coding-standards.md` | Python 3.8/cppython limits, libraries, memory, app lifecycle, local runs |
| `workflow.md` | `make.py`, create/deploy/contribute, `sdk_settings.ini`, project layout |
| `web-standards.md` | `http.server`, ports, the web app template and design system |

**Loads automatically when a matching file is in context** (`inclusion: fileMatch`):

| File | Fires on paths matching |
|---|---|
| `gps-standards.md` | `*gps*`, `*nmea*`, `*gnss*`, `*rtk*` |
| `speedtest-standards.md` | `*speed*`, `*iperf*`, `*netperf*`, `*ookla*` |

If the task is about GPS or speed testing but no such file is open yet (e.g. a brand-new app),
load the file explicitly with `disclose_context` before writing code.

**Load on request only** (`inclusion: manual`):

| File | When |
|---|---|
| `container-standards.md` | Docker/containers on the router |
| `cradlepoint-docs-api.md` | fetching content from docs.cradlepoint.com |
| `windows-notes.md` | user is on Windows and exit codes are in question |

## Skills — the task workflows

In `.kiro/skills/`. Each is a slash command, and each also activates when a request matches its
description. They take arguments: `/deploy my_app`, `/rtfm status/wan/devices`.

| Skill | Does |
|---|---|
| `deploy` | build + install to the router, then verify it started from the logs |
| `rtfm` | verify an API path and its fields against docs, DTD, and the live router |
| `learn` | record a finding into the right steering file or `docs/ncos-api/` |
| `setup` | run `setup_env.py`: rebuild `.venv`, set router credentials, check Developer Mode |

A user typing "deploy", "rtfm", "learn", or "setup" as a bare word means that skill — use it.

**Reference docs** are not steering — grep them: `docs/ncos-api/` (API paths, structures,
`gotchas.md`), `docs/NCOS_SDK_Developer_Guide.md`, `docs/containers-*.md`.

## Session-start environment check

The **Check Environment** hook runs `setup_env.py --hook` and prints one line:

- `kiro-env: ready ...` — everything is in place. Do **not** run `setup_env.py` again.
- `kiro-env: PROBLEM — ...` — follow the `KIRO —` line in the same output and tell the user
  in plain language. Do not build or deploy until it is fixed.
- No `kiro-env:` line — Python is missing, or the hook did not run.

Interpreter-probe noise (`python: command not found`, Microsoft Store messages) appears before
the `kiro-env:` line. Ignore it; only `kiro-env:` lines are meaningful.
