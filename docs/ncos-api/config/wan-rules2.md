# config/wan/rules2

WAN profiles that match and configure WAN devices. Each rule has a trigger pattern that matches device properties.

## Structure

List of rule objects. Each rule:

| Field | Type | Description |
|-------|------|-------------|
| `_id_` | uuid | Unique rule identifier |
| `trigger_name` | string | Human-readable name |
| `trigger_string` | string | Match pattern (e.g., `type\|is\|mdm%sim\|is\|sim1`) |
| `priority` | float | Failover/failback priority. **LOWER number = more preferred** |
| `disabled` | boolean | **True = rule disabled, False/absent = enabled** |

## Disabling WAN Devices

**Use the `disabled` field to enable/disable WAN connections:**

```python
# Get device's rule ID from status
device = cp.get('status/wan/devices/mdm-41949674')
config_id = device.get('info', {}).get('config_id')

# Disable the rule
cp.put(f'config/wan/rules2/{config_id}/disabled', True)

# Enable the rule
cp.put(f'config/wan/rules2/{config_id}/disabled', False)
```

## Device-to-Rule Mapping

Each WAN device in `status/wan/devices/{device_id}/info` has a `config_id` field that references its matched rule's `_id_`:

```python
# Find which rule a device is using
devices = cp.get('status/wan/devices') or {}
for device_id, device_data in devices.items():
    config_id = device_data.get('info', {}).get('config_id')
    if config_id:
        rule = cp.get(f'config/wan/rules2/{config_id}')
        print(f"{device_id} uses rule: {rule.get('trigger_name')}")
```

## Common Patterns

### Disable specific modem

```python
# Get modem's config_id
modem = cp.get('status/wan/devices/mdm-41949674')
rule_id = modem.get('info', {}).get('config_id')

# Disable it
if rule_id:
    cp.put(f'config/wan/rules2/{rule_id}/disabled', True)
```

### Disable all modems

```python
rules = cp.get('config/wan/rules2') or []
for rule in rules:
    if 'type|is|mdm' in rule.get('trigger_string', ''):
        rule_id = rule.get('_id_')
        cp.put(f'config/wan/rules2/{rule_id}/disabled', True)
```

## Notes

- **Multiple devices can match one rule** (e.g., SIM1 and SIM2 both match a generic modem rule)
- **Disabled rules prevent device activation** - device won't connect even if plugged in
- **Priority only matters for enabled rules** - disabled rules are ignored regardless of priority
- **Negative priority is NOT the same as disabled** - negative priority affects failover order, disabled completely prevents use

## Priority direction: LOWER is more preferred

The DTD only says `"comment": "Failover and failback priority."` without a direction, and an
earlier version of this page claimed "higher = preferred". That was **wrong**. The stock
priorities on an R2400 (NCOS 7.26.81) are:

| Rule | Priority |
|------|----------|
| Wbond | -10.012 |
| DSDS Modem-Internal Modem 1 | 0 |
| Ethernet | 1 |
| 5G/LTE Multi-mode Modems | 1.5 |
| Satellite | 1.7 |
| LTE-only Modems | 2 |
| LTE/3G Multi-mode Modems | 2.5 |
| WiFi as WAN | 4 |
| 3G-only Modems | 5 |

Read in **ascending** order that is exactly NCOS's default WAN preference (Ethernet before
5G/LTE before Satellite before LTE-only, with WiFi-as-WAN and 3G last), so lower number =
more preferred. Inferred from the stock ordering rather than a controlled failover test, but
the match is exact across nine rules.

## DSDS modems: both SIM slots share one rule and one priority

On a DSDS modem each SIM slot is a separate `mdm-*` device, but **both slots report the same
`info/config_id`**, so they match a single rule and share its priority. Verified on an R2400
where both slots pointed at `00000008-…` (`DSDS Modem-Internal Modem 1`, priority 0).

WAN rule priority therefore **cannot express a preference between the two slots of one DSDS
modem**. An app that needs a preferred slot has to carry its own priority setting; see
`apps/dsds_wan_verify/`. Per-SIM WAN rules can be created (`trigger_string` does support
`sim|is|sim1`, unlike ipverify's trigger fields), but that changes device-to-rule mapping and
is not required just to express a preference.

## See Also

- [status/wan/devices/info](../status/wan/devices/info.md) - Device config_id field
- [config/wan/](README.md) - WAN configuration overview
