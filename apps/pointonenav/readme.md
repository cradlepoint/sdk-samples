# pointonenav

Configures the router's RTK/NTRIP client for the [Point One Navigation](https://pointonenav.com)
("P1") corrections service, using the P1 GraphQL API to register the router as a
licensed P1 device.

## What it does

The app runs a supervisor loop: it re-reads its configuration every 15 seconds,
applies it whenever it differs from what was last applied, and reports RTK
status in between. One pass does this:

1. Reads the P1 personal access token from SDK appdata field `p1_token`.
2. Resolves this router's P1 device (see **Device identity** below). Creates one
   only when this router has none, and deletes an older device only when it is a
   genuine hardware replacement.
3. Attaches a license unless the device already has one. An unassigned license
   already in the account is reused when available; a new license is only
   created as a last resort.
4. Reads the device back and collects the NTRIP credentials.
5. Enables GPS if it is off (`config/system/gps/enabled`), writes
   `config/system/rtk/ntrip` (host, port, mountpoint, username, password) in a
   single PUT, then sets `config/system/rtk/enabled` to `true`.
6. Logs `status/rtk` after a short delay so the connection result is visible.

Before step 2 the app checks that `config/system/rtk` exists. On a model without
RTK support it stops there and creates **no** Point One device or license, so an
unsupported router never leaves stray billable resources in the account.

Once provisioned, the loop keeps polling configuration and logs `status/rtk`
every 5 minutes. The app never exits: `package.ini` has `restart = true`, so a
process that exits is relaunched immediately, which would spin the provisioning
flow in a loop. Every error path stays inside the loop and retries.

## Live configuration reload

Configuration is a reloadable state, not a startup gate. Nothing here needs an
app restart or a router reboot.

- **Poll interval**: every 15 seconds the app re-reads
  `config/system/sdk/appdata` (one read of that single path, not one per field)
  plus `config/system/system_id`.
- **Missing configuration keeps the app running.** With `p1_token` unset the app
  logs one waiting line naming the missing field, then repeats it at most every
  5 minutes. Add the token and the app picks it up on the next poll.
- **Any consumed field is watched, not just the token.** Editing, adding, or
  removing any field in the table below logs
  `Configuration changed: <field names> - re-applying` and re-runs the
  provisioning flow. Field *names* are logged, never values.
- **A router rename is picked up live.** The P1 device label follows
  `config/system/system_id`, so renaming the router renames the device in place.
- **Retry backoff**: a failed provisioning attempt retries after 60 s, then
  doubles up to a 900 s ceiling. Any configuration change resets the backoff and
  retries immediately. A model without RTK support retries at the 900 s ceiling
  instead of looping noisily.
- **Changing the token re-provisions under the new token** and does not touch
  the old account. If the new token belongs to a *different* P1 account, the
  router has no device there, so the app will create one and attach a license —
  reusing an unassigned license from that account's inventory if one exists, and
  otherwise creating (billing) a new one unless `p1_create_license` is `false`.
- **Clearing `p1_token` returns the app to waiting and leaves the router's
  RTK/NTRIP config in place.** Corrections keep flowing on the credentials
  already written; the app does not disable RTK as a side effect of an appdata
  edit. Set the token again (or disable RTK yourself) to change that.
- **A failed appdata read is treated as "unknown", not "cleared".** The app logs
  it, skips the pass, and keeps the configuration it already applied.
- **The token is never logged.** Logs show presence only, as `<unset>` or a
  masked prefix like `eyJh... (250 chars)`.

## Device identity

The P1 device **label is the router hostname** (`config/system/system_id`) —
readable in the Point One console. Identity, however, is the router **MAC**,
stored in a tag, because the hostname can be changed at any time:

| Tag | Value | Purpose |
|---|---|---|
| `router_mac` | full MAC, lowercase, no colons (e.g. `0030444e3ae3`) | True hardware identity |
| `sdk_app` | `pointonenav` | Marks devices this app owns |

Resolution is a three-way decision:

1. **A device tagged with this MAC exists** → it is ours. Reuse it. Nothing is
   created, nothing is deleted. If the router was renamed, the label is updated
   in place.
2. **No MAC match, but a device *this app created* carries this hostname as its
   label** → different hardware in the same deployment slot, so this router is a
   replacement. The old device is unlicensed and deleted (freeing its license
   back to inventory), then ours is created.
3. **Neither** → first run on this router. Create the device.

Because identity is a tag and not the label, renaming the router updates the
label in place rather than orphaning the device and its license.

Two safety properties:

- A same-label device **without** the `sdk_app=pointonenav` tag is never
  deleted — devices added by hand or by other tooling are left alone, and a
  warning is logged.
- Re-running the app is a no-op against the Point One account. This is what
  keeps the router's `restart = true` relaunch behavior from churning devices
  and licenses.

Case 2 assumes a hostname identifies one deployment slot, which is the normal
expectation for a router fleet. If two *live* routers ever did share a hostname,
each would see the other as replaced hardware and they would take the slot from
one another on every restart — and because each new device gets fresh NTRIP
credentials, the router that loses the slot keeps using credentials for a
deleted device and its corrections stop. Set `p1_replace_stale=false` to opt out
of the deletion in that case.

