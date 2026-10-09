# DSDS (Dual SIM Dual Standby) modems

<!-- path: status/wan/devices/{device_id} -->
<!-- type: status -->

[status](../) / [wan](.) / [devices](.) / dsds

---

A DSDS modem presents **each SIM slot as its own `mdm-*` WAN device**, but only one slot can
be connected at a time. The standby slot stays registered enough to keep reporting live
signal diagnostics, which is the capability that makes signal-driven failback possible.

Verified on an **R2400-5GF-NA, NCOS 7.26.81** with a T-Mobile SIM in slot 1 and a Verizon
SIM in slot 2.

## Detecting DSDS

| Field | Path | Value |
|-------|------|-------|
| `dsds` | `status/wan/devices/{uid}/info/dsds` | boolean `true` — cleanest indicator |
| `DSDS_ENABLED` | `.../diagnostics/DSDS_ENABLED` | string `'TRUE'` |
| `DSDS_INSTANCE` | `.../diagnostics/DSDS_INSTANCE` | string `'0'` / `'1'` — which DSDS leg |

Both indicators are present on both slot devices. Accept either, since only `DSDS_ENABLED`
is guaranteed on older builds.

## Telling the two slots apart

**`info/port` and `info/config_id` are IDENTICAL on both slots.** Both slots of one physical
modem match a single WAN rule (`trigger_string` on the test unit was
`type|is|mdm%tech|is|5g/lte%port|is|int1%dsds|is_true|int1`), so neither field can single
out a slot.

| Field | sim1 | sim2 | Distinguishes? |
|-------|------|------|----------------|
| `info/port` | `int1` | `int1` | No — shared |
| `info/config_id` | `00000008-…` | `00000008-…` | No — shared |
| `diagnostics/DISP_IMEI` | `354086290070284` | `354086290070284` | No — shared |
| `info/sim` | `sim1` | `sim2` | **Yes** |
| `info/uid` | `5a3e6e08` | `5a10a751` | **Yes** |
| `info/serial` (= `CGSN`) | `354086290070284` | `355395210070285` | **Yes** |
| `info/model` | `Internal 5GF-NA (SIM1)` | `Internal 5GF-NA (SIM2)` | **Yes** |
| `info/plug_id` | `2-1` | `2-2` | **Yes** |
| `info/sib_plug_id` | `2-2` | `2-1` | points at the sibling |
| `diagnostics/NETIF_NAME_STR` | `rmnet501` | `rmnet502` | **Yes** |

Note `diagnostics/DISP_IMEI` is shared while `info/serial` is **not** — `info/serial`
carries the per-slot `CGSN`. Group slots by `info/port`, tell them apart with `info/sim`,
and pair siblings with `plug_id` / `sib_plug_id`.

## Which slot is active

| Field | Path | Notes |
|-------|------|-------|
| `connection_state` | `.../status/connection_state` | `connected` on the active slot. **Use this for readiness.** |
| `isActiveSib` | `.../status/isActiveSib` | boolean; which slot owns the radio. Flips mid-switch — not a readiness signal |
| `IS_ACTIVE_SIB` | `.../diagnostics/IS_ACTIVE_SIB` | string `'TRUE'`/`'FALSE'`; same meaning |
| `summary` | `.../status/summary` | `connected`, `standby`, `Dual SIM switch`, `sibling transitioning` |
| `reason` | `.../status/reason` | `Dual SIM` while DSDS-managed, `Linkdown` on standby |

## Switching SIM slots

```python
# The PUT goes to the CONNECTED slot's device.
cp.put('control/wan/devices/mdm-5a3e6e08/testmode/dsds_switch', True)
```

`control/wan/devices/{uid}/testmode` is `{reset, ready, shutdown, dsds_switch}`. The PUT
returns in ~0.1s and the swap runs asynchronously.

**Two traps with the `dsds_switch` key:**

- It is **not always present** in a device's `testmode` struct beforehand. Its absence does
  not mean unsupported — the PUT creates it.
- Once written it **persists in the control tree for both slots** (control tree writes
  merge, never replace), so its presence does not mean supported either.

Never gate on the key. Gate on `info/dsds` / `DSDS_ENABLED`.

### Measured timeline

