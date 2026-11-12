# NCOS SDK Documentation

Reference material for building NCOS SDK apps. This folder is organized into three groups: the
**SDK guide** (how apps work), the **`cp` module reference** (the API your app calls), and the
**NCOS API reference** (the router paths your app reads and writes).

> **Looking for setup instructions?** Installing Python, cloning the repo, signing in to Kiro,
> and configuring your router all live in the [repo root README](../README.md). This folder is
> reference only — no setup steps here.

## Folder map

```
docs/
├── README.md                      # this file
├── NCOS_SDK_Developer_Guide.md    # the complete SDK developer guide — start here
├── cp_methods_reference.md        # every cp.py method (get, put, register, helpers)
│
├── ncos-api/                      # NCOS router API reference (see its own README)
│   ├── README.md                  # API overview + common-task index
│   ├── gotchas.md                 # verified surprises — read before trusting a path
│   ├── api-structures.md          # response shapes and patterns
│   ├── dtd-usage.md               # verify field types/requirements via /api/dtd/
│   ├── FEATURES_TO_ENABLE.md      # status paths that are absent until a feature is on
│   ├── client-usage-qos.md        # client usage + QoS specifics
│   ├── explore_status.py          # live explorer: print a real status subtree
│   ├── generate_config_paths.py   # regenerates config/PATHS.md
│   ├── status/                    # read-only status tree (wan, gps, modem, system, …)
│   ├── config/                    # settings tree — 500+ paths in PATHS.md, plus a dtd/ dump
│   ├── control/                   # action endpoints (reboot, ping, gpio, speedtest, …)
│   └── state/                     # app-published status/<app> state notes
│
├── sdk-in-container.md            # run an SDK app inside a container
├── containers-quick-start.md      # containers on the router: getting started
├── containers-advanced-config.md  # advanced container configuration
├── containers-memory-resources.md # tuning container memory
└── containers-usb-audio.md        # USB audio in containers
```

## Where to start

| If you want to… | Read |
|---|---|
| Understand app structure, lifecycle, packaging | [NCOS_SDK_Developer_Guide.md](NCOS_SDK_Developer_Guide.md) |
| Look up a `cp` call (`cp.get`, `cp.put`, `cp.register`, helpers) | [cp_methods_reference.md](cp_methods_reference.md) |
| Find the right router API path and its fields | [ncos-api/README.md](ncos-api/README.md) |
| Avoid a known API pitfall before writing code | [ncos-api/gotchas.md](ncos-api/gotchas.md) |
| Run your app in a container | [sdk-in-container.md](sdk-in-container.md), [containers-quick-start.md](containers-quick-start.md) |

## NCOS API reference (`ncos-api/`)

The API docs mirror the router's own API namespaces, so the folder you want matches the path you
would call:

| Folder | Namespace | Read/write | Example |
|---|---|---|---|
| [`status/`](ncos-api/status/README.md) | `status/…` | read-only | `cp.get('status/wan/devices')` |
| [`config/`](ncos-api/config/README.md) | `config/…` | read/write settings | `cp.put('config/system/…', value)` |
| [`control/`](ncos-api/control/README.md) | `control/…` | trigger actions | `cp.put('control/system/reboot', …)` |
| [`state/`](ncos-api/state/README.md) | `status/<app>` | app-published | your app publishes its own status subtree |

Config paths are broad; the full list lives in [config/PATHS.md](ncos-api/config/PATHS.md), and
`config/dtd/` holds a DTD dump you can use to check a path's exact field types and whether they
are required. The two Python helpers in `ncos-api/` are tools, not docs: `explore_status.py`
prints a live status subtree from your dev router, and `generate_config_paths.py` regenerates
`PATHS.md`.

## Conventions

- **Verify before you code.** API paths and fields are easy to assume wrong. Check a path against
  these docs, the DTD, and a live response before writing code against it — and check
  [gotchas.md](ncos-api/gotchas.md), which collects paths that behave unexpectedly.
- **Status is read-only; config is read/write; control triggers actions.** Reading from `config/`
  or `control/` where you meant `status/` is a common mix-up.
- **Reference, not steering.** These files are documentation you read on demand. The rules the
  agent always follows live in `../.kiro/steering/`, and the build/deploy tool is `../make.py`.