## Requirements

- A router model with RTK/NTRIP support (for example an **R2400**). Models
  without RTK support have no `config/system/rtk` key at all. The app checks for
  it before writing anything or touching the P1 account, logs the reason, and
  then re-checks quietly at the 900 s backoff ceiling instead of exiting.
- A Point One account and a personal access token.

## Appdata fields

Set these under `config/system/sdk/appdata`.

| Field | Required | Default | Description |
|---|---|---|---|
| `p1_token` | **yes** | — | Point One personal access token. Sent as `Authorization: Bearer <token>`. |
| `p1_caster_host` | no | `truertk.pointonenav.com` | NTRIP caster hostname. |
| `p1_caster_port` | no | `2101` | NTRIP caster port. |
| `p1_mountpoint` | no | `AUTO` | NTRIP mountpoint. `AUTO` lets the caster pick the datum; set a specific one (e.g. `ITRF2014`) to pin it. |
| `p1_license_type` | no | `True RTK` | License type to use. Either a license type UUID, or a substring matched against the license type description. When several descriptions match, the longest term wins. |
| `p1_create_license` | no | `true` | When `false`, the app only reuses an unassigned license from account inventory and never creates (bills) a new one. |
| `p1_license_auto_renewal` | no | `false` | Sets `autoRenewal` on newly created licenses. |
| `p1_replace_stale` | no | `true` | When `false`, an older device holding this hostname is left in place instead of being deleted. Use for fleets where hostnames are not unique. |

Every field is re-read on the 15 second poll interval, so adding, editing, or
clearing any of them takes effect without restarting the app — see **Live
configuration reload** above.

The app never writes defaults back to appdata, so NCM group configs are not
overridden.

## Point One API notes

- Endpoint: `https://graphql.pointonenav.com/graphql`, auth header
  `Authorization: Bearer <personal access token>`.
- `device.services.rtk.ntrip` returns `login` and `password` as **real,
  unmasked values**.
- `casterUrl` and `mountPoint` can come back as `null`, which is why the caster
  host, port, and mountpoint have defaults in this app. When the API does supply
  them, the API values take precedence over the defaults and over the appdata
  overrides. Observed on a licensed device: `casterUrl` =
  `truertk.pointonenav.com` and `mountPoint` = `AUTO`, so `p1_caster_host`,
  `p1_caster_port` and `p1_mountpoint` have no effect once the device is
  licensed — they only matter while the API returns `null`.
- Operations used: `myDevices` (filtered by tag and by label), `device`,
  `createDevice`, `updateDevice`, `deleteDevices`, `setDeviceTag`, `licenses`
  (filtered by device), `licenseTypes`, `applyLicenseToDevice`,
  `removeLicenseFromDevice`, `createLicensesForDevices`.
- `myDevices(filter: {tag: {key: ..., value: {eq: ...}}})` does exact
  server-side tag matching. Tags must be requested explicitly in the selection
  set (`tags { key value }`) or they come back **absent, not empty** — the
  standalone `deviceTags(deviceId:)` query returned `null` in testing, so read
  tags inline off the device instead. `DEVICE_FIELDS` in `pointonenav.py` must
  keep `tags { key value }`: `find_devices_by_tag()` and `resolve_device()`
  re-check tags locally on the devices those queries return, so dropping the
  field makes every identity lookup miss and the app creates a duplicate of a
  device that already exists.
- List queries are paginated (`offset` / `limit`). The `last` page flag was
  unreliable in testing, so pagination keys off `totalElements`.

## Config written

```
config/system/gps/enabled = true      # only if currently false
config/system/rtk/ntrip = {
    "host":       "truertk.pointonenav.com",
    "port":       2101,
    "mountpoint": "AUTO",
    "username":   "<P1 ntrip login>",
    "password":   "<P1 ntrip password>"
}
config/system/rtk/enabled = true
```

`username` and `password` are capped at 32 characters and `mountpoint` at 64 by
NCOS; the app validates lengths before writing. The NTRIP struct is written in
one PUT because NCOS validates a config struct as a unit.

`format` and `gga_rate` are left at their existing values — a partial dict PUT
to a config struct merges rather than replaces.

GPS is required, not optional: the NTRIP client reports its position to the
caster as GGA sentences (that is what `gga_rate` controls), so corrections
cannot flow without it. GPS is enabled first, and if it cannot be enabled the
app stops without writing the NTRIP settings or enabling RTK. GPS that is
already on is left alone rather than rewritten.

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
once the caster link is up, and `corrections/frames_total` climbs while
corrections flow. Older builds reported `ntrip { connected rtk_quality }` and
`rtcm_total` instead; the app logs whichever shape the router returns.

To check live reload:

1. With `p1_token` unset, the log shows one `Waiting for configuration:` line
   naming `p1_token` and nothing further for five minutes.
2. Add `p1_token` to `config/system/sdk/appdata`. Within ~15 s the log shows
   `Configuration changed: token - re-applying` followed by the provisioning
   flow — and **no** second `Starting pointonenav...` line, which is the proof
   that the app was not restarted.
3. Clear or delete `p1_token`. Within ~15 s the waiting line returns, the
   router's RTK config is left as it is, and again there is no restart.
