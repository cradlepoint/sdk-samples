# dsds_wan_verify

Connectivity verification and automatic failover for **Dual SIM Dual Standby (DSDS)**
modems, with a web UI on port 8000.

Tests per SIM slot, each independently switchable:

- **Ping** — IP Verify ping tests bound to that slot's WAN device, with only the connected
  slot's test armed.
- **HTTP** — GET or HEAD from the app itself, with the socket's source address bound to
  that slot's WAN IP, retried before a failure counts.
- **Signal** — **one threshold per slot**, meaning *the level at which this slot is no longer
  worth using*. Signal works on the **disconnected** slot too, which a DSDS modem keeps
  reporting live, so the same number answers every signal question about that slot.

---

## Quick start

1. Deploy the app. **All three tests are off by default**, so nothing can fail and nothing
   will switch until you enable something.
2. Remote Connect LAN Manager to 127.0.0.1 port 8000 HTTP.  
Or if locally connected open `http://<router-lan-ip>:8000`. If the page times out, see
   [LAN access](#lan-access-requires-a-firewall-zone-forward).
3. On **Connectivity Tests**, pick a slot tab and expand **Ping Test** or **HTTP Test**. Add
   ping targets or enter a URL, then turn that test's toggle on. **Test Now** checks an HTTP
   URL before you save.
4. On **Signal Thresholds**, set one threshold per slot. Set the **secondary** slot's
   threshold **lower** than the preferred slot's — see [The signal threshold](#the-signal-threshold).
5. Pick the **Preferred SIM** on the dashboard. It applies immediately; there is nothing to
   save.
6. Watch the dashboard.

---

## Preferred SIM

The dashboard carries a single **Preferred SIM** choice per modem: SIM1 or SIM2. It applies
the moment you click it — there is no Save — and it settles two things:

- **Where the app returns to.** With *Return to this slot when its signal recovers* enabled on
  the preferred slot, the app moves back to it once its signal comes good again.
- **The tiebreak.** If neither slot is above its signal threshold, there is no better place to
  be, so the app does not switch on signal and traffic stays on (or moves to) the preferred
  SIM. That is what stops it bouncing between two weak slots.

## How failover is decided

Every 2 seconds, for the **connected** slot only:

| Test | Source | Fails when |
|---|---|---|
| Ping | `status/ipverify` | per `ping_fail_mode`: all targets fail (default), or any target fails |
| HTTP | performed by the app | status code not accepted, timeout, or connection error |
| Signal | `status/wan/devices/{uid}/diagnostics` | any reported metric is below its threshold |

Ping and HTTP combine per `test_combine`, which defaults to **both must pass**. An HTTP test
is normally added to catch what ping cannot — a captive portal, broken DNS, or a path that
drops everything except ICMP — so a failing HTTP test counts even while ping succeeds. Set
it to *either* when the endpoint is less reliable than the link.

**Each test confirms its own failures.** Ping retries via IP Verify's `ping_retry_count` /
`ping_retry_interval`, and HTTP retries via `http_retry_count` / `http_retry_interval`, so a
reported failure is already a confirmed one and is acted on immediately. There is no
separate slot-level failure counter. Signal is the exception — it has no retry concept, so
it keeps `signal_fail_threshold` consecutive low readings at the 2 second poll rate.

### The signal threshold

**One threshold set per slot**, meaning *the level at which this slot is no longer worth
using*. The app reads it three ways, so the number only has to be decided once:

| Job | What it does |
|---|---|
| **Leaving** | While this slot is connected and drops below the threshold for `signal_fail_threshold` consecutive readings, the app moves off it. |
| **Arriving** | The app will not fail over *to* this slot on signal alone while it is below its own threshold. |
| **Both weak** | If neither slot is above its threshold there is no better place to be, so the app does not switch on signal and the **Preferred SIM** decides where traffic sits. |
| **Failback** | With `signal_failback_enabled`, the app returns to the preferred slot once it climbs back above its threshold. |

#### What failback does

`signal_failback_enabled` is consulted **only when the slot is a strictly higher priority than
the connected one** — with two slots, only on the preferred SIM. It drives two things:

1. **Proactively** — the connected slot is passing every one of its own tests, but the
   preferred slot has come back above its threshold, so the app returns to it. Possible only
   because a DSDS modem keeps reporting live diagnostics for the standby slot; there is no way
   to ping it.
2. **As a gate** — the connected slot failed and the preferred slot is the candidate, in which
   case it has to clear its threshold first.

> In case 2 the threshold is **overridden when the connected slot has lost connectivity
> outright** — a failing ping/HTTP test, or no connection at all. It stays enforced when the
> current slot merely degraded on signal, where swapping blind could land somewhere worse.

With failback **off**, the app still returns to the preferred slot when the *other* slot fails;
it just will not move on signal recovery alone.

### The failback holdoff

This covers the one flap a signal threshold cannot reach.

A slot with **strong signal but a broken link** fails its connectivity tests, so the app fails
over. From standby, ping and HTTP cannot run on it, and its signal still looks fine — so
failback fires immediately, connectivity fails again, and the modem flaps every
`settle_seconds + ~30s`, indefinitely.

So a failover caused by a **connectivity** failure starts a `failback_holdoff_seconds` timer
(default **1 hour**) on the slot being left, and no proactive failback to it happens until the
timer expires. The dashboard shows the countdown on the slot card and in the status bar.

The timer is **not** set when the app left on low signal or a lost connection: signal is
readable on a standby slot, so the threshold is live evidence that already gates the return
properly, and a timer would only delay a correct decision. Set it to `0` to disable the wait.

**The holdoff only exists on the preferred slot.** It delays a proactive failback *to* a slot,
and the app only fails back to one that outranks its sibling. Leaving the secondary puts
traffic on the preferred SIM, which nothing moves off on its own, so there is no return to
delay — the field is hidden on the secondary slot's **Connectivity Tests** page, and no timer
is armed there. Flip the **Preferred SIM** and it reappears with its stored value intact.

The hold is cleared when it expires, when the slot becomes connected again by any means
(including **Switch SIM Now**, which overrides it), when the slot stops being the preferred
one, or when the slot disappears.

### Timing summary

| Phase | Duration |
|---|---|
| Confirm a ping failure | router-side: `ping_interval + ping_retry_count × ping_retry_interval` |
| Confirm an HTTP failure | `(http_retry_count + 1) × http_timeout + http_retry_count × http_retry_interval` |
| Confirm low signal | `2s × signal_fail_threshold` (default ~6s) |
| Perform the switch | ~30s (measured 29–37s) |
| Settle on the new slot | `settle_seconds` of that slot (default 45s) |
| Wait before failing back after a connectivity failure | `failback_holdoff_seconds` (default 1h) |

There is no general rate limiting. Beyond the connectivity holdoff above, a switch happens
whenever the conditions are met, so the per-test retries, `settle_seconds`, and your choice of
thresholds are what keep the modem from flapping.

Keep the HTTP confirmation budget below `http_interval`, or the next run is already due when
the current one finishes. At the defaults it is `2 × 2 + 1 × 2 = 6s` against a 30s interval.

---

## Why settle time matters

`settle_seconds` ignores a slot's test results for a while after it becomes the connected
slot. It is the single most important guard against ping-ponging, and it earns its keep for
three reasons:

1. **A freshly connected slot legitimately fails tests for a few seconds.** It has just
   registered on a new carrier, and DNS and routes are not up yet. A ping or HTTP test run
   two seconds after connect can fail on a link that is perfectly healthy.
2. **Every switch rewrites IP Verify config**, because the app flips which slot's identity
   is enabled. Any such write restarts the router's poller and blanks *every* test's result
   to `''` for up to `interval + retry_count × retry_interval`. Settle covers that window so
   the app is not making decisions on blank data.
3. **There is no slot-level failure counter.** A confirmed failure acts immediately, so
   without settle time an early transient failure on the slot just switched to would trigger
   another switch straight back — each one costing ~30s of downtime, in a loop.

Settle time and the [failback holdoff](#the-failback-holdoff) guard different flaps. Settle
covers the first seconds on a slot the app has just *arrived* at; the holdoff covers the hour
after the app *left* a slot on a connectivity failure it cannot re-test from standby.

The app also applies settle after an externally driven slot change (NCOS, a reboot, a switch
made elsewhere), using the incoming slot's own value.

Set it to 0 only if you want the app to react the instant a new slot comes up, and accept
the flapping risk. The default 45s comfortably covers the registration and poller-restart
windows measured on the test unit.

## Why tests are gated on connection state

**An IP Verify test bound to a disconnected WAN device does not sit idle — it reports
`pass: false`.** A standby SIM slot is therefore indistinguishable from a real outage, and
WAN binding alone does not gate anything. Verified on an R2400.

So the app disables the standby slot's identity
(`config/identities/ipverify/{index}/enabled = false`), which removes its key from
`status/ipverify` entirely. That is what makes "the test only runs while that SIM is
connected" literally true, rather than merely ignored after the fact. HTTP tests are gated
in app code: a standby slot has no WAN IP to source from.

The signal test is the exception, and deliberately so — it is the only test that works on a
disconnected slot, which is what makes checking the destination possible at all.

The app treats three things as "no result", never as failure:

- the identity is disabled (key absent from `status/ipverify`)
- `pass` is `''`, meaning the router's poller has not reached a verdict yet
- the result predates the slot becoming active, or is older than `3 × http_interval`

---

## Configuration

All settings are stored as JSON in the appdata field **`dsds_wan_verify`**, shaped as
`{"slots": {...}}`. There is no global section — everything is per SIM slot. Defaults are
applied in code and never written back, so an NCM group config is not overridden.

Values outside the ranges below are clamped rather than rejected, so a bad config degrades
instead of stopping the app.

### Per slot (`slots["<port>|<sim>"]`, e.g. `slots["int1|sim1"]`)

| Field | Default | Description |
|---|---|---|
| `priority` | the SIM number | Which slot the app prefers. **Lower number = higher priority** (1–99). The dashboard's **Preferred SIM** control writes `1` and `2`. Defaults to the slot's own SIM number, so SIM 1 outranks SIM 2. Equal on both slots means no preference: no proactive failback, and no both-weak tiebreak. |
| `settle_seconds` | `45` | Ignore this slot's test results for this long after it becomes the connected slot (0–900). See [why settle time matters](#why-settle-time-matters). |
| `failback_holdoff_seconds` | `3600` | After leaving this slot because its **connectivity** tests failed, wait this long before failing back to it (0–86400, `0` = no wait). Not applied to a signal or disconnect failover. Read only on the slot that outranks its sibling, since that is the only slot the app fails back to — ignored on the secondary. See [the failback holdoff](#the-failback-holdoff). |
| `test_combine` | `all` | `all` = ping and HTTP must both pass; `any` = either is enough. |
| `ping_enabled` | `false` | Run an IP Verify ping test on this slot. |
| `ping_targets` | `[]` | Up to 8 IPs or hostnames. |
| `ping_fail_mode` | `all` | `all` = failed only when every target fails; `any` = one is enough. |
| `ping_interval` | `10` | Seconds between runs (1–3600). |
| `ping_retry_count` | `2` | Retries before a verdict (0–5, router limit). |
| `ping_retry_interval` | `5` | Seconds between retries (5–30, router limit). |
| `ping_pkt_per_try` | `1` | Packets per attempt (1–255). |
| `ping_pkt_size` | `36` | Payload bytes (router minimum is 36). |
| `ping_pkt_timeout` | `10` | Per-packet timeout in **tenths of a second** (1–255). |
| `signal_enabled` | `false` | Use a signal threshold on this slot. |
| `signal_thresholds` | `{}` | Metric → value. **One set per slot**, read for leaving, arriving, the both-weak tiebreak, and failback. Set the secondary slot's values **lower** than the preferred slot's. |
| `signal_fail_threshold` | `3` | Consecutive readings before acting, for leaving and for failing back (1–100). |
| `signal_failback_enabled` | `false` | Return to this slot when its signal climbs back above its threshold. Only read when this slot's `priority` is strictly lower than the other's — i.e. on the preferred slot. Overridden when the other slot has no connection at all; deferred by `failback_holdoff_seconds`. |
| `http_enabled` | `false` | Run an HTTP test on this slot. |
| `http_url` | `''` | Full URL. `http://` is assumed when no scheme is given. |
| `http_method` | `GET` | `GET` or `HEAD`. |
| `http_timeout` | `2` | Seconds for connect plus response, per attempt (1–120). |
| `http_interval` | `30` | Seconds between runs (5–3600). |
| `http_retry_count` | `1` | Extra attempts after a failure before reporting it (0–10). |
| `http_retry_interval` | `2` | Seconds between attempts (1–60). |
| `http_expect_status` | `[]` | Accepted status codes. Empty means any 2xx or 3xx. |
| `http_verify_tls` | `false` | Verify the TLS certificate. See note below. |

Threshold metric keys: `DBM`, `RSRP`, `RSRQ`, `SINR`, `RSRP_5G`, `RSRQ_5G`, `SINR_5G`.
All are higher-is-better, so `-85` beats `-110`.

`http_verify_tls` defaults to **off** because this is a reachability probe: a stale CA
bundle or a captive portal would otherwise register as a connectivity failure and trigger a
pointless failover. Turn it on when the endpoint's identity genuinely matters.

### Fixed values, not configurable

| Value | Setting | Why |
|---|---|---|
| Poll interval | 2s | How often results are read. Each test confirms its own failures via its own retries. |
| Automatic failover | always on | Controlled by which tests you enable, not a separate arm. |
| NCM alerts | never sent | The app logs instead, and writes `alert_on_*: false` onto the IP Verify identities it creates so the router does not alert for them either. |
| Rate limiting | none, beyond the holdoff | `signal_fail_threshold`, `settle_seconds` and `failback_holdoff_seconds` are the flap controls. |
| No-slot-connected grace | 20s | Covers the ~1s mid-switch gap where neither slot is connected. |
| Switch timeout | 150s | Generous headroom over the measured 29–37s. |

### Example appdata value

```json
{
  "slots": {
    "int1|sim1": {
      "priority": 1,
      "settle_seconds": 45,
      "failback_holdoff_seconds": 3600,
      "ping_enabled": true, "ping_targets": ["8.8.8.8", "1.1.1.1"],
      "signal_enabled": true,
      "signal_thresholds": {"RSRP": -110, "RSRP_5G": -110},
      "signal_fail_threshold": 3,
      "signal_failback_enabled": true,
      "http_enabled": true, "http_method": "HEAD", "http_timeout": 2,
      "http_url": "http://connectivitycheck.gstatic.com/generate_204",
      "http_expect_status": [204]
    },
    "int1|sim2": {
      "priority": 2,
      "ping_enabled": true, "ping_targets": ["8.8.8.8"],
      "signal_enabled": true,
      "signal_thresholds": {"RSRP": -118, "RSRP_5G": -118}
    }
  }
}
```

Note the shape of that example. The preferred slot (`sim1`) sits at `-110` and has failback
on; the secondary (`sim2`) sits **lower**, at `-118`, and has no failback setting because it is
never a failback target. That gap is what makes the secondary usable when the preferred SIM
goes marginal instead of both breaching together.

Earlier builds split signal thresholds up to three ways (`signal_failover_thresholds`,
`signal_select_thresholds`, `signal_failback_thresholds`, and before those
`signal_failover_below`, `signal_min_to_select`, `signal_failback_above`). A config written
against any of them is migrated on read into `signal_thresholds`, preferring the failover set
since it carries the same meaning, then the failback set, then the floor. `signal_enabled` is
taken from `signal_failover_enabled` when it is absent.

A `slots[...].enabled` field from an earlier build is ignored. Both slots are always
monitored, so there is nothing for it to turn off.

---

## Web UI

| Page | Contents |
|---|---|
| Dashboard | Monitor status, poll/settle/switch counters and any running failback hold, the **Preferred SIM** selector, manual **Switch SIM Now**, and a card per slot with state, signal bars against their thresholds, and test results. |
| Connectivity Tests | One tab per SIM slot, holding how ping and HTTP verdicts combine, the settle time, the failback holdoff, and collapsible **Ping Test** and **HTTP Test** sections. Each collapsed bar summarizes what is configured. **Test Now** runs an ad-hoc HTTP check from that slot. |
| Signal Thresholds | One tab per SIM slot: the single threshold table, the consecutive-reading count, and — on the preferred slot only — **Return to this slot when its signal recovers**. The threshold table shows each metric's live value and marks ones the slot is not reporting. |
| Event Log | In-memory log of switches, failures, and slot changes. |

Both configuration pages stay in sync on the selected slot, and either **Save Configuration**
button writes the whole config. The **Preferred SIM** selector applies immediately and needs no
save; switching it moves the failback option to the other slot's tab, keeping the value stored
against the slot it was set on.

Where a slot reports **none** of the metrics its threshold is set on — a threshold on `RSRP`
while the radio is on 5G SA, say — the dashboard says so rather than showing a verdict. The app
treats "no reading" as a reason not to act in either direction: it will not leave the slot, and
will not fail back to it.

### JSON API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | Full snapshot: slots, metrics, test results, history. |
| `GET` | `/api/config` | Stored config plus defaults and metric metadata. |
| `GET` | `/api/info` | Router model, serial, MAC, firmware, app version. |
| `POST` | `/api/config` | Save `{"slots": {...}}`. |
| `POST` | `/api/switch` | Manual switch. Blocks until complete (~30s). |
| `POST` | `/api/http_test` | Ad-hoc HTTP test from one slot. |
| `POST` | `/api/clear_tests` | Delete every IP Verify object this app created. |

### LAN access requires a firewall zone forward

If the app is running but LAN clients time out on port 8000, the Zone Firewall has no
forward from the Primary LAN Zone to the Router Zone. Add one under
**Security → Zone Firewall**, or at `config/firewall/zone_fwd`.

The UI has no authentication of its own. Anyone who can reach port 8000 can change the
failover configuration and force a SIM switch. Keep the zone forward scoped to trusted
networks.

---

## Router objects this app touches

| Path | Access | Notes |
|---|---|---|
| `status/wan/devices` | read | Slot discovery, state, signal. |
| `status/ipverify` | read | Ping results. |
| `status/system/memory` | read | Memory guard. |
| `config/ipverify/ping` | read/write | Only entries whose identity is named `DSDSWV-*`. |
| `config/identities/ipverify` | read/write | Only entries named `DSDSWV-*`. |
| `config/system/sdk/appdata` | read/write | The `dsds_wan_verify` field only. |
| `control/wan/devices/{uid}/testmode/dsds_switch` | write | Triggers the switch. |

IP Verify objects created by anything else are left alone. **Remove App's IP Verify Tests**
on the Connectivity Tests page deletes only this app's objects; they are recreated on the
next poll for any slot that still has a ping test enabled, so use it after disabling the
tests. Disabling a slot's ping test also removes its objects automatically.

The app does **not** modify `config/wan/rules2`. Both DSDS slots share one WAN rule, and
slot selection is driven by `dsds_switch` rather than by rule priority, so splitting the
rule is unnecessary.

---

## Limitations

- **Requires a DSDS modem.** With no slot reporting `DSDS_ENABLED` / `info/dsds`, the app
  idles and says so. It does not manage non-DSDS WAN failover; NCOS WAN rule priorities
  already do that.
- **The preferred SIM is app-local.** It cannot be read from the WAN profile, because both DSDS
  slots share one WAN rule and one priority value. If you also set WAN rule priorities, they
  govern choice *between physical WANs*, not between the two slots of one modem.
- **Automatic return needs the failback option on the preferred slot.** With it off, or with
  both slots set to the same priority number directly in appdata, the app never moves back on
  its own — it only returns when the slot carrying traffic fails.
- **Both slots are always monitored.** There is no way to exclude one, because a slot the app
  cannot use is a slot it can never fail over to.
- **Signal rules yield to a dead link.** The both-weak tiebreak and the failback threshold are
  both skipped when the connected slot has failed its connectivity tests or lost its
  connection, so no signal rule can keep traffic on a slot that cannot carry it. They only
  constrain a switch the app chose to make on signal alone.
- **Connectivity on the standby slot is unknowable** without switching to it. Signal is the
  only standby-slot evidence available, which is exactly why a connectivity-caused failover
  needs the [failback holdoff](#the-failback-holdoff) rather than a signal rule.
- **The failback holdoff is a timer, not a test.** It cannot know whether the broken link came
  back, only that an hour has passed. After it expires the app returns to the preferred slot
  and re-tests there, at the cost of one more switch if the link is still broken. Raise it on a
  link you expect to stay broken for a long time.
- **A switch costs ~30 seconds of downtime.** The per-test retries, `signal_fail_threshold`,
  `settle_seconds` and `failback_holdoff_seconds` are what prevent flapping, so set thresholds
  you are willing to act on repeatedly.
- **No switching when nothing is connected.** `dsds_switch` must be sent to a connected
  device. If both slots are down, NCOS drives recovery and the app waits.
- **Multiple DSDS modems** (`int1`, `int2`) are each handled independently. Failover never
  moves between physical modems.
- Running the app locally (off-router) cannot perform HTTP tests: binding to the router's
  WAN IP fails with `Can't assign requested address`. Everything else works over REST.

---

## Local development

```bash
# From the repo's apps/ directory, so cp.py can find ../sdk_settings.ini
.venv/bin/python3 dsds_wan_verify/dsds_wan_verify.py
```

The web UI then binds to **your** machine's port 8000 while reading and writing the dev
router over REST. HTTP tests fail as noted above; ping tests, discovery, config, and
switching all work.

## Deploy

```bash
.venv/bin/python3 make.py deploy dsds_wan_verify   # Mac/Linux
.venv\Scripts\python make.py deploy dsds_wan_verify  # Windows
```
