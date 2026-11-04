<img width="1127" height="835" alt="image" src="https://github.com/user-attachments/assets/110d53e7-54c8-4ae0-9032-7ffd673c2c4c" />
<img width="1127" height="734" alt="image" src="https://github.com/user-attachments/assets/3a012a10-a54f-4c58-a208-8d0f01923c1e" />
<img width="1127" height="527" alt="image" src="https://github.com/user-attachments/assets/b956e369-101a-43d7-a4d9-8cc4342ffd74" />

# Cell Survey

See which cellular carriers are around your router and how strong each one is,
then optionally lock your modem to the carrier you want. Everything happens in
a simple web page served by the router — no apps to install on your computer.

## What you can do

- **See your modem at a glance** — carrier, network type (5G or LTE), band,
  APN, SIM, and signal strength, with an easy-to-read quality label.
- **Run a survey** to find every nearby cell tower, grouped by carrier and
  sorted strongest first.
- **Export the results** to a spreadsheet (CSV).
- **Lock onto a carrier** so the modem uses only that network, and switch back
  to automatic whenever you want.
- **Activate an eSIM profile** for a carrier, if your modem is eSIM-capable and
  already has a profile installed for it.
- **Schedule surveys** to run on their own and, if you like, automatically move
  the modem to the best carrier afterward.
- **Keep a history** of past surveys you can download anytime.

## Opening the app

From a phone or computer connected to the router, open a web browser to:

```
http://<your-router-IP>:8000
```

For example `http://192.168.0.1:8000`. (Your router's IP is the same address
you use to reach its admin page.)

If the page doesn't load, see **Troubleshooting** at the bottom.

## The three pages

A menu on the left switches between:

- **Run Survey** — your modem's live status and the manual survey.
- **Schedule** — set up surveys that run automatically.
- **History** — browse and download past survey results.

## Running a survey

1. **Pick a modem.** If your router has more than one modem, choose it from the
   **Modem** menu; otherwise the built-in modem is already selected. You pick
   the modem, not a SIM slot.
2. **Check the SIM slots.** Below the menu, a small tag shows each SIM slot's
   status — **NO SIM** if the slot is empty, otherwise whether it's connected.
3. **Review the status tiles** for the current carrier and signal. You don't
   need an active connection to run a survey — it scans the airwaves directly
   and works even with no SIM installed.
4. **Click Run Survey.** A "Scanning..." timer appears. Most scans finish in
   under a minute; 5G can take a couple of minutes.
5. **Read the results.** Carriers are listed strongest first. Click a carrier
   to expand its individual towers with band, channel, and signal details. The
   live status tiles collapse to a one-line summary so the results stand out —
   click **Current connection** to open them again.
6. **Export CSV** (above the results) saves everything to a file you can open
   in Excel or Google Sheets.

## Locking onto a carrier

To make the modem use one specific carrier, click **Lock Carrier PLMN** on that
carrier and confirm. The modem re-registers on that network, so your connection
may drop for a few seconds.

A banner then shows which carrier is locked. To go back to normal, click
**Restore Automatic** in that banner.

## Activating an eSIM profile

If your modem has a built-in eSIM, the app reads the profiles already loaded on
it. When a surveyed carrier matches one of your usable profiles, an **Activate
eSIM Profile** button appears next to **Lock Carrier PLMN** for that carrier.

- Click it and confirm to switch to that profile. The modem re-registers and
  may briefly drop the connection.
- A carrier that's already active shows an **eSIM active** badge instead.
- If your modem has no eSIM, you simply won't see any eSIM buttons.

## Scheduling surveys

On the **Schedule** page you can have the app survey on its own. Turn on either
or both:

- **Run Survey on Startup** — runs once shortly after the router powers on.
- **Run Survey on Schedule** — repeats on a timing you choose. Pick a ready-made
  option (every 15 minutes, hourly, daily at 6am, and so on) or build your own.

For each one, the **After the survey** menu decides what happens next:

- **Do not select carrier** — just save the results (default).
- **Lock best carrier PLMN** — lock the modem to the strongest carrier found.
- **Activate best carrier eSIM** — switch to the eSIM profile of the best
  carrier that has one installed. (Only shown when your modem has a usable eSIM
  profile.)

Click **Save Schedule** to keep your settings; they survive a reboot.

## History

Every survey that finds towers is saved automatically on the **History** page,
whether you ran it yourself or it ran on a schedule.

- **Download** saves that survey's CSV to your device.
- The list shows when each ran, how it was triggered, and how many carriers and
  towers it found.
- **Clear All** removes saved surveys. The app keeps the 100 most recent and
  drops older ones on its own.

## Tips

- A survey briefly uses the radio, so it may cause a short hiccup on an active
  connection.
- Right after a lock or eSIM switch the modem is still settling, so a scan can
  show fewer towers. Wait a few seconds and scan again for a full picture.
- A tower the app can't match to a known carrier shows as "Unknown."
- The header has **Help** and **Device Info** buttons and a light/dark toggle.

## Troubleshooting

- **The page won't open.** Double-check the router's IP and that you used port
  `8000` (`http://<your-router-IP>:8000`). Make sure your device is connected
  to the router. If it still won't load, the router's firewall may be blocking
  the port — ask whoever manages the router to allow LAN devices to reach it on
  that port.
- **"Run Survey" is greyed out.** The survey needs one of the supported modems
  (Cradlepoint's Telit 5G modules). Other modems can't run it, and the app will
  say so.
- **No modems listed.** Use the **Refresh** button, especially right after
  inserting a SIM or powering the modem up.

## Good to know

The app only changes your network settings when *you* lock or restore a carrier
(or when a schedule you set up does). It doesn't touch anything else on the
router, and it doesn't send your data anywhere — everything runs on the router
itself.
