# 5GSpeed
Runs speedtests and puts results into a configurable field. Designed to enable NCM API support for speedtests.

## Speedtest Engines (priority order)

1. **Ookla** - if licensed `ookla` binary is present in app directory (BYOB)
2. **iPerf3** - if appdata `speedtest` is set to `iperf3` and `iperf3_server` is configured
3. **Netperf** - built-in router netperf service (default)

## SDK Appdata Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `5GSpeed` | No | Config path (default: `config/system/asset_id`) | Path where results are written |
| `speedtest` | No | `netperf` (default), `iperf3` | Engine selection when Ookla binary is not present |
| `iperf3_server` | Only if engine=iperf3 | `ip:port` or `ip:portx-porty` | iPerf3 server address. Single port or port range. App starts at the first port and increments if busy/failed |

### iperf3_server format examples

- `192.168.1.1:8000` — uses port 8000
- `10.0.0.1:5201-5210` — tries port 5201 first, increments through 5210 if a port is busy

## Steps to Use

The app will create an entry in the router configuration under System > SDK Data named "5GSpeed" with the path for the results field.
Default is `config/system/asset_id`.

Clear the results by performing any of the following:

1. Use NCM API PUT router request to clear the results field and to run the SDK speedtest. Wait for 1 min, and run NCM API GET router request to get the result.
2. Clear the results in NCM > Devices tab (if using description or asset_id).
3. Go to device console and clear results field:
   ```
   put {results_path} ""
   ```

## Sample Results

**Ookla:**
```
DL:52.54Mbps UL:16.55Mbps Ping:9.7ms Server:Telstra ISP:Vocus Time:2023-04-11T01:06:43Z
```

**Netperf:**
```
DL:96.82Mbps UL:46.74Mbps Engine:netperf Time:2023-04-11T01:06:43Z
```

**iPerf3:**
```
DL:85.23Mbps UL:42.11Mbps Engine:iperf3 Server:10.0.0.1:5201 Time:2023-04-11T01:06:43Z
```

## Retrieve Results via NCM API

- Generate NCM API v2 API Keys on the Tools page > NetCloud API tab in NCM.
- Use those keys in the headers of an HTTP GET request to `https://www.cradlepointecm.com/api/v2/routers/{router_id}/`
- `router_id` can be found in NCM or at CLI: `get status/ecm/client_id`
- The results are in the field defined in SDK Data (default is asset_id)

## Clear Results and Run New Test via NCM API

- Use API keys in headers of an HTTP PUT request to `https://www.cradlepointecm.com/api/v2/routers/{router_id}/`
- Content-Type: `application/json`
- Body contains blank field defined in SDK Data (default is asset_id):
  ```json
  {"asset_id": ""}
  ```

In a few minutes, new results should populate.
