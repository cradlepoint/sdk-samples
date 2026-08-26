# IMEI_ICCID_asset_id

Writes the internal modem IMEI and the ICCID/carrier of every SIM present into the
router's Asset ID field (`config/system/asset_id`), which surfaces as **Asset ID** in
NetCloud Manager.

## Output format

```
IMEI: 357926100739635 | SIM1: Verizon 89148000010933156465 | SIM2: T-Mobile 8901260882194090000
```

- `IMEI` comes from the internal modem (`diagnostics/DISP_IMEI`, falling back to
  `info/serial`). Both SIM slots share one physical modem, so there is one IMEI.
- One `SIM{n}` section per slot that has a SIM installed, ordered by slot number.
  Slots reporting `NOSIM` or no ICCID are omitted entirely.
- The carrier name is whatever the modem reports in `CARRID` (falling back to
  `HOMECARRID`, then `info/carrier_id`). This is the short form, e.g. `Verizon`,
  `T-Mobile`, `ATT` — not the marketing name. If no carrier is reported, the section
  shows just the ICCID.

## How it works

Every poll the app reads `status/wan/devices`, keeps the `mdm-*` devices whose
`info/port` is `int1` (the internal modem — each SIM slot is its own `mdm-*` device),
and builds the string from their `diagnostics`. It only PUTs to
`config/system/asset_id` when the value differs from what is already there, so a
stable router does no config writes after the first one.

If the modem has not reported IMEI/SIM data yet (common right after boot), the app
retries every 15 seconds until it has data, then settles into the normal poll interval.

## Appdata

All fields are optional.

| Field | Default | Description |
|-------|---------|-------------|
| `IMEI_ICCID_asset_id.poll_interval` | `300` | Seconds between checks. Values below `30` are clamped to `30`. |

Set appdata in NCM under Configuration > System > SDK Data, or on the router at
`config/system/sdk/appdata`.

## Notes

- Only the internal modem (`port` = `int1`) is included. USB or external modems are
  ignored.
- The app overwrites any existing Asset ID value.
