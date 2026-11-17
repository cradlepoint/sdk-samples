# dsds_wan_verify

Connectivity verification and automatic failover for **Dual SIM Dual Standby (DSDS)** modems,
with a web UI on a port shown in the app log (usually 8000).

<img width="1634" height="923" alt="image" src="https://github.com/user-attachments/assets/b6b7587e-dcee-44f8-b1b8-a88dca6e4854" />
<img width="1634" height="923" alt="image" src="https://github.com/user-attachments/assets/7315c5be-e936-4f26-b402-de33c775fd72" />
<img width="1573" height="846" alt="image" src="https://github.com/user-attachments/assets/098c3bbb-405e-48da-95b6-f91fdfef2d77" />

The app watches the SIM slot currently carrying traffic and, when it fails, switches to the
other slot. Each slot can be checked three ways, and each check is switchable per slot:

- **Ping** — IP Verify ping tests to one or more targets.
- **HTTP** — a GET or HEAD request to a URL you choose.
- **Signal** — a minimum signal threshold below which the slot is considered unusable.

---

## Quick start

1. **Deploy the app.** It starts working immediately on its built-in defaults — ping `8.8.8.8`
   on both slots, with automatic failover on — so review them before leaving it unattended.
2. **Open the web UI.** From a LAN client, go to `http://<router-lan-ip>:<port>`. The port is
   shown in the app log and saved in `dsds_wan_verify_web_port` (usually 8000, or the next free
   port if that is taken; see [Web server port](#web-server-port)). If the page times out, see
   [LAN access](#lan-access). You can also reach it through Remote Connect LAN Manager to
   `127.0.0.1` on the same port.
3. **Set your tests.** On **Connectivity Tests**, pick a slot tab and edit the **Ping Test**
   targets or add an **HTTP Test** URL (use **Test Now** to check a URL before saving).
4. **Set your signal thresholds.** On **Signal Thresholds**, adjust the minimum signal per slot.
5. **Pick your Preferred SIM** on the dashboard. It applies immediately — no save needed.
6. **Watch the dashboard** for live status.

### Default behavior

Out of the box, with nothing configured, the app is already a working failover setup:

| Setting | Default |
|---|---|
| Ping | on, both slots, target `8.8.8.8` |
| Signal threshold | on, both slots: `RSRP -100`, `RSRP_5G -120` |
| Automatic return (failback) | on, SIM 1 only |
| Settle time after a switch | 10s |
| Failback holdoff | 1 hour |
| HTTP | off (no default URL) |

Two things to know before it runs unattended:

- **It will switch SIMs on its own** when the connected slot's tests fail. Each switch costs
  about 30 seconds of downtime.
- Defaults live in code and are **never written to appdata**, so an NCM group config always
  wins. The only value the app writes is the web port it picks on first start (see
  [Web server port](#web-server-port)).

---

## Preferred SIM

The dashboard has one **Preferred SIM** choice (SIM1 or SIM2) that applies the moment you click
it. It controls:

- **Where the app returns to** once a failed slot recovers (if automatic return is on).
- **The tiebreak** — if both slots have weak signal, traffic stays on the preferred SIM instead
  of bouncing between them.

---

## How failover works

Every couple of seconds the app checks the **connected** slot:

| Test | Fails when |
|---|---|
| Ping | targets fail (all by default, or any — your choice) |
| HTTP | wrong status code, timeout, or connection error |
| Signal | a reported metric drops below its threshold for several readings |

Ping and HTTP combine per slot — by default both must pass; you can set it to either. Each test
retries on its own before a failure counts, so a reported failure is already confirmed and acted
on right away.

The ping test is bound to the connected slot's WAN IP (it sets the IP Verify test's `source_ip`),
so the probe is forced out that SIM rather than following the router's default route. On a
public-internet SIM both behave the same, but on a **private APN** (for example a private 5G core
such as EP5G) the router has no default route to a public ping target out that slot, so an unbound
probe never leaves the modem and the test fails even though the link is up. If ping still will not
pass on a private APN, point it at a target reachable *inside* that network, or use the HTTP test,
which is bound the same way.

**IP Verify support.** Ping runs entirely through the router's IP Verify feature, which not every
NCOS model has. At startup the app reads `config/ipverify`; when that comes back `null` the feature
is absent, so the app skips ping tests altogether — it creates no IP Verify objects and reads no
ping results — and logs that ping is disabled. The HTTP and signal tests are unaffected (the app
performs HTTP itself), so a slot still fails over on a failing HTTP test or low signal. On the
dashboard the ping rows read "not run (router does not support IP Verify)". Enable an HTTP test on
each slot if you rely on connectivity failover on such a model.

**Settle time** (default 10s) tells the app to ignore a slot's test results for a short while
right after switching to it. A freshly connected slot legitimately fails tests for a few seconds
while it registers on the carrier, so this is the main guard against the modem flapping back and
forth. Lower it only if you want faster reactions and accept the flapping risk.

**Ping test arming.** The app keeps the ping test disarmed while the modem is switching slots and
for a few seconds after a slot connects, then arms it only on the connected slot. A DSDS slot
reports `connected` a moment before its route is usable, and a ping test left running through the
switch fails on the slot that lost its route - which is why an early-armed test used to flash a
failure and log `retry_fail` right as a slot came up. With the test armed only once the route is
ready, the first result is a real one.

**Failback holdoff** (default 1 hour) prevents one specific flap: a slot with strong signal but a
broken link looks fine from standby, so the app would otherwise return to it, fail, and repeat.
The holdoff is armed in two cases, both of which signal cannot judge from standby:

- The app leaves a slot because its own *connectivity* tests failed.
- Something **outside the app** — NCOS, a reboot, or an admin elsewhere — moves traffic off the
  preferred slot. A bad APN, lost registration, or a carrier-side drop makes NCOS fail the modem
  over on its own, and from standby that slot still reports healthy signal, so without the holdoff
  the app would immediately fail back into the slot the network just dropped and loop.

After the holdoff is armed the app waits this long before returning. If the slot carrying traffic
then fails too, the app returns early rather than sit on a dead link.

When a slot is left because its *connectivity* test failed, its card keeps that failing test
marked in red on the dashboard — "failed — holding off failback for *Nm Ns*" while the holdoff
counts down — so the reason for the switch stays visible instead of reverting to a grey "waiting
for a result". The red mark clears once the holdoff expires or the slot reconnects and produces a
fresh result. A slot with no holdoff (the non-preferred SIM) keeps the red mark until it
reconnects.

**Suspended slots are not switch targets.** A SIM that fails to register — most often a bad APN —
is parked by NCOS on a suspended backoff timer (`suspended (N secs)`) before it returns to
`standby`. The modem accepts a switch request aimed at a suspended slot but never completes it, so
the app will not switch to a slot while it is suspended; it waits for the slot to return to
standby first. If a switch is requested and the modem does not begin switching within a few
seconds (the slot summaries normally change almost immediately), the app treats the switch as
failed, logs it, and retries once the target is switchable again rather than waiting out the full
switch timeout.

**Failed switches say why.** When a switch does not complete, the Event Log entry gives the reason
the target SIM did not come up: the modem's own error (for example `the modem reported "CPPM
failed: no carrier"`), or, when the modem gives none, how far the SIM got (never handed the radio,
handed the radio but never given an IP address) and the last state it was in. If the modem posts
its error only after the switch is over, a follow-up entry adds it. If the modem gives up and goes
back to the original SIM, the app notices and reports the failure then instead of waiting out the
full timeout.

---

## Configuration

> **Manage configuration from the web UI, not by editing SDK appdata directly.** The UI validates
> your input, keeps both configuration pages in sync, and writes the whole config correctly. The
> appdata field documented below is for reference and for NCM group deployment — hand-editing it
> is easy to get wrong.

Settings are stored as JSON in the appdata field **`dsds_wan_verify`**, shaped as
`{"slots": {...}}` — everything is per SIM slot. You normally set these through the web UI; this
table is for reference. Out-of-range values are clamped, not rejected. The app picks up external
changes (NCM push, REST, manual edit, or deletion) within about 10 seconds without a restart.

### Web server port

The web UI port is kept in a separate appdata field, **`dsds_wan_verify_web_port`** (not part of
the `dsds_wan_verify` config JSON), so it can be pushed from an NCM group on its own.

- **Set:** the app uses exactly that port, any number from 1 to 65535. If the port is busy it
  retries for about 10 seconds and never moves to another port.
- **Not set:** on first start the app takes the first free port from 8000 and saves it to
  `dsds_wan_verify_web_port`, so the port stays the same after reboots.
- **Invalid or busy:** if the value is not a number from 1 to 65535, or the port stays busy, the
  app stops and logs why. Fix or delete the field, then start the app.

The startup log shows the port, for example:

```text
Bound port 8001 (discovered, saved to dsds_wan_verify_web_port)
Web server started on port 8001
```

To change the port for one router or a group, set `dsds_wan_verify_web_port` in NCM SDK Data
(device or group) and restart the app. Delete the field and restart to go back to automatic
selection. **The port is read once at startup**, so unlike the per-slot config it is not reloaded
live. Make sure the Zone Firewall forward lets LAN clients reach the app's web port (see
[LAN access](#lan-access)).

| Field | Required | Description |
|---|---|---|
| `dsds_wan_verify_web_port` | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 8000 and saves it here. Delete it to pick a port automatically again. |
| `dsds_wan_verify_port` | No | Deprecated. Older name for the web port, used only when `dsds_wan_verify_web_port` is not set. It used to reject ports below 1024; the new field accepts 1-65535. |

### Per slot (`slots["<port>|<sim>"]`, e.g. `slots["int1|sim1"]`)

| Field | Default | Description |
|---|---|---|
| `priority` | the SIM number | Which slot the app prefers. **Lower = higher priority** (1–99). The dashboard **Preferred SIM** control sets this. |
| `settle_seconds` | `10` | Ignore this slot's test results for this long after switching to it (0–900). |
| `failback_holdoff_seconds` | `3600` | After leaving this slot on a connectivity failure, wait this long before returning (0–86400, `0` = no wait). |
| `test_combine` | `all` | `all` = ping and HTTP must both pass; `any` = either is enough. |
| `ping_enabled` | `true` | Run a ping test on this slot. |
| `ping_targets` | `["8.8.8.8"]` | Up to 8 IPs or hostnames. |
| `ping_fail_mode` | `all` | `all` = fails only when every target fails; `any` = one is enough. |
| `ping_interval` | `10` | Seconds between runs (1–3600). |
| `ping_retry_count` | `2` | Extra attempts before a verdict (0–5). |
| `ping_retry_interval` | `5` | Seconds between retries (5–30). |
| `ping_pkt_per_try` | `1` | ICMP requests per attempt (1–255); the attempt passes if any is answered. |
| `ping_pkt_size` | `36` | Payload bytes (minimum 36). |
| `ping_pkt_timeout` | `10` | Per-packet reply timeout, stored in tenths of a second (1–255); the router counts a reply that arrives after this as a lost packet. The web UI edits this field in milliseconds and converts (so stored `10` shows as `1000` ms). |
| `signal_enabled` | `true` | Use a signal threshold on this slot. |
| `signal_thresholds` | `{"RSRP": -100, "RSRP_5G": -120}` | Metric → minimum value. |
| `signal_fail_threshold` | `5` | Consecutive low readings before acting (1–100). |
| `signal_failback_enabled` | `true` on SIM 1 | Return to this slot when its signal recovers. |
| `http_enabled` | `false` | Run an HTTP test on this slot. |
| `http_url` | `''` | Full URL (`http://` assumed if no scheme). |
| `http_method` | `GET` | `GET` or `HEAD`. |
| `http_timeout` | `2` | Seconds per attempt (1–120). |
| `http_interval` | `30` | Seconds between runs (5–3600). |
| `http_retry_count` | `1` | Extra attempts after a failure (0–10). |
| `http_retry_interval` | `2` | Seconds between attempts (1–60). |
| `http_expect_status` | `[]` | Accepted status codes. Empty = any 2xx or 3xx. |
| `http_verify_tls` | `false` | Verify the TLS certificate. |

Signal metric keys: `DBM`, `RSRP`, `RSRQ`, `SINR`, `RSRP_5G`, `RSRQ_5G`, `SINR_5G`. All are
higher-is-better, so `-85` beats `-110`.

### Example appdata value

```json
{
  "slots": {
    "int1|sim1": {
      "priority": 1,
      "ping_enabled": true, "ping_targets": ["8.8.8.8", "1.1.1.1"],
      "signal_enabled": true,
      "signal_thresholds": {"RSRP": -110, "RSRP_5G": -110},
      "signal_failback_enabled": true,
      "http_enabled": true, "http_method": "HEAD",
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

---

## Web UI

| Page | Contents |
|---|---|
| Dashboard | Status, counters, the **Preferred SIM** selector, manual **Switch SIM Now**, and a card per slot with state, signal, and test results. When a failback holdoff is active it shows a **Failback hold** counter in the status bar, a **Failback hold** badge with the remaining time on the held slot's card, and an explanatory banner — all counting down as the hold expires. |
| Connectivity Tests | One tab per slot: how ping and HTTP combine, settle time, failback holdoff, and the ping/HTTP settings. **Test Now** runs an ad-hoc HTTP check. |
| Signal Thresholds | One tab per slot: the enable and failback toggles, reading count, and the threshold table with live values. |
| Event Log | In-memory log of switches, failures, and config reloads. |

The **?** button in the header shows the full reference documentation. **Save Configuration**
writes the whole config; the **Preferred SIM** selector applies immediately with no save.

### LAN access

If the app is running but LAN clients time out on the app's web port, add a Zone Firewall forward from the
Primary LAN Zone to the Router Zone under **Security → Zone Firewall** (or at
`config/firewall/zone_fwd`).

The UI has no authentication — anyone who can reach the app's web port can change the config and force a
switch. Keep the zone forward scoped to trusted networks.

### JSON API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | Full snapshot. |
| `GET` | `/api/config` | Stored config plus defaults. |
| `GET` | `/api/info` | Router model, serial, MAC, firmware, app version. |
| `POST` | `/api/config` | Save `{"slots": {...}}`. |
| `POST` | `/api/switch` | Manual switch (blocks ~30s). |
| `POST` | `/api/http_test` | Ad-hoc HTTP test from one slot. |
| `POST` | `/api/clear_tests` | Delete every IP Verify object this app created. |

---

## Limitations

- **Requires a DSDS modem.** Without one the app idles and says so; it does not manage non-DSDS
  WAN failover (NCOS WAN rule priorities already do that).
- **A switch costs ~30 seconds of downtime**, so set thresholds you are willing to act on
  repeatedly.
- **The preferred SIM is app-local** — it cannot be read from the WAN profile, since both DSDS
  slots share one WAN rule.
- **Both slots are always monitored.** There is no way to exclude one.
- **Standby-slot connectivity is unknowable** without switching to it; only its signal is
  visible. This is why a connectivity-caused failover uses the failback holdoff.
- **No switching when nothing is connected.** If both slots are down, NCOS drives recovery and
  the app waits.
