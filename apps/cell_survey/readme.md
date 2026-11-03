<img width="1127" height="835" alt="image" src="https://github.com/user-attachments/assets/110d53e7-54c8-4ae0-9032-7ffd673c2c4c" />
<img width="1127" height="734" alt="image" src="https://github.com/user-attachments/assets/3a012a10-a54f-4c58-a208-8d0f01923c1e" />
<img width="1127" height="527" alt="image" src="https://github.com/user-attachments/assets/b956e369-101a-43d7-a4d9-8cc4342ffd74" />


Scan the cellular networks around your router, see which carriers are in range
and how strong each one is, and optionally lock your modem to the carrier you
want. Everything happens in a simple web page served by the router.

## What you can do with it

- **See your modem's status at a glance** — carrier, network type (5G or LTE),
  band, APN, SIM (ICCID), and signal strength, with an easy-to-read quality
  label on the main signal reading.
- **Run a survey** to discover every nearby cell tower, grouped by carrier and
  country and sorted strongest signal first.
- **Export the results** to a spreadsheet-friendly CSV file.
- **Lock onto a carrier** so the modem uses only that network, and switch back
  to automatic selection whenever you want.
- **Activate an eSIM profile** for a carrier, if your modem is eSIM-capable and
  already has an operational profile installed for that network.
- **Schedule surveys** to run automatically on router startup and/or on a
  repeating schedule, and optionally act on the strongest carrier afterwards.
- **Keep a history** of every completed survey as a downloadable, timestamped
  CSV.

## Pages

A sidebar on the left switches between three pages:

- **Run Survey** (default) — the live modem status and the manual survey
  described below.
- **Schedule** — set up automatic surveys on startup and/or on a schedule.
- **History** — browse and download the CSVs saved from completed surveys.

## Opening the app

The app runs on the router and serves its web page on **port 8000** by default.

From a device connected to the router, open a browser to:

```
http://<router-LAN-IP>:8000
```

For example `http://192.168.0.1:8000`.

If the page won't load, the router's firewall may be blocking the port. Make
sure traffic from the LAN is allowed to reach the router on the port the app is
using (in the router UI under **Security > Zone Firewall**, forward the Primary
LAN Zone to the Router Zone for that port).

## Configuration (optional SDK appdata)

These fields are optional. Set them in the router config under
**System > SDK Data** (`config/system/sdk/appdata`). When unset, the app uses
its built-in default.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `cell_survey_port` | No | `8000` | TCP port the web server listens on. Use this to avoid a conflict with another app already using port 8000 (e.g. `8001`). Must be 1–65535. |
| `cell_survey_schedule` | No | _(unset)_ | JSON holding the startup/schedule settings. This is written by the **Schedule** page in the app — you normally don't edit it by hand, but it can be pushed from an NCM group config to apply the same schedule to a fleet. Shape: `{"startup_enabled":bool,"startup_action":"none\|lock\|esim","schedule_enabled":bool,"schedule_cron":"*/30 * * * *","schedule_action":"none\|lock\|esim"}`. |

After changing `cell_survey_port`, open the app on the new port
(`http://<router-LAN-IP>:<port>`) and make sure the firewall forwards the LAN
Zone to the Router Zone for that port.

## Using it

1. **Pick a modem.** If your router has more than one modem, choose it from the
   **Modem** dropdown. The built-in modem is selected for you by default. Use
   **Refresh** if you just inserted a SIM or the list looks out of date.
2. **Check the status tiles** to confirm the modem is **Connected** and see its
   current carrier and signal.
3. **Click Run Survey.** A "Scanning..." message with a timer appears while the
   scan runs. Most modems finish in under a minute; a 5G Standalone connection
   can take a couple of minutes.
4. **Review the results.** When the survey finishes, the current-connection
   tiles collapse to a one-line summary so the results stand out; click
   **Current connection** to expand them again. Carriers are listed strongest
   first and expanded by default. Each carrier lists its individual cells with
   band, channel, and signal details. Click a carrier's header to collapse it.
