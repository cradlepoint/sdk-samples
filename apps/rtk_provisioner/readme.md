# rtk_provisioner

Configures the router's RTK/NTRIP client for an RTK corrections service and
registers the router with that service's account. The corrections **provider
is detected from SDK appdata** - whichever provider's detection field is
present selects it - so one app can serve several services. Today
[Point One Navigation](https://pointonenav.com) ("P1") ships; other providers
can be added without touching the generic core.

This is the generic successor to the `pointonenav` app: the Point One logic now
lives in a provider plugin, and the router-side work (GPS, the
`config/system/rtk` writes, the supervisor loop) is shared by every provider.

## Provider detection

On every poll the app reads `config/system/sdk/appdata` once and looks for each
provider's detection field. The **first** match wins:

| Provider | Detection field | Selected when |
|---|---|---|
| Point One Navigation | `p1_token` | `p1_token` is present and non-empty |

With no detection field present the app parks in its waiting state and names
the fields it is looking for. Keep detection fields distinct across providers
so one set of appdata selects exactly one provider.

## What it does

The app runs a supervisor loop: it re-reads its configuration every 15 seconds,
applies it whenever it differs from what was last applied, and reports RTK
status in between. One pass does this:

1. Reads SDK appdata and detects the provider from its fields.
2. Checks that `config/system/rtk` exists. On a model without RTK support it
   stops there and creates **no** provider resources, so an unsupported router
   never leaves stray billable resources in the account.
3. Asks the provider to register this router and return NTRIP credentials. The
   device label is the router hostname; hardware identity is the router MAC, so
   a rename is tracked in place rather than orphaning the device.
4. Enables GPS if it is off (`config/system/gps/enabled`), writes
   `config/system/rtk/ntrip` (host, port, mountpoint, username, password) in a
   single PUT, then sets `config/system/rtk/enabled` to `true`.
5. Logs `status/rtk` after a short delay so the connection result is visible.

Once provisioned, the loop keeps polling configuration and logs `status/rtk`
every 5 minutes. The app never exits: `package.ini` has `restart = true`, so a
process that exits is relaunched immediately. Every error path stays inside the
loop and retries.

## Live configuration reload

Configuration is a reloadable state, not a startup gate. Nothing here needs an
app restart or a router reboot.

- **Poll interval**: every 15 seconds the app re-reads
  `config/system/sdk/appdata` (one read of that single path) plus
  `config/system/system_id`.
- **Missing configuration keeps the app running.** With no provider detected
  the app logs one waiting line naming the fields it looks for, then repeats it
  at most every 5 minutes. Add a detection field and the app picks it up on the
  next poll.
- **Any consumed field is watched.** Editing, adding, or removing any field the
  active provider reads logs `Configuration changed: <field names> -
  re-applying` and re-runs the flow. Field *names* are logged, never values.
- **Switching providers** (clearing one detection field and setting another's)
  is picked up live and re-provisions against the new provider.
- **A router rename is picked up live.** The device label follows
  `config/system/system_id`, so renaming the router renames the device in place.
- **Retry backoff**: a failed attempt retries after 60 s, then doubles up to a
  900 s ceiling. Any configuration change resets the backoff and retries
  immediately. A model without RTK support retries at the 900 s ceiling instead
  of looping noisily.
- **Clearing the detection field returns the app to waiting and leaves the
  router's RTK/NTRIP config in place.** Corrections keep flowing on the
  credentials already written; the app does not disable RTK as a side effect of
  an appdata edit.
- **A failed appdata read is treated as "unknown", not "cleared".** The app
  logs it, skips the pass, and keeps the configuration it already applied.
- **Secrets are never logged.** Logs show field names and presence only.

## Requirements

- A router model with RTK/NTRIP support (for example an **R2400**). Models
  without RTK support have no `config/system/rtk` key at all. The app checks for
  it before writing anything or touching a provider account, logs the reason,
  and then re-checks quietly at the 900 s backoff ceiling instead of exiting.
- An account and credentials with one of the supported providers.

## Appdata fields

Set these under `config/system/sdk/appdata`.

### Point One Navigation (`p1_token`)

| Field | Required | Default | Description |
|---|---|---|---|
| `p1_token` | **yes** | — | Point One personal access token. Its presence selects this provider. Sent as `Authorization: Bearer <token>`. |
| `p1_caster_host` | no | `truertk.pointonenav.com` | NTRIP caster hostname. |
| `p1_caster_port` | no | `2101` | NTRIP caster port. |
| `p1_mountpoint` | no | `AUTO` | NTRIP mountpoint. `AUTO` lets the caster pick the datum; set a specific one (e.g. `ITRF2014`) to pin it. |
| `p1_license_type` | no | `True RTK` | License type to use. Either a license type UUID, or a substring matched against the license type description. When several descriptions match, the longest term wins. |
| `p1_create_license` | no | `true` | When `false`, the app only reuses an unassigned license from account inventory and never creates (bills) a new one. |
| `p1_license_auto_renewal` | no | `false` | Sets `autoRenewal` on newly created licenses. |
| `p1_replace_stale` | no | `true` | When `false`, an older device holding this hostname is left in place instead of being deleted. Use for fleets where hostnames are not unique. |

Every field is re-read on the 15 second poll interval, so adding, editing, or
clearing any of them takes effect without restarting the app.

The app never writes defaults back to appdata, so NCM group configs are not
overridden.

## Device identity (Point One)

The P1 device **label is the router hostname** (`config/system/system_id`).
Identity is the router **MAC**, stored in a tag, because the hostname can change
at any time:

| Tag | Value | Purpose |
|---|---|---|
| `router_mac` | full MAC, lowercase, no colons (e.g. `0030444e3ae3`) | True hardware identity |
| `sdk_app` | `rtk_provisioner` | Marks devices this app owns |

Resolution is a three-way decision:

1. **A device tagged with this MAC exists** → it is ours. Reuse it. The label is
   updated in place if the router was renamed.
2. **No MAC match, but a device this app created carries this hostname as its
   label** → different hardware in the same deployment slot, so this router is a
   replacement. The old device is unlicensed and deleted (freeing its license
   back to inventory), then ours is created.
3. **Neither** → first run on this router. Create the device.

Safety properties: a same-label device **without** the `sdk_app=rtk_provisioner`
tag is never deleted, and re-running the app is a no-op against the account,
which keeps `restart = true` from churning devices and licenses.

## Config written

```
config/system/gps/enabled = true      # only if currently false
config/system/rtk/ntrip = {
    "host":       "<caster host>",
    "port":       <caster port>,
    "mountpoint": "<mountpoint>",
    "username":   "<ntrip login>",
    "password":   "<ntrip password>"
}
config/system/rtk/enabled = true
```

`username` and `password` are capped at 32 characters and `mountpoint` at 64 by
NCOS; the app validates lengths before writing. The NTRIP struct is written in
one PUT because NCOS validates a config struct as a unit. `format` and
`gga_rate` are left at their existing values.

GPS is required, not optional: the NTRIP client reports its position to the
caster as GGA sentences, so corrections cannot flow without it. GPS is enabled
first; if it cannot be enabled the app stops without writing the NTRIP settings
or enabling RTK. GPS that is already on is left alone.

## Adding a provider

1. Add a module under `providers/` with a `Provider` subclass (see
   `providers/base.py` and `providers/pointone.py` for the contract):
   - set `NAME` and a unique `DETECT_FIELD`
   - implement `required_fields()`, `read_config(snapshot, helpers)`, and
     `provision(config, hostname, mac)` returning an `NtripResult`
2. Append the class to `PROVIDERS` in `providers/__init__.py`.

A provider only does account-side work and returns NTRIP credentials. The core
owns everything on the router (GPS, the `config/system/rtk` writes, retries,
status logging), so a new provider cannot misconfigure the router.

## Project layout

```
apps/rtk_provisioner/
├── rtk_provisioner.py      # generic core: detection, router config, loop
├── providers/
│   ├── __init__.py         # provider registry + detect_provider()
│   ├── base.py             # Provider base class, NtripResult, ProviderError
│   └── pointone.py         # Point One Navigation provider
├── cp.py                   # CP module (generated)
├── package.ini             # metadata (generated)
├── start.sh                # launcher (generated)
└── readme.md
```

## Point One API notes

- Endpoint: `https://graphql.pointonenav.com/graphql`, auth header
  `Authorization: Bearer <personal access token>`.
- `device.services.rtk.ntrip` returns `login` and `password` as real,
  unmasked values.
- `casterUrl` and `mountPoint` can come back as `null`, which is why the caster
  host, port, and mountpoint have defaults. When the API supplies them, the API
  values take precedence over the defaults and over the appdata overrides.
- `DEVICE_FIELDS` in `providers/pointone.py` must keep `tags { key value }`:
  identity lookups re-check tags locally on the devices the queries return, so
  dropping the field makes every lookup miss and the app creates a duplicate of
  a device that already exists.
- List queries are paginated (`offset` / `limit`); pagination keys off
  `totalElements`, as the `last` page flag was unreliable in testing.

## Verifying

```
get config/system/gps/enabled
get config/system/rtk/enabled
get config/system/rtk/ntrip
get status/rtk
get status/rtk/correction_source/state
get status/rtk/corrections/frames_total
```

On the firmware tested (R2400), `status/rtk` reports `enabled`,
`correction_source { type state error }` and
`corrections { frames_total frames_dropped frames_queued }`.
`correction_source/state` reads `stopped` before provisioning and `connected`
once the caster link is up. Older builds reported `ntrip { connected
rtk_quality }` and `rtcm_total` instead; the app logs whichever shape the router
returns.

To check live reload:

1. With no detection field set, the log shows one `Waiting for configuration:`
   line and nothing further for five minutes.
2. Add `p1_token` to `config/system/sdk/appdata`. Within ~15 s the log shows
   `Configuration read: provider Point One Navigation` followed by the
   provisioning flow - and **no** second `Starting rtk_provisioner...` line,
   which is the proof that the app was not restarted.
3. Clear `p1_token`. Within ~15 s the waiting line returns, the router's RTK
   config is left as it is, and again there is no restart.
