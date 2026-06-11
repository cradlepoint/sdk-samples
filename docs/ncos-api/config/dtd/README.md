# DTD Files — Config Schema by Model and NCOS Version

The DTD (Data Type Definition) defines the complete config tree schema for a specific router model and NCOS firmware version. It contains every configurable path with types, defaults, min/max values, options, and structure.

Different router models have different hardware capabilities (ethernet ports, radios, modems, GPS, WiFi, Bluetooth) and therefore different config schemas. A DTD captured from one model may not apply to another.

## Naming Convention

```
{MODEL}-NCOS-{VERSION}.json
```

Examples:
- `E3000-NCOS-7.25.101.json` — E3000 enterprise branch router
- `E300-NCOS-7.25.101.json` — E300 endpoint
- `R1900-NCOS-7.25.50.json` — R1900 ruggedized router
- `IBR1700-NCOS-7.24.3.json` — IBR1700 vehicle router

## Current DTDs

| File | Model | NCOS Version | Notes |
|------|-------|--------------|-------|
| [E3000-NCOS-7.25.101.json](E3000-NCOS-7.25.101.json) | E3000 | 7.25.101 | 10 ethernet ports (4 PoE), enterprise branch router |

## How to Add a New DTD

1. **Capture the DTD from your router:**

```bash
curl -s -k -u admin:password "https://ROUTER_IP/api/dtd/config" | python3 -m json.tool > {MODEL}-NCOS-{VERSION}.json
```

2. **Name the file** using the convention above. Get the model from:
   - Router label / NCM device list
   - `GET /api/status/product_info/product_name`

3. **Place the file** in this directory (`docs/ncos-api/config/dtd/`).

4. **Update the table above** with the new entry.

5. **Regenerate PATHS.md** if needed (point the script at the new DTD):

```bash
python3 generate_config_paths.py --dtd docs/ncos-api/config/dtd/{MODEL}-NCOS-{VERSION}.json
```

## What Varies Between Models

| Capability | Example Differences |
|------------|-------------------|
| Ethernet ports | E3000 has 10 (1 WAN + 9 LAN, 4 PoE). Smaller models may have 1–5 |
| Cellular modems | Some have dual 5G, some single LTE, some none |
| WiFi radios | May have 0, 1, or 2 radios; WiFi 5 vs WiFi 6 |
| GPS | Some have built-in GPS, some rely on modem GPS |
| Bluetooth | Present on some models for BLE beacon scanning |
| Serial ports | Vehicle/industrial models may have RS-232 or CAN bus |
| PoE (PSE) | Enterprise models supply power; others do not |
| Container support | Not all models support Docker containers |

## Usage in Development

The DTD is useful for:
- **Verifying config paths exist** before writing code that uses them
- **Checking field types and constraints** (min/max, allowed values, string lengths)
- **Understanding defaults** — what the router ships with
- **Discovering available options** — enum fields list all valid values

```python
# Example: check what options a field supports
# Look in the DTD for "options" arrays — they list [value, description] pairs
```

## Steering Integration

The `.kiro/steering/api-reference.md` file references the DTD for API verification. When working with a specific model, point your verification at the correct DTD file for that model.