5. **Export CSV** (top of the results) downloads every detected cell as a
   timestamped file you can open in Excel or Google Sheets.

## Locking onto a carrier

To force the modem to use a specific carrier, click **Lock Carrier PLMN** on
that carrier, then confirm. The modem re-registers on that network, so the data
connection may drop for a few seconds.

A yellow banner shows which carrier is locked. To go back to normal, click
**Restore Automatic** in that banner and the modem returns to picking a network
on its own.

## Activating an eSIM profile

If your modem is eSIM-capable (an eUICC module such as the Internal 5GF-NA
eSIM), the app reads the profiles already installed on it. When a surveyed
carrier matches one of your **operational** eSIM profiles, an **Activate eSIM
Profile** button appears next to **Lock Carrier PLMN** for that carrier.

- Click **Activate eSIM Profile** and confirm to enable that profile. The modem
  switches to it, re-registers on the carrier, and may briefly drop the
  connection (and can reset if the profile needs different modem firmware).
- A carrier whose profile is already the active one shows an **eSIM active**
  badge instead of a button.
- Only operational profiles are offered; test/provisioning profiles are not.
- Modems without eSIM support simply don't show any eSIM controls.

## Scheduling surveys

Open the **Schedule** page in the sidebar to have the app run surveys on its
own. There are two independent triggers, and you can enable either or both:

- **Run Survey on Startup** — runs one survey a short time after the router
  boots and the modem connects.
- **Run Survey on Schedule** — repeats on a schedule you choose. Pick a quick
  preset (every 15 minutes, hourly, daily at 6am, and so on), use the builder
  to assemble a simple recurrence, or enter a custom cron expression. Schedule
  times are in the router's time (UTC). The current cron expression is shown
  under the builder.

For each trigger you choose what the app does with the surveyed carriers
**after** the scan — the **After the survey** dropdown:

- **Do not select carrier** — just save the results to History and change
  nothing (default).
- **Lock best carrier PLMN** — lock the modem to the strongest surveyed
  carrier (same as clicking Lock Carrier PLMN by hand).
- **Activate best carrier eSIM** — activate the eSIM profile of the
  highest-ranking carrier that has an operational profile installed on the
  modem. The app walks carriers strongest-first, so if the strongest carrier
  has no matching profile it moves on to the next strongest that does. This
  option only appears when the selected modem has an operational eSIM profile.

Click **Save Schedule** to store the settings. They persist across reboots and
can be pushed to a fleet via NCM (see the `cell_survey_schedule` appdata field
above).

Automatic surveys only run when a supported, connected modem is available; if
one is not ready, the app logs why and skips that run. A manual survey never
triggers a carrier action — you stay in control of lock/eSIM from the results
page.

## History

Every completed survey that found cells is saved automatically as a CSV on the
**History** page, whether you ran it by hand or it ran on a schedule. Each file
is named with the date/time and the router's name, for example
`20260312_084500 - Store-142.csv`.

- Click **Download** next to any entry to save that CSV to your computer.
- The list shows when each survey ran, whether it was manual, startup, or
  scheduled, and how many carriers and cells it found.
- **Clear All** removes every saved CSV. The app keeps the 100 most recent
  surveys and prunes older ones automatically.

## Tips

- **Run the survey when the modem shows Connected.** Running it right after a
  lock or restore, while the modem is still re-registering, can return fewer
  cells or none. Wait for **Connected**, then scan again for a full result.
- A survey briefly uses the radio, so it may cause a short hiccup on an active
  connection.
- Carrier and country names come from a built-in lookup table, so they work
  without internet access. A cell the app can't match to a known carrier is
  shown as "Unknown."
- The header has a **Help** button and a **Device Info** button, plus a
  light/dark mode toggle.

## Good to know

This app only changes your network settings when *you* lock or restore a
carrier. It doesn't alter any other router configuration, and it doesn't send
your data anywhere — the survey and carrier lookup run entirely on the router.
