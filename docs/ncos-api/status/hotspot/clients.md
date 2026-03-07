# status/hotspot – clients

<!-- path: status/hotspot/clients -->
<!-- type: status -->

[status](../) / [hotspot](../hotspot.md) / clients

---

Client IP to per-client object (20+ fields). Returned as `status/hotspot` → `clients`.

### Structure

**clients.{ip}**

| Field | Type | Description |
|-------|------|-------------|
| `mac` | string | Client MAC address |
| `sessionid` | string | Session ID |
| `bw_up` | integer | Upload bandwidth limit (kbps) |
| `bw_down` | integer | Download bandwidth limit (kbps) |
| `stats` | object | See sub-table |
| `idle_timeout` | integer | Idle timeout seconds |
| `session_timeout` | integer | Session timeout seconds |
| `idle_time` | number | Idle time |
| `interim_interval` | number | Interim interval |
| `interim_time` | number | Interim time |
| `mac_authed` | boolean | MAC authorized |
| `max_input_octets` | number | Max input octets |
| `max_output_octets` | number | Max output octets |
| `max_total_octets` | number | Max total octets |
| `outpkt` | number | Output packets |
| `session_term_time` | number | Session termination time |
| `time` | number | Time |
| `uam_chal` | string | UAM challenge |
| `url` | string | URL |
| `username` | string | Username |

**clients.{ip}.stats**

| Field | Type | Description |
|-------|------|-------------|
| `in` | object | `{bytes, packets}` |
| `out` | object | `{bytes, packets}` |
