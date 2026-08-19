---
inclusion: fileMatch
fileMatchPattern: "**/*speed*,**/*iperf*,**/*netperf*"
description: "Speedtest implementation standards for Cradlepoint SDK apps"
---
# Speedtest Implementation

- **NO Ookla license exists for SDK apps** - do NOT bundle or distribute the Ookla binary. All apps must work without it.
- **Engine priority**: Ookla (BYOB) → Netperf (built-in) → iPerf3 (user-provided server)
- **BYOB (Bring Your Own Binary)**: If a customer has their own Ookla license, they can drop the `ookla` binary into the app folder. Apps should detect it and use it automatically — but NEVER require it.
- **Default engine is Netperf** - uses `cp.speed_test()` from cp.py. No binary needed, no server config needed, supports per-interface testing via `ifc_wan`.
- **iPerf3 for user-controlled servers** - use when the user needs to test against their own infrastructure. Requires a server address (appdata or UI input). Bundle `iperf3-arm64v8` binary from @speedtest_web.

### Engine detection pattern (use in all speedtest apps):
```python
import os

OOKLA_BINARIES = ('ookla', 'speedtest', 'speedtest-cli')
IPERF3_BINARIES = ('iperf3', 'iperf3-arm64v8', 'iperf3-aarch64')

def _find_binary(candidates):
    """Find first existing binary from candidates list, chmod if needed."""
    for name in candidates:
        if os.path.exists(name):
            if not os.access(name, os.X_OK):
                try:
                    os.chmod(name, 0o755)
                except Exception:
                    pass
            return name
    return None

def has_ookla():
    return _find_binary(OOKLA_BINARIES) is not None

def has_iperf3():
    return _find_binary(IPERF3_BINARIES) is not None
```

### Simple speedtest (single interface, no UI):
```python
def run_speedtest():
    """Ookla if present, else netperf."""
    if has_ookla():
        result = run_ookla()
        if result:
            return result
        cp.log('Ookla failed, falling back to netperf...')
    return run_netperf()

def run_ookla():
    try:
        from speedtest_ookla import Speedtest
        s = Speedtest(timeout=90)
        s.start()
        return s.results.download / 1e6, s.results.upload / 1e6
    except Exception as e:
        cp.log(f'Ookla error: {e}')
        return None

def run_netperf():
    result = cp.speed_test(duration=10, direction='both')
    if result:
        return result['download_bps'] / 1e6, result['upload_bps'] / 1e6
    return 0.0, 0.0
```

### Per-interface testing (multi-SIM apps):
- **Netperf**: Use `cp.speed_test(interface=iface)` — the `ifc_wan` parameter handles routing natively. No source routing needed.
- **Ookla**: Requires source routing or `-i source_ip` binding (see Mobile_Site_Survey `speedtest.py`)
- **iPerf3**: Use `-B source_ip` for binding. Needs port range for concurrent tests (one port per modem).

### Concurrent multi-modem testing:
- **Netperf CANNOT run concurrent tests** - it's a single shared router resource. Test modems sequentially.
- **Ookla CAN run concurrent tests** - each is an independent subprocess with `-i source_ip`
- **iPerf3 CAN run concurrent tests** - each subprocess uses `-B source_ip` and a different port from a configured range (e.g. `5201-5210`)
- **For concurrent multi-modem**: Use Mobile_Site_Survey's `speedtest.py` wrapper which handles both Ookla (BYOB) and iPerf3 with port allocation

### Netperf API (cp.speed_test):
```python
result = cp.speed_test(
    interface='rmnet501',  # ifc_wan - routes test through this interface
    duration=10,           # seconds
    direction='both'       # 'recv', 'send', or 'both'
)
# Returns: {'download_bps': float, 'upload_bps': float, ...}
```

### Netperf TCP RR (latency/jitter):
Use `control/netperf` with `"rr": True` for latency measurement. See @speedtest_web for implementation.

Verified field names in `status/wan/devices/{uid}/status/perf_results/tcp_rr`:
- **`RT_LATENCY`** and **`STDDEV_LATENCY`**, both in **microseconds** (divide by 1000 for ms)
- **There is no `MEAN_LATENCY`, `MIN_LATENCY`, `MAX_LATENCY`, `P50_LATENCY` or `P99_LATENCY`** on NCOS 7.x — speedtest_web checks `MEAN_LATENCY` first and falls through to `RT_LATENCY`, so always keep the `RT_LATENCY` fallback
- `THROUGHPUT_UNITS` for an RR test is `Trans/s` (transactions/sec) — it is NOT a bitrate, do not convert it to bps

### Netperf gotchas:
- **`cp.speed_test()` does NOT return byte counters or latency** — `latency_ms` is initialised to 0 and never populated. Real volume is in `perf_results/tcp_down/LOCAL_BYTES_RECVD` and `perf_results/tcp_up/LOCAL_BYTES_SENT` (strings, coerce to int). Read them right after the test.
- **`perf_results` accumulates keys across runs and is never cleared** — after a recv-only test the tree still holds the `tcp_up` and `tcp_rr` values from whenever they last ran. Reading a key that the current test did not produce silently returns stale numbers. Compare the entry's `TIME` field against its value from before the run if you need to be sure.
- **`ifc_wan` takes the iface name** (e.g. `pmip3`, `wan`), from `status/wan/devices/{uid}/info/iface` — not the device uid.
- **Do NOT substitute `control/ping` for netperf latency** — netperf has a real latency/jitter test (TCP_RR, above). Use it. `cp.speed_test()` for throughput plus one `control/netperf` `rr` call for latency is the correct combination.

### iPerf3 pattern:
```python
cmd = ['./iperf3-arm64v8', '-c', server, '-p', str(port), '-t', '10', '-J']
cmd.append('-R')  # reverse for download
# For source binding: cmd.extend(['-B', source_ip])  # MUST be IP address, NOT interface name
```
- **`-B` requires an IP address** — passing an interface name (e.g. `pmip3`) causes "Invalid argument". Resolve iface to IP first via `status/wan/devices/{uid}/status/ipinfo/ip_address`

### Reference apps:
- **@speedtest_web** - Full web UI with all 3 engines, history, reports, latency/jitter
- **@5GSpeed** - Simple Ookla→netperf fallback pattern
- **@Mobile_Site_Survey** - Concurrent multi-modem with Ookla BYOB + iPerf3 port range
