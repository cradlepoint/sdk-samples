# AutoInstall_Web

AutoInstall – Detects SIMs, speedtests each, collects diagnostics, picks fastest. Default: reprioritizes WAN by download speed. With group_by_sim/carrier: moves router to matching NCM group. Optionally enforces min_speed, sends alerts, and updates NCM custom fields.

<img width="1162" height="1034" alt="image" src="https://github.com/user-attachments/assets/a9353b53-d62c-434d-943c-98338d7c91b5" />

## What It Does

1. Detects SIMs per appdata `sims`: `all` (default), `local`, or `captive`
2. Runs a speed test on each SIM (with retries)
3. Optionally enforces a minimum download speed (**min_speed**) – stops with error if no SIM meets it
4. Collects modem diagnostics (ICCID, carrier, signal, etc.)
5. Picks the SIM with the fastest download
6. **Default:** Reprioritizes WAN profiles by download speed – fastest SIM gets highest priority. If multiple SIMs share the same profile, duplicates the profile per SIM with `trigger_string` and `trigger_name` for port/sim.
7. **When group_by_sim or group_by_carrier is set:** Only moves the router to an NCM group that matches that SIM (by carrier name if `group_by_carrier`, or by SIM slot if `group_by_sim`); does not change WAN config.
8. Optionally sends an alert and updates NCM custom1/custom2 with a results summary

## Accessing the App

- Open **http://&lt;router-ip&gt;:&lt;port&gt;/** in a browser (default port 8000; set **AutoInstall_Web_port** to override)
- Enter the installer password to start (see Appdata below), or set **autostart** to begin automatically without user input
- The page shows progress, a short log, and a **Download Logs** button (available when the run finishes or fails)
- Mobile-friendly layout with dark mode toggle

## Appdata (Configuration)