Elapsed from the PUT, polling `status/wan/devices` every second:

| Time | Outgoing slot | Incoming slot |
|------|---------------|---------------|
| 0.1s | PUT returns `{"success": true, "data": true}` | |
| 2.6s | `disconnecting` | |
| 3.7s | loses its IP | |
| 6.0s | `disconnected` / summary `standby` | |
| 7.2s | summary → `sibling transitioning` | `connecting` / summary `Dual SIM switch` |
| 14.1s | `isActiveSib` → false | `isActiveSib` → true |
| 28.3s | | receives an IP |
| **30.7s** | summary → `standby` | **`connected`** |

Across several switches the total ranged **29s to 37s**. Treat ~30s as typical and allow
headroom; a cold registration on a new carrier takes longer than a warm one.

- `summary` of `Dual SIM switch` (incoming) or `sibling transitioning` (outgoing) is the
  reliable way to detect a switch **in flight** and avoid re-triggering it.
- **Device UIDs are stable across a switch.** `mdm-5a3e6e08` stays slot 1, so IP Verify
  tests bound by `uid` keep working and their results follow the switch automatically.
- The router logs a kernel `NETDEV WATCHDOG: rmnet_ipa0 (ipa): transmit queue 2 timed out`
  warning with a full call trace during the swap. It is normal noise from the modem's
  internal core, not a fault.
- `dsds_switch` must be sent to a **connected** device. If neither slot is connected there
  is nothing to send it to, and NCOS drives recovery.

## Signal metrics depend on the live radio technology, not the modem

The available metric set is **not** a property of the modem or even of the slot. A modem
moves between these states without reconnecting, so re-read the set on every poll:

| `SRVC_TYPE_DETAILS` | Reported | Absent |
|---|---|---|
| `SA - 5G Sub-6 GHz` | `RSRP_5G` `-88`, `RSRQ_5G` `-11`, `SINR_5G` `17.5` | `DBM`, `RSRP`, `RSRQ`, `SINR` |
| `NSA - 5G Sub-6 GHz` | **both** families: `DBM` `-55`, `RSRP` `-84`, `RSRQ` `-10`, `SINR` `9.4` **and** `RSRP_5G` `-84`, `RSRQ_5G` `-11`, `SINR_5G` `31.5` | — |
| LTE | `DBM` `-50`, `RSRP` `-84`, `RSRQ` `-15`, `SINR` `12.6` | all `*_5G` |

5G **NSA** is anchored on LTE so it reports both families; 5G **SA** reports only the 5G
family. A threshold set only on `RSRP`/`SINR` therefore stops applying the moment the slot
moves to 5G SA. Code that assumes `DBM` exists will read `None` on a 5G SA connection.

**The standby slot reports live signal metrics**, which is specific to DSDS and is the only
basis available for judging a disconnected slot:

```python
# Works on the DISCONNECTED slot
diag = cp.get('status/wan/devices/mdm-5a10a751/diagnostics')
diag['RSRP']   # '-83'  — live
diag['SINR']   # '12.0' — live
cp.get('status/wan/devices/mdm-5a10a751/status/cellular_health_score')  # 88.0
```

`status/.../status/signal_backlog` also carries `dbm`/`sinr`/`rsrp`/`rsrq` for both slots,
but samples roughly **hourly** (observed `ts` deltas of 3600s), so it is far too stale for
failover decisions.

## Placeholder strings in diagnostics

Some diagnostics fields carry the **literal string** `'None'` rather than being omitted. On
a standby slot, `SRVC_TYPE_DETAILS` is `'None'`, which renders as the text "None" if passed
straight to a UI. Normalize `''`, `'None'`, and `'Unknown'` to absent.

Also note `CARRID` is **absent** on a slot that is not registered; fall back to
`HOMECARRID`. An empty slot has `NOSIM: 'TRUE'` and no `ICCID` or `CARRID` keys at all.

## See Also

- [status/wan/devices/diagnostics](diagnostics.md) — full signal metric list
- [status/wan/devices/info](info.md) — `config_id`, `port`, `sim`
- [config/wan/rules2](../../../config/wan-rules2.md) — WAN rules and `trigger_string`
- `apps/dsds_wan_verify/` — working app built on all of the above
