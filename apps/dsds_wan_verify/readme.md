# dsds_wan_verify

Connectivity verification and automatic failover for **Dual SIM Dual Standby (DSDS)** modems,
with a web UI on port 8000.

<img width="1634" height="923" alt="image" src="https://github.com/user-attachments/assets/b6b7587e-dcee-44f8-b1b8-a88dca6e4854" />
<img width="1634" height="923" alt="image" src="https://github.com/user-attachments/assets/7315c5be-e936-4f26-b402-de33c775fd72" />
<img width="1634" height="923" alt="image" src="https://github.com/user-attachments/assets/91ea9fad-41fc-4fd9-bc28-f6e3aa7ef3d4" />

The app watches the SIM slot currently carrying traffic and, when it fails, switches to the
other slot. Each slot can be checked three ways, and each check is switchable per slot:

- **Ping** — IP Verify ping tests to one or more targets.
- **HTTP** — a GET or HEAD request to a URL you choose.
- **Signal** — a minimum signal threshold below which the slot is considered unusable.

---

## Quick start

1. **Deploy the app.** It starts working immediately on its built-in defaults — ping `8.8.8.8`
   on both slots, with automatic failover on — so review them before leaving it unattended.
2. **Open the web UI.** From a LAN client, go to `http://<router-lan-ip>:8000`. If the page
   times out, see [LAN access](#lan-access). You can also reach it through Remote Connect LAN
   Manager to `127.0.0.1` port 8000.
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
| Settle time after a switch | 20s |
| Failback holdoff | 1 hour |
| HTTP | off (no default URL) |

Two things to know before it runs unattended:

- **It will switch SIMs on its own** when the connected slot's tests fail. Each switch costs
  about 30 seconds of downtime.
- Defaults live in code and are **never written to appdata**, so an NCM group config always
  wins.

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

**Settle time** (default 20s) tells the app to ignore a slot's test results for a short while
right after switching to it. A freshly connected slot legitimately fails tests for a few seconds
while it registers on the carrier, so this is the main guard against the modem flapping back and
forth. Lower it only if you want faster reactions and accept the flapping risk.

**Failback holdoff** (default 1 hour) prevents one specific flap: a slot with strong signal but a
broken link looks fine from standby, so the app would otherwise return to it, fail, and repeat.
After the app leaves a slot because its *connectivity* tests failed, it waits this long before
returning. If the slot carrying traffic then fails too, the app returns early rather than sit on
a dead link.

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

### Per slot (`slots["<port>|<sim>"]`, e.g. `slots["int1|sim1"]`)

| Field | Default | Description |
|---|---|---|
| `priority` | the SIM number | Which slot the app prefers. **Lower = higher priority** (1–99). The dashboard **Preferred SIM** control sets this. |
| `settle_seconds` | `20` | Ignore this slot's test results for this long after switching to it (0–900). |
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
| `ping_pkt_timeout` | `10` | Per-packet timeout in tenths of a second (1–255). |
| `signal_enabled` | `true` | Use a signal threshold on this slot. |
| `signal_thresholds` | `{"RSRP": -100, "RSRP_5G": -120}` | Metric → minimum value. |
| `signal_fail_threshold` | `3` | Consecutive low readings before acting (1–100). |
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
| Dashboard | Status, counters, the **Preferred SIM** selector, manual **Switch SIM Now**, and a card per slot with state, signal, and test results. |
| Connectivity Tests | One tab per slot: how ping and HTTP combine, settle time, failback holdoff, and the ping/HTTP settings. **Test Now** runs an ad-hoc HTTP check. |
| Signal Thresholds | One tab per slot: the enable and failback toggles, reading count, and the threshold table with live values. |
| Event Log | In-memory log of switches, failures, and config reloads. |

The **?** button in the header shows the full reference documentation. **Save Configuration**
writes the whole config; the **Preferred SIM** selector applies immediately with no save.

### LAN access

If the app is running but LAN clients time out on port 8000, add a Zone Firewall forward from the
Primary LAN Zone to the Router Zone under **Security → Zone Firewall** (or at
`config/firewall/zone_fwd`).

The UI has no authentication — anyone who can reach port 8000 can change the config and force a
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

---

## Deploy

```bash
.venv/bin/python3 make.py deploy dsds_wan_verify     # Mac/Linux
.venv\Scripts\python make.py deploy dsds_wan_verify  # Windows
```

## Local development

```bash
# From the repo's apps/ directory, so cp.py can find ../sdk_settings.ini
.venv/bin/python3 dsds_wan_verify/dsds_wan_verify.py
```

The web UI binds to your machine's port 8000 while reading and writing the dev router over REST.
HTTP tests fail locally; ping, discovery, config, and switching all work.