Set these in the router UI under **System > SDK Data** (or in NCM under the device's SDK app configuration):

| Field | Purpose |
|-------|---------|
| **installer_password** | Password to start the install. If blank, the router serial number is used. Case-insensitive. |
| **logo** | Base64-encoded image (or full `data:image/...;base64,...` URL) to display instead of the SIM card icon next to the panel title. |
| **logo_dark** | Optional dark-mode logo. If set, used in night mode instead of `logo`. If not set, the regular logo is CSS-inverted in dark mode. |
| **title** | Panel title. Default: `AutoInstall`. |
| **text** | Intro text shown above the signal meter. Default: `Enter password to start auto-install process.` |
| **autostart** | If set (any value), the auto-install process starts automatically on app launch — but only if **results** appdata does not exist. This prevents re-running on every reboot. Delete **results** to re-run. |
| **results** | Written automatically on successful completion. One-line parseable string: `timestamp \| port sim carrier ICCID=X dl:Xmbps ul:Xmbps score:X \| ...` sorted by download speed. Delete this field (via NCM API or router UI) to allow autostart to run again. |
| **sims** | Which SIMs to test: `all` (default), `local` (remote/product_name not populated), or `captive` (remote/product_name populated). Case-insensitive. |
| **min_speed** | Minimum download speed (Mbps). If no SIM meets this, the process stops with an error. Default: no minimum. |
| **group_keyword** | Word that must appear in the NCM group name. Default: `prod`. |
| **group_by_sim** | If set (any value), enables **group mode**: only move router to NCM group (no WAN reprioritization). Groups are matched by **SIM slot**. |
| **group_by_carrier** | If set (any value), enables **group mode**: only move router to NCM group (no WAN reprioritization). Groups are matched by carrier name. |
| **diagnostics** | Comma-separated list of modem fields to log. Default: `DBM,SINR,RSRP,RSRQ,RFBAND,SRVC_TYPE,SRVC_TYPE_DETAILS`. |
| **AutoInstall_Web_port** | Web server port (1–65535). Default: 8000. Case-insensitive. |
| **disable_alerts** | If set (any value), the app does not send the results alert. |
| **custom1** | If set (any value), the app writes a results summary to the NCM device custom1 field. |
| **custom2** | If set (any value), the app writes a results summary to the NCM device custom2 field. |
| **results_field** | Optional NCOS config path to write results to (e.g. `config/system/desc` or `config/system/asset_id`). Truncated to 1023 chars. |

## UI

- Single panel layout: logo on left, title centered, dark mode toggle on right
- **logo** / **logo_dark**: Custom logo instead of SIM icon; **logo_dark** for night mode (otherwise logo is inverted)
- **title**: Customize panel heading
- **Signal meter**: Replaces intro text. Shows DISCONNECTED when no SIM is connected, or 4G/5G plus a horizontal meter (red→green) based on RSRP/RSRQ or RSRP_5G/RSRQ_5G from modem diagnostics. Auto-refreshes every 3 seconds. Metrics (e.g. RSRP_5G: -87 | RSRQ_5G: -5) shown below the meter.
- **Connect**: Sets the first SIM’s `def_conn_state` to always on.
- **Switch SIMs**: Cycles to the next SIM in the list.
- **Start AutoInstall**: Validates password and starts the auto-install process.
- Dark mode persists in `localStorage`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/signal` | GET | Returns signal diagnostics for the connected SIM. Used by the signal meter. `connected`, `label` (4G/5G), `rsrp`, `rsrq`, `rsrp_key`, `rsrq_key`. If disconnected: `disconnected: true`. |
| `/connect` | POST | Sets the first SIM’s WAN rule `def_conn_state` to always on. |
| `/switch_sims` | POST | Switches to the next SIM in the list (cycles through available SIMs). |

## Default: WAN Reprioritization

When neither **group_by_sim** nor **group_by_carrier** is set:
- The app reprioritizes WAN profiles by download speed.
- Fastest SIM gets the lowest priority number (highest WAN priority).
- If multiple SIMs share the same profile (`_id_`), the app duplicates the profile per SIM with:
  - `trigger_string` matching port and sim (e.g. `type|is|mdm%sim|is|sim1%port|is|int1`)
  - `trigger_name` in "carrier port sim" format (e.g. `T-Mobile int1 sim1`)
- Per-SIM rules created during the run are automatically cleaned up afterward — no orphan rules are left behind on repeated runs.
- If a per-SIM rule already exists from a previous run, it is reused instead of creating a duplicate.
- Priorities are assigned starting from the lowest existing priority: fastest gets base, next gets base+0.1, etc.
- If two SIMs report the same rule `_id_` (e.g. router hasn't reconciled new per-SIM rules yet), the app resolves each to its per-SIM rule via `trigger_string` lookup before setting priorities.
- **No NCM API keys required** for reprioritization-only mode.

## Group Mode (group_by_sim or group_by_carrier)

When **group_by_sim** or **group_by_carrier** is set:
- The app only moves the router to an NCM group; it does **not** change WAN config.
- **group_by_carrier:** Match by carrier name. Group name must contain **group_keyword** and carrier (e.g. `prod_ATT`, `prod_Verizon`).
- **group_by_sim:** Match by SIM slot. Group name must contain **group_keyword** and slot (e.g. `prod_SIM1`, `prod_SIM2`).
  - On dual-modem routers, the app prefers groups that also contain the port name (e.g. `prod_Internal_SIM1`, `prod_MC400_SIM1`) to disambiguate SIM1 on modem 1 from SIM1 on modem 2. Falls back to slot-only matching if no port-specific group exists.
- Carrier names are normalized (e.g. VZW → Verizon, AT&T → ATT).
- **NCM API keys required** when in group mode.

## Dual-Modem Support

The app fully supports routers with two modems (e.g. internal + MC400), each with two SIM slots (4 SIMs total):

- **SIM discovery** iterates all `mdm-*` devices, picking up SIMs across all modems.
- **Per-SIM WAN rules** are created when SIMs share a profile, and cleaned up after each run.
- **SIM switching** disables other profiles and only re-enables them after the target SIM is confirmed connected, preventing modems from competing.
- **WAN reprioritization** resolves shared rule IDs to per-SIM rules so each SIM gets its own priority.
- **Group matching** (group_by_sim) disambiguates by port name on dual-modem routers (e.g. `prod_Internal_SIM1` vs `prod_MC400_SIM1`).

## Re-running AutoInstall

The manual **Start AutoInstall** button always works regardless of results state.

When using **autostart**, the app checks for the **results** appdata field on boot:
- If **results** exists: autostart is skipped (already ran successfully).
- If **results** does not exist: autostart runs immediately.

To re-run via automation, delete the **results** appdata field from the device config via NCM API.

## Requirements

- At least 2 SIMs are present (filtered by appdata `sims`: `all`, `local`, or `captive`).
- WAN is available.
- **NCM API keys** (Certificate Management) are required only when:
  - **group_by_sim** or **group_by_carrier** is set (moving to group), or
  - **custom1** or **custom2** is set (writing to NCM custom fields).
- When in group mode: NCM has groups whose names match your **group_keyword** and either carrier or SIM slot.

## When It Stops or Fails

The app will stop and show an error if:

- Fewer than 2 SIMs are found
- Every speedtest attempt fails for a SIM (3 tries per SIM)
- **min_speed** is set and no SIM meets the minimum download speed
- In **group mode**: no NCM group matches (keyword + carrier or keyword + slot)
- In **group mode**: moving the router to the group fails

On error, the button shows **Auto-Install Failed! Restart** and the log file can be downloaded.

## Troubleshooting

| Message or issue | What to check |
|------------------|---------------|
| Fewer than 2 SIMs found | At least 2 SIMs required. If sims=captive, ensure remote/product_name is populated for 2+ SIMs. If sims=local, ensure 2+ SIMs have no remote/product_name. |
| Failed to test SIM after all retries | WAN, SIM activation, and coverage. |
| Missing NCM API keys | Configure API keys in Certificate Management. Required only when group_by_sim, group_by_carrier, custom1, or custom2 is set. |
| Failed to get NCM groups | Router connected to NCM; API keys valid. |
| No SIM meets minimum speed XMbps | Remove **min_speed** appdata or improve coverage/activation. |
| No matching group for SIM: X | Create an NCM group whose name contains both group_keyword and SIM1 or SIM2 (group_by_sim mode). |
| No matching group for carrier: X | Create an NCM group whose name contains both group_keyword and the carrier name. |
| Using serial number as password | Set **installer_password** in appdata to use a custom password. |

## Logs

- Filename pattern: `AutoInstall_{system_id}_{timestamp}.txt`
- Contains version, system ID, diagnostics, speedtest results, and timestamps
- Can be downloaded via **Download Logs** on the page when the run completes or errors
