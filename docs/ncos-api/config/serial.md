# config/system/serial - Serial Port Configuration

<!-- path: config/system/serial -->
<!-- type: config -->

[NCOS API Documentation](../) / [config](README.md) / system/serial

Serial port settings plus the router's built-in serial redirector service.
Verified on an E3000-C18B running NCOS 7.26.41.

---

## Read

```python
import cp
config = cp.get('config/system/serial')
```

```bash
curl -s -u admin:pass http://ROUTER/api/config/system/serial
```

Actual response:

```json
{
    "baud_rate": 9600,
    "byte_parity": 0,
    "byte_size": 8,
    "enabled": false,
    "flow_control": {
        "hardware": false,
        "software": true
    },
    "linefeed": 2,
    "serial_ip": {
        "enabled": false,
        "host": "server",
        "port": 7218,
        "remote_port": 7218,
        "wan": false
    },
    "serial_port": "ttyUSB0",
    "server": {
        "lan": true,
        "lan_admin": true,
        "port": 7218,
        "wan": false
    },
    "status": "Disabled",
    "stop_bits": 0,
    "telnet_control": false
}
```

`status` is read-only informational text ("Disabled" when `enabled` is false).

## Enumerated fields

From `/api/dtd/config/system/serial`.

### `byte_parity`

**The order is None, Even, Odd — Even is 1, not 2.** Getting this backwards
silently misconfigures the line.

| Value | Meaning | pyserial constant |
|-------|---------|-------------------|
| 0 | None | `serial.PARITY_NONE` |
| 1 | Even | `serial.PARITY_EVEN` |
| 2 | Odd | `serial.PARITY_ODD` |
| 3 | Mark | `serial.PARITY_MARK` |
| 4 | Space | `serial.PARITY_SPACE` |

### `stop_bits`

| Value | Meaning | pyserial constant |
|-------|---------|-------------------|
| 0 | 1 | `serial.STOPBITS_ONE` |
| 1 | 1.5 | `serial.STOPBITS_ONE_POINT_FIVE` |
| 2 | 2 | `serial.STOPBITS_TWO` |

### `byte_size`

`5`, `6`, `7`, or `8`. Passed straight to pyserial's `bytesize`.

### `serial_port`

`ttyUSB0` (labelled both "Serial" and "USB" in the DTD options) or `ttyACM0`
("ACM"). The device path is `/dev/{serial_port}`.

### `baud_rate`

50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800, 9600, 19200,
38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600, 1000000, 1152000,
1500000, 2000000, 2500000, 3000000, 3500000, 4000000.

### `linefeed`

0 Ignore, 1 CRLF, 2 CR, 3 LF.

## Flow control is mutually exclusive

`flow_control.hardware` (RTS/CTS) and `flow_control.software` (XON/XOFF) cannot
both be true. The router returns:

```json
{"exception": "servicevalidation",
 "path": ["config", "system", "serial", "flow_control"],
 "reason": "Software and Hardware flow controls cannot be configured together."}
```

Because of this, **write serial settings as a single struct PUT, not per-leaf
PUTs.** Per-leaf writes make the router validate each intermediate state, so
switching from software to hardware flow control always fails partway through
and leaves the earlier leaves already applied.

```python
# Correct: one PUT, validated as a whole, all-or-nothing
cp.put('config/system/serial', {
    'serial_port': 'ttyUSB0',
    'baud_rate': 19200,
    'byte_size': 8,
    'byte_parity': 0,
    'stop_bits': 0,
    'flow_control': {'hardware': True, 'software': False},
})
```

The PUT merges into the existing struct, so unlisted fields such as `serial_ip`
and `server` are preserved.

## Opening the port from an SDK app

```python
import cp
import serial

PARITY_MAP = {0: serial.PARITY_NONE, 1: serial.PARITY_EVEN, 2: serial.PARITY_ODD,
              3: serial.PARITY_MARK, 4: serial.PARITY_SPACE}
STOPBITS_MAP = {0: serial.STOPBITS_ONE, 1: serial.STOPBITS_ONE_POINT_FIVE,
                2: serial.STOPBITS_TWO}

config = cp.get('config/system/serial')
flow = config.get('flow_control') or {}
ser = serial.Serial(
    port='/dev/%s' % config['serial_port'],
    baudrate=config['baud_rate'],
    bytesize=config['byte_size'],
    parity=PARITY_MAP.get(config['byte_parity'], serial.PARITY_NONE),
    stopbits=STOPBITS_MAP.get(config['stop_bits'], serial.STOPBITS_ONE),
    xonxoff=bool(flow.get('software')),
    rtscts=bool(flow.get('hardware')),
    timeout=1,
)
```

`pyserial` is not in cppython's stdlib — bundle the `serial/` package in the app
folder. See the `serial_to_UDP` sample.

Notes:

- `enabled` turns on the router's own serial redirector service. An SDK app
  holding `/dev/ttyUSB0` and the redirector service can contend for the device.
- Serial hardware is not reachable when running an app locally against a dev
  router; `serial.Serial` opens your computer's devices, not the router's. Test
  serial paths on the router.

## Related

- [README.md](README.md) - Config API conventions and PUT semantics
- [PATHS.md](PATHS.md) - Full config path list
