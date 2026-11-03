# Cell Survey

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
