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

## Opening the app

The app runs on the router and serves its web page on **port 8000**.

From a device connected to the router, open a browser to:

```
http://<router-LAN-IP>:8000
```

For example `http://192.168.0.1:8000`.

If the page won't load, the router's firewall may be blocking the port. Make
sure traffic from the LAN is allowed to reach the router on port 8000 (in the
router UI under **Security > Zone Firewall**, forward the Primary LAN Zone to
the Router Zone for that port).

## Using it

1. **Pick a modem.** If your router has more than one modem, choose it from the
   **Modem** dropdown. The built-in modem is selected for you by default. Use
   **Refresh** if you just inserted a SIM or the list looks out of date.
2. **Check the status tiles** to confirm the modem is **Connected** and see its
   current carrier and signal.
3. **Click Run Survey.** A "Scanning..." message with a timer appears while the
   scan runs. Most modems finish in under a minute; a 5G Standalone connection
   can take a couple of minutes.
4. **Review the results.** Carriers are listed strongest first and expanded by
   default. Each carrier lists its individual cells with band, channel, and
   signal details. Click a carrier's header to collapse it.
5. **Export CSV** (top of the results) downloads every detected cell as a
   timestamped file you can open in Excel or Google Sheets.

## Locking onto a carrier

To force the modem to use a specific carrier, click **Use this carrier** on that
carrier, then confirm with **Lock Modem**. The modem re-registers on that
network, so the data connection may drop for a few seconds.

A yellow banner shows which carrier is locked. To go back to normal, click
**Restore Automatic** in that banner and the modem returns to picking a network
on its own.

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
