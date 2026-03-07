# status/wan/devices/{device_id}/diagnostics

<!-- path: status/wan/devices/{device_id}/diagnostics -->
<!-- type: status -->
<!-- response: object -->

[status](../) / [wan](.) / [devices](.) / diagnostics

---

Cellular modem diagnostics. **Only on `mdm-*` devices**; not on ethernet WAN. Flat key-value object. Includes signal metrics (DBM, RSRP, SS) and capability/config keys (SUPPORTS_*, FW_INFO*, VER_*, etc.).

### Fields (flat key-value object)

| Field | Type | Description |
|-------|------|-------------|
| `CARRID` | string | Carrier name (T-Mobile, Verizon, ATT) |
| `DBM` | string | Signal strength dBm |
| `RSRP` | string | Reference Signal Received Power (dBm) |
| `RSRQ` | string | Reference Signal Received Quality (dB) |
| `SINR` | string | Signal-to-Interference-plus-Noise Ratio |
| `RSRP_5G` | string | 5G RSRP when on 5G |
| `RSRQ_5G` | string | 5G RSRQ when on 5G |
| `SINR_5G` | string | 5G SINR when on 5G |
| `SS` | string | Signal strength % (0-100) |
| `RFBAND` | string | LTE band (e.g. Band 66) |
| `SRVC_TYPE` | string | Service type (LTE) |
| `CELL_ID` | string | Cell identifier |
| `ICCID` | string | SIM card ID |
| `EMMSTATE` | string | Registration state (Registered) |
| `MODEMOPMODE` | string | Online, Offline |
| `MODEMTEMP` | string | Modem temperature |
| `ACTIVEAPN` | string | Active APN |
| `ROAM` | string | Roaming (1=home; other values unknown) |

### SDK Example
```python
import cp
devices = cp.get('status/wan/devices') or {}
for dev_id, dev in devices.items():
    if dev_id.startswith('mdm-'):
        diag = cp.get(f'status/wan/devices/{dev_id}/diagnostics')
        if diag:
            carrier = diag.get('CARRID', '')
            dbm = diag.get('DBM', '')
            cp.log(f'{dev_id}: {carrier} signal {dbm} dBm')
```

### REST
```
GET /api/status/wan/devices/mdm-{uid}/diagnostics
```

### Example (partial)
```json
{
  "CARRID": "T-Mobile",
  "DBM": "-58",
  "RSRP": "-85",
  "RSRQ": "-8",
  "SINR": "23.4",
  "SS": "100",
  "RFBAND": "Band 66",
  "SRVC_TYPE": "LTE",
  "EMMSTATE": "Registered",
  "MODEMOPMODE": "Online",
  "ACTIVEAPN": "fast.t-mobile.com",
  "ROAM": "1"
}
```
