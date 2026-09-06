# Speedtest Analyzer

Speedtest Analyzer provides web-based WAN performance testing and analysis for Cradlepoint routers with multiple test engines, per-WAN testing, scheduling, history, live cellular diagnostics, Carrier Activity, historical Cellular Analysis, site-wide GeoView context, iPerf3 server management, endpoint reliability tracking, and reporting.

**Version:** 1.1.3
**Firmware family tested:** NCOS 7.26.x
**Architecture:** ARM64 (aarch64)

> **Validation notice:** This app has been tested on the device models and firmware versions listed below. Other Cradlepoint models may work, but have not been fully validated. Results and feature behavior may vary.

For implementation details, platform behavior, validation logic, Carrier Activity internals, source routing, Netperf lifecycle handling, persistence behavior, and the complete engineering changelog, see [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).

---

# What You Can Do

Speedtest Analyzer is designed to let a technical user test, monitor, and compare WAN connections directly from a Cradlepoint router without needing to understand the application's internal routing, API, or process-management logic.

Key capabilities include:

- Run on-demand **Downlink and Uplink** throughput tests.
- Test the current **Active Primary WAN** or select a specific connected WAN.
- Use **iPerf3**, **Netperf**, or an optional licensed **Ookla** binary.
- Use the bundled **Public iPerf3 Server** catalog or maintain a separate **User Server List**.
- Run one-time tests against a **Custom Server** without saving it.
- Schedule recurring tests using presets, the visual schedule builder, or cron.
- Stop supported in-progress tests from the **Test Center**.
- Review successful, partial, and failed tests in **History & Reports**.
- Filter results by interface, status, and time range.
- View throughput trends and detailed test information.
- Monitor cellular health, service type, serving bands, and Carrier Activity when NCOS exposes the required data.
- Analyze retained cellular history by serving cell, network mode, RF conditions, radio configuration, and observed handoffs.
- Review a site-wide **Cellular GeoView** showing serving cells observed across all retained cellular interfaces, with carrier filtering and per-cell interface context.
- Review published modem Carrier Aggregation capability references for supported modem variants.
- Track saved iPerf3 endpoint reliability.
- Export results in CSV or HTML format.
- Export Cellular Analysis as a self-contained HTML report optimized for browser printing and **Save as PDF**.
- Write successful result summaries to supported NCOS-accessible output fields when desired.

---

# Validated Platforms

## Standalone devices

| Device | Firmware Tested | Validation Date | iPerf3 | Netperf |
|---|---|---|---|---|
| **E400-5GE-AM** | 7.26.60.e4f838965b | 2026-08-20 | Supported primary + secondary WAN | Supported primary + secondary WAN |
| **E3000-5GB** | 7.26.60.e4f838965b | 2026-08-20 | Supported primary + secondary WAN | Supported primary + secondary WAN |
| **R1900-5GB** | 7.26.41.5c28c17a47 | 2026-08-20 | Supported primary + secondary WAN | Supported primary + secondary WAN |
| **R980-5GD** | 7.26.60.e4f838965b | 2026-08-20 | Supported primary + secondary WAN | Supported primary + secondary WAN |
| **R2400** | 7.26.60 | 2026-08-20 | Supported on validated WAN paths | Supported on validated WAN paths |
| **W1850** | 7.26.60.e4f838965b | 2026-08-18 | Supported on validated cellular path | Supported on validated cellular path |
| **W1855** | 7.26.60.e4f838965b | 2026-08-18 | Supported on validated cellular path | Supported on validated cellular path |
| **W2255** | 7.26.60.e4f838965b | 2026-08-20 | Supported on validated cellular path | **Disabled — known NCOS defect** |

## Validated controller + captive-modem combinations

| Combination | Validation Date | iPerf3 | Netperf |
|---|---|---|---|
| **E3000 + W1850** | 2026-08-18 | Supported | Supported |
| **R2400 + RC1250** | 2026-08-19 | Supported | **Disabled — known NCOS defect** |

## Known engine limitations

| Platform / Combination | Engine | Confirmed Firmware | User Impact | Recommended Alternative |
|---|---|---|---|---|
| **W2255** | Netperf | 7.26.60 | Netperf is disabled because the native NCOS test can hang or continue indefinitely. | Use iPerf3. |
| **R2400 + RC1250** | Netperf | 7.26.60 | Netperf is disabled when testing the RC1250 captive WAN because the native NCOS test can continue beyond the requested duration and fail to return results. | Use iPerf3. |
| **AER2200** | iPerf3 | 7.25.121 | The bundled iPerf3 executable cannot be launched on this platform. | Use Netperf. |

A validation warning does not block testing by itself. A confirmed engine defect can disable only the affected engine for the matching device or captive-modem combination.

---

# Quick Start

## 1. Install the app

Deploy the `speedtest_analyzer` SDK application to the Cradlepoint router using your normal application deployment method.

After installation, allow a short period for NCOS to upload, extract, and start the application.

## 2. Access the web interface

The application listens on TCP port `8000`.

If connecting through **NCM LAN Manager**, no local firewall zone-forwarding changes are required to access the app.

If connecting from a device on the router's **local LAN**, configure zone forwarding in both directions:

- Primary LAN Zone to Router Zone
- Router Zone to Primary LAN Zone

Then browse to:

```text
http://<router_ip>:8000
```

Example:

```text
http://192.168.0.1:8000
```

## 3. Run your first test

1. Open **Test Center**.
2. Leave **Active Primary WAN** selected to test whichever WAN NCOS currently considers primary, or select a specific connected WAN.
3. Select **iPerf3** or **Netperf**.
4. For iPerf3 Public mode, select a **Region** and a server.
5. Set the desired test duration and available options.
6. Start the test.
7. Review Downlink, Uplink, data transferred, latency/jitter when available, and cellular information when testing a cellular WAN.

<img width="1134" height="608" alt="Speedtest Analyzer Test Center configured for a Public iPerf3 test" src="https://github.com/user-attachments/assets/2bca8ddb-dd22-474f-9adf-b67b243af867" />

*Screenshots in this guide use example lab device names and private IP addressing. Device names, WAN labels, addresses, and available interfaces will vary by deployment.*

The bundled **Public iPerf3 Server** catalog is available without first creating a User Server List.

- **Public iPerf3 Servers** are the easiest way to begin testing.
- **User Server List** is intended for private, trusted, or preferred persistent iPerf3 endpoints.
- **Custom Server** provides a one-time manual iPerf3 test without saving the endpoint.
- **Netperf** uses the router's native Cradlepoint Netperf service and does not require an iPerf3 server.
- **Ookla** is optional and requires a compatible licensed ARM64 Ookla/Speedtest binary to be included with the application.

---

# Test Center

**Test Center** is the central area for on-demand Manual Tests, live test results, and Scheduled Tests.

## Manual Tests

Use **Manual Tests** when you want to run a test immediately.

### WAN selection

The default selection is **Active Primary WAN**.

This is useful when the goal is to test the router's currently preferred connection without manually selecting an interface. The application resolves the actual primary WAN when the test starts, and History records the real interface that was used.

Manual Tests and Scheduled Tests both keep the WAN selector available whenever a connected WAN exists. The selector shows **Active Primary WAN** first and also lists each connected WAN interface, even when only one physical WAN is connected.

Select a specific interface when you want the test pinned to that WAN instead of following whichever WAN is primary when the test starts.

Friendly interface labels may include:

- **Ethernet WAN**
- **Wi-Fi as WAN**
- **Satellite WAN-XXXX**
- **E3000 Internal - VZW-SIM1**
- **W1850 Captive - TMO-SIM1**
- **W1850 - TMO-SIM1** on a standalone adapter

The friendly name is only a display label. The application retains the underlying NCOS interface identity for actual test execution.

### Typical workflow

1. Select the WAN.
2. Select the test engine.
3. Select the server or server source when applicable.
4. Configure duration and available options.
5. Start the test.
6. Watch the live status and cellular information.
7. Review the final result.
8. Open **History & Reports** for previous tests, trends, filters, detailed diagnostics, or exports.

Unsupported engine/device combinations are disabled rather than silently attempted.

### Stopping a test

The Test Center supports stopping an active manual test.

For iPerf3, the application terminates the active local iPerf3 process. If Downlink completed but Uplink is cancelled, the completed direction can be retained as a **Partial** result.

Netperf cancellation uses the router's native NCOS speed-test control.

## Live Results and Cellular Information

During and after a test, the Test Center can display:

- Downlink throughput
- Uplink throughput
- Data downloaded
- Data uploaded
- Latency or iPerf3 TCP RTT
- Jitter
- TCP retransmissions for iPerf3
- Cellular Health
- Service Type
- Active Carriers

<img width="1260" height="226" alt="Speedtest Analyzer live cellular results showing throughput, cellular health, service type, and Active Carriers" src="https://github.com/user-attachments/assets/1bac67aa-75f1-4043-b3f8-f41ac9a171fe" />

**Data downloaded** and **Data uploaded** represent data reported by the active test engine. They are not general WAN-interface byte-counter changes, so unrelated production/user traffic sharing the selected WAN is not counted as speed-test data.

If a direction does not produce a valid engine result, its data value remains unavailable rather than falling back to total WAN traffic.

### Active Carriers

When a cellular WAN is selected, **Active Carriers** shows the current radio state reported by NCOS, including available items such as:

- Service mode
- Active carrier count
- Active bands
- Observed Downlink bandwidth across reported active serving carriers
- Peak carrier count and observed Downlink bandwidth reached during the current test

Cellular state is refreshed approximately every two seconds while a test is running.

The application reports what NCOS exposes. It does not force Carrier Aggregation or 5G activation.

A successful speed test therefore does not guarantee that additional component carriers will activate.

## Scheduled Tests

Use **Scheduled Tests** to run recurring tests automatically.

Run a configuration manually first to verify that the selected WAN, engine, and server complete successfully before scheduling it.

The WAN selector defaults to **Active Primary WAN**.

Available schedule methods include:

- Quick presets
- Visual schedule builder
- Custom cron expression

Typical presets include:

- Every 5 minutes
- Every 15 minutes
- Every 30 minutes
- Hourly
- Daily
- Weekly
- Weekdays

<img width="1259" height="706" alt="Speedtest Analyzer Scheduled Tests configured for hourly Public iPerf3 testing on the Active Primary WAN" src="https://github.com/user-attachments/assets/d281524a-8191-4a19-aa07-97f5044f6440" />

For Public iPerf3 schedules, select the Scheduled Region and server independently from the manual test configuration in Test Center.

A Custom iPerf3 server cannot be scheduled.

The same device and engine compatibility rules used for manual testing apply to Scheduled Tests. A hard-disabled combination cannot be saved as a scheduled job.

iPerf3 Scheduled Tests can optionally capture **Jitter**. TCP RTT is collected automatically for iPerf3 whether Jitter is enabled or disabled. Netperf continues to use the **Latency/Jitter** option.

### Enable Schedule and Auto-start on boot

**Enable Schedule** and **Auto-start on boot** are independent settings, and both are saved
across application and router restarts.

- **Enable Schedule** controls whether the schedule is enabled. Saving an enabled schedule
  starts it immediately, whether or not Auto-start is selected.
- **Auto-start on boot** controls whether an enabled schedule starts automatically when the
  application starts.

Because they are independent, the Scheduled Tests status can show three states:

- **Active** — the schedule is enabled and currently running.
- **Enabled — Not Running** — the schedule is enabled but is not currently running. This is
  expected after an application or router restart when Auto-start is off: the configuration is
  preserved and **Enable Schedule** stays checked, but the schedule does not resume on its own.
  Click **Save Schedule** to start it now.
- **Disabled** — the schedule is not enabled.

Turning Auto-start off while a schedule is enabled does not stop the current session; the
schedule keeps running until the next restart, at which point it will not start automatically.

## Test Engines

### iPerf3

iPerf3 is bundled with the application and is the recommended general-purpose throughput engine.

User-facing capabilities include:

- TCP Downlink and Uplink testing.
- Primary and validated non-primary WAN testing.
- Public, User, and Custom server workflows.
- Port-range support.
- Automatic retry for eligible listener failures.
- Public same-Region backup behavior when the selected Public server cannot start Downlink after eligible listener failures.
- Automatic TCP RTT reporting.
- Optional Jitter capture for Manual and Scheduled Tests.
- TCP retransmission reporting.
- Actual server and port information recorded in History and CSV.
- Stop/cancellation support.

iPerf3 requires access to an iPerf3 server.

**TCP RTT** is measured while the Uplink throughput test is actively using the connection. Because this is a loaded measurement, it can be higher than idle or pre-test latency reported by other speed-test engines, particularly on cellular WANs.

Enable **Jitter** when you want the iPerf3 test to capture Jitter in addition to its normal throughput and TCP RTT results.

### Netperf

Netperf uses the router's native NCOS speed-test service.

User-facing capabilities include:

- TCP Downlink and Uplink testing.
- Per-WAN testing.
- Optional latency and jitter reporting.
- Native Cradlepoint Netperf infrastructure.
- Automatic safety handling when a native test does not stop normally.

Some platforms have confirmed NCOS Netperf defects. The application disables Netperf only where the matching known-defect rule applies.

### Ookla

Ookla support is optional.

A compatible licensed ARM64 Ookla/Speedtest binary must be included with the application. The distributed app does not include a licensed Ookla binary by default.

Platform behavior should be considered unvalidated unless separately tested.

---

# Servers

Open **Servers** to manage test destinations, select the active iPerf3 server source, maintain saved User endpoints, and review iPerf3 Reliability statistics.

<img width="1356" height="1186" alt="Speedtest Analyzer Server Management showing Public iPerf3 servers, region selection, and endpoint reliability statistics" src="https://github.com/user-attachments/assets/fa660fd0-b018-425c-8a74-0220115c088e" />

## Netperf Servers

Netperf uses the router's native NCOS speed-test service and can operate without maintaining an iPerf3 server list.

The Servers page also provides optional Netperf server management. A Netperf server can be saved with an IP address and an optional descriptive label.

If no custom Netperf server is saved, the application uses the default Netperf service available through NCOS.

Netperf server definitions can be imported or exported from the Servers page.

Netperf server configuration is independent from the iPerf3 **Server List Mode** described below.

## iPerf3 Server List Modes

Speedtest Analyzer provides two persistent iPerf3 server sources:

- **Public iPerf3 Servers**
- **User Server List**

Use the **Server List Mode** selector on the Servers page to choose the active source.

The selected mode controls which saved iPerf3 source is presented to Manual Tests, Scheduled Tests, and the Servers page.

Switching modes preserves both persistent server sources. The inactive source is not deleted.

See **Switching between Public and User modes** below for the effect of a mode change on an existing iPerf3 Scheduled Test.

### Public iPerf3 Servers

**Public iPerf3 Servers** is the default iPerf3 server source for new Speedtest Analyzer installations.

The bundled read-only catalog is organized into five United States regions:

- East
- Southeast
- Midwest
- Southwest
- West

The catalog is sourced from the monitored public server list at `iperf3serverlist.net`.

The application uses the bundled catalog and does not continuously query the external site during normal operation.

Each Public entry can provide information such as:

- Friendly server name
- Hostname or IP address
- Port or port range
- City
- Country
- Region

Public servers are operated by third parties. Availability, load, and individual listener ports can change at any time.

#### Manual Public tests

Manual Public testing provides:

1. Region selection.
2. Friendly server selection within that Region.
3. A **Custom Server** option for one-time testing.

The Region selected for Manual Tests is independent from the Region used by Scheduled Tests.

#### Scheduled Public tests

Scheduled Public testing maintains its own Region and server selection.

Changing the Scheduled Region requires the scheduled server to be selected from the new Region.

**Custom Server is not available for Scheduled Tests.**

### User Server List

Use **User Server List** for private, trusted, or preferred iPerf3 endpoints that should remain saved.

<img width="1337" height="505" alt="Speedtest Analyzer User Server List showing saved iPerf3 endpoints and server management controls" src="https://github.com/user-attachments/assets/bb1091f7-96af-4b4b-9b5c-3affbdaf90fd" />

Available management functions include:

- Add Server
- Edit Server
- Delete Server
- Delete All Servers
- Download Server List Template
- Export My Server List
- Import Server List
- Merge Lists
- Replace List

The User Server List remains stored when the application is switched to Public mode.

A saved User endpoint is identified by its:

- Hostname or IP address
- Port or port range

Friendly Name, City, and Country are descriptive metadata.

Editing only Friendly Name, City, or Country preserves the endpoint identity, existing schedule association, and Reliability history.

Changing Hostname/IP or Port/Range changes the endpoint identity. If an existing iPerf3 schedule references that endpoint, the application can require confirmation before resetting the affected schedule.

Duplicate endpoint definitions are not treated as separate saved servers.

### Switching between Public and User modes

To change the active iPerf3 server source:

1. Open **Servers**.
2. Locate **Server List Mode**.
3. Select **Public iPerf3 Servers** or **User Server List**.
4. Review the confirmation warning if an iPerf3 Scheduled Test is currently configured.
5. Confirm the mode change.
6. Return to **Test Center** and select a server from the newly active source before creating a new iPerf3 schedule.

Switching modes changes the active iPerf3 server source but does **not** delete either persistent server source. A saved **User Server List** remains stored while Public mode is active and becomes available again when User mode is selected.

However, an existing iPerf3 Scheduled Test can be tied to a server from the currently active source. If changing Server List Mode would make that scheduled server reference incompatible, Speedtest Analyzer displays a confirmation warning before completing the change.

<img width="471" height="208" alt="Speedtest Analyzer warning that changing iPerf3 server list mode removes the existing scheduled iPerf3 job" src="https://github.com/user-attachments/assets/37d7c0be-017b-4ef5-b753-fee2966c1ceb" />

If the mode change is confirmed, the incompatible iPerf3 Scheduled Test is reset and must be configured again using a server from the newly active source.

Changing iPerf3 Server List Mode does not affect saved server definitions or Netperf Scheduled Tests.

### Custom Server

**Custom Server** is intended for one-time Manual Tests against an iPerf3 endpoint that does not need to be permanently saved.

A Custom Server:

- Is available for Manual iPerf3 testing.
- Is not added to the Public catalog.
- Is not added to the User Server List.
- Cannot be used for Scheduled Tests.
- Is excluded from persistent iPerf3 Reliability statistics.

If you want long-term Reliability statistics for a private or preferred endpoint, add it to the **User Server List** instead.

## Port ranges and retries

A Public or User server can define a single port or a port range.

The application uses a bounded retry strategy and does not endlessly scan a configured range.

Eligible listener problems, such as a busy or unavailable iPerf3 listener, can move the test to another unused port.

Generic WAN, DNS, routing, timeout, or system failures are not treated as listener failures.

For Public mode, one same-Region backup server can be attempted when the original server exhausts its eligible Downlink listener attempts before throughput begins.

User Server List tests remain locked to the configured endpoint and do not automatically move to another User server.

After Downlink succeeds, Uplink remains on the successful server and tries the successful Downlink port first.

## iPerf3 Reliability

The Servers page provides lightweight Reliability statistics for saved Public or User iPerf3 endpoints.

Reliability information is maintained for the active persistent server source and includes:

- Successful Tests
- Endpoint Failures
- Failure Rate
- Most Failed Port

Only listener-attributable endpoint failures are counted.

WAN, DNS, routing, generic timeout, and system failures are excluded so the Reliability metric is not presented as a general WAN-success score.

Custom Server tests are excluded because they do not have a stable saved server identity.

Resetting Reliability statistics affects only the currently active Public or User Reliability source and does not delete saved server definitions.

---

# Cellular Analysis

**Cellular Analysis** turns retained cellular test history into a view of how the router has actually been using the cellular network over time.

Instead of looking at one final modem snapshot from one speed test, the page combines retained serving-cell identity, network mode, RF conditions, carrier activity, and radio configuration so you can see:

- Which serving cells the device has used.
- How often each serving cell was observed.
- How much active test traffic occurred on each cell.
- When the device changed between serving cells.
- Whether radio configuration, available bandwidth, or network mode changed.
- The RF conditions associated with a selected serving cell.
- The strongest radio configurations observed while traffic was active.

Cellular Analysis uses data already retained by Speedtest Analyzer. It does not continuously poll the modem outside normal test activity.

The page is divided into two scopes:

- **Site Cellular GeoView** provides site-wide context across all retained cellular interfaces and history.
- The lower **Cellular Analysis workspace** lets you select a specific cellular interface and history range for detailed analysis.

## Site Cellular GeoView

**Site Cellular GeoView** appears at the top of the Cellular Analysis page and summarizes the identifiable serving cells observed across all retained cellular interfaces.

The default **Local Only** mode requires no external geolocation service.

In Local Only mode, GeoView shows:

- The Site.
- Each identifiable serving cell observed in retained history.
- The number of serving cells, carriers, and cellular interfaces observed.
- Which interfaces have seen the same serving cell.
- Carrier-aware serving-cell markers.
- A local serving-cell schematic.

The local schematic is intentionally **not geographic**. Marker placement shows the observed serving-cell inventory and Site relationship without claiming that the displayed marker position represents the physical tower location.

<img width="1277" height="680" alt="Local GeoView with observed serving cells]" src="https://github.com/user-attachments/assets/3f005b48-29d0-4a43-a1e6-f594b3486902" />

GeoView is site-wide. It does not change when you select a different Interface or History Range in the lower Cellular Analysis workspace.

### Configure GeoView

Select **Configure** to choose how Site context is maintained.

**Local Only** remains fully functional without Google Maps or OpenCellID.

A Site Location can still be configured in Local Only mode using:

- **Device GPS** — queries the router GPS only when requested.
- **Manual Site Location** — enter a Site Address, or use latitude/longitude through Advanced coordinates.

Saved Site Location information is retained independently from the optional Geolocation Services feature.

Device GPS is not continuously polled. Selecting **Refresh GPS** performs one explicit request to the router.

<img width="872" height="712" alt="Configure GeoView with Site Location options" src="https://github.com/user-attachments/assets/4a032eb7-9bbf-4cdb-8197-8797c1bb1da7" />

## Cellular Overview

The lower Cellular Analysis workspace begins with an **Interface** and **History Range** selector.

Use these controls to decide which retained cellular tests should be analyzed.

The **Cellular Overview** summarizes the selected scope with:

- **Tests Analyzed** — the number of retained tests included in the analysis.
- **Serving Cells Observed** — the number of identifiable serving cells used during those tests.
- **Network Mode** — the technology mix observed, such as LTE, 5G NSA, or 5G SA.

This provides a quick indication of whether the selected cellular connection has remained on one network resource or has moved between multiple serving cells or technologies.

## Serving Cell Distribution and Timeline

**Serving Cell Distribution** shows how the selected cellular interface used each identifiable serving cell.

Each cell receives a simple label such as **A**, **B**, or **C** while the underlying Cell ID, PCI, TAC, serving role, and band remain visible.

Two measurements help describe how each cell was used:

- **Tests Seen** — how many retained tests observed that serving cell.
- **Active Traffic** — the percentage of measured Download/Upload traffic time associated with that cell when timed in-test telemetry is available.

A single test can observe more than one serving cell, so **Tests Seen** is not intended to total 100%.

**Active Traffic** is mutually exclusive and better represents where the device spent its measured test traffic time.

The **Serving Cell Timeline** shows the chronological serving-cell history across the selected time range. Changes between A, B, C, and later cells make long-term attachment behavior easy to identify.

In-test handoff markers can also appear when Speedtest Analyzer observed a serving-cell transition while traffic was actively running.

<img width="1264" height="560" alt="Cellular Overview with serving-cell distribution and timeline" src="https://github.com/user-attachments/assets/64c1b617-a930-4e83-993f-32e492fc55f8" />

## Cellular Change Activity

**Cellular Change Activity** summarizes how dynamic the selected cellular connection has been.

The page tracks:

- **Serving Cell Changes** — changes between identifiable serving cells.
- **Peak Config Changes** — changes in the strongest radio configuration observed during active traffic.
- **Bandwidth Changes** — changes in observed serving-carrier bandwidth.
- **Network Mode Changes** — transitions between LTE, 5G NSA, and 5G SA.

These measurements help distinguish a connection that stays on a stable radio environment from one that frequently changes serving resources or radio configuration.

A change does not automatically indicate a problem. Cellular networks routinely change cells, bands, and carrier combinations based on mobility, RF conditions, traffic demand, and network decisions.

## Serving Cell Details

Use the **Serving Cell** selector to inspect one identified serving cell at a time.

**Serving Cell Details** can include:

- Carrier.
- Serving role and primary band.
- Cell ID.
- PLMN.
- TAC.
- PCI.
- Channel.
- First Seen and Last Seen.
- Tests Seen.
- Active Traffic percentage.

This lets an operator move from the high-level distribution and timeline into the specific network identity behind Cell A, B, C, and later observations.

## RF Conditions

**RF Conditions** summarizes retained radio measurements associated with the selected serving cell.

Available values can include:

- Average RSRP.
- Average RSRQ.
- Average SINR.
- Best and worst retained measurements.
- Cellular Health observations.

RF values are associated with the selected serving cell rather than simply using the final modem state from the most recent test.

This is useful when comparing whether different serving cells were observed under meaningfully different radio conditions.

## Radio Resource Summary

**Radio Resource Summary** shows how the modem was configured while active test traffic was running.

The section includes:

- **Technology Usage** — the network modes observed for the selected serving cell.
- **Peak Observed Radio Configurations** — the strongest valid component-carrier combinations observed during active test traffic.
- Total observed Downlink bandwidth.
- Number of tests where each configuration was observed.
- Relative usage of each configuration.

For example, two tests can use the same LTE anchor serving cell while activating different LTE or 5G NR secondary carriers.

Peak Observed Radio Configuration describes what the modem reported during active traffic. It does not claim that every displayed carrier carried an equal portion of the speed-test traffic.

<img width="1262" height="782" alt="Cellular Analysis details with RF and radio resource summary" src="https://github.com/user-attachments/assets/d3ed30ff-b57e-476f-a858-0dfc299bf841" />

## Optional Geolocation Services

Cellular Analysis does not require an external geolocation service.

When **Geolocation Services** is enabled, GeoView can add geographic context to the serving-cell inventory using:

- **OpenCellID** — estimated serving-cell locations.
- **Google Maps JavaScript API** — interactive geographic map.
- **Google Geocoding API** — converts a manually entered Site Address into Site coordinates.

GeoView estimates the location of the **serving cellular infrastructure** observed by the router. The Site location remains a separate reference point supplied by Device GPS, Site Address, or Manual Coordinates.

Speedtest Analyzer resolves only the independently identifiable primary serving radio:

- **LTE Only** — LTE primary serving cell.
- **5G NSA** — LTE anchor.
- **5G SA** — NR primary serving cell.

A complete serving-cell identity is required. PCI, band, and channel values are not used as substitutes for a missing Cell ID.

### Google API Key Setup

GeoView uses **two separate Google Maps Platform API keys** so the server-side Site Address lookup and browser-based interactive map can be restricted independently.

A Google Cloud project with **billing enabled** is required for Google Maps Platform. Google recommends restricting API keys to only the applications and APIs that require them.

**Google Server API Key**

Used only when Speedtest Analyzer converts a manually entered **Site Address** into coordinates.

1. Enable the **Geocoding API** in your Google Cloud project.
2. Create an API key.
3. Restrict the key to the **Geocoding API**.
4. When the deployment has predictable public egress, consider an appropriate server-side IP restriction.
5. Enter the key in **Google Server API Key** under Configure GeoView.

[Google: Set up the Geocoding API](https://developers.google.com/maps/documentation/geocoding/get-api-key-v4)

**Google Maps JavaScript API Key**

Used by the browser to render the interactive geographic GeoView.

1. Enable the **Maps JavaScript API** in your Google Cloud project.
2. Create a **separate** API key.
3. Restrict the key to the **Maps JavaScript API**.
4. Apply Website/HTTP-referrer restrictions appropriate to how Speedtest Analyzer is accessed when practical.
5. Enter the key in **Google Maps JavaScript API Key** under Configure GeoView.

[Google: Set up the Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/get-api-key)

[Google Maps Platform API security guidance](https://developers.google.com/maps/api-security-best-practices)

The Google Server key is stored in protected Device-scoped NCOS credential storage. The Maps JavaScript key is kept separate because it must be supplied to the browser when the interactive map is loaded.

For safest credential entry, access Speedtest Analyzer through **NCM LAN Manager** when available.

### Resolve Cell Locations

Select **Resolve Cell Locations** when you want Speedtest Analyzer to request estimated locations for eligible serving cells.

Previously resolved locations are cached so the application does not need to request the same information every time Cellular Analysis is opened.

When geographic locations are available, the interactive map can show:

- The configured Site.
- Estimated serving-cell markers.
- Site-to-cell relationship lines.
- Carrier-aware marker colors.
- Distance and direction from the Site.
- Serving-cell information and retained usage.

<img width="1254" height="601" alt="GeoView with resolved serving-cell locations" src="https://github.com/user-attachments/assets/9edb38ed-be3c-4641-971f-80d811faf0d0" />

## OpenCellID Contributions

OpenCellID contribution is optional and **Off by default**.

When enabled, Speedtest Analyzer can contribute the geographic position where an eligible serving cell was observed by the router.

It does **not** submit the OpenCellID estimated serving-cell coordinates as an observation.

Contribution supports eligible primary serving-cell observations from internal or captive cellular modems and uses either Device GPS or a validated Manual Site Location.

A persistent deduplication record prevents repeated contribution of the same serving cell from effectively the same location.

## Exporting Cellular Analysis

Select **Export HTML Report** to create a self-contained report of the currently selected Cellular Analysis scope.

The report preserves the selected interface and history range and includes the Cellular Overview, Serving Cell Distribution and Timeline, Change Activity, RF conditions, radio-resource information, and geographic context when available.

Unlike the interactive application, where you select one serving cell at a time for detailed analysis, the exported report includes the available detail sections for **all identifiable serving cells** in the selected scope. This makes the report easier to review, share, or archive without requiring the reader to interact with the live application.

When geographic GeoView data is available, the live Google map is replaced with a self-contained Site/serving-cell schematic showing the Site, resolved serving-cell locations, distance and direction, and serving-cell location details. The exported report does not require Google Maps, provider credentials, Internet access, or continued access to the router.

Unknown serving-cell observations remain represented in the overview, distribution, and timeline when identity data is incomplete, but Speedtest Analyzer does not create a detailed serving-cell section for an unidentified cell.

Open the exported HTML file in a browser and use **Print → Save as PDF** when a PDF copy is required.

<img width="1331" height="507" alt="Cellular Analysis export with serving-cell location schematic" src="https://github.com/user-attachments/assets/8bd65e64-9a4c-4191-a882-1086bdf6c5d8" />

---

# History & Reports

**History & Reports** contains completed, partial, and failed tests.

Depending on the engine and WAN, information can include:

- Downlink throughput
- Uplink throughput
- Latency or iPerf3 TCP RTT
- Jitter
- iPerf3 TCP retransmissions
- Data transferred
- WAN/interface used
- Test engine
- Actual iPerf3 server and ports
- Test time
- Cellular Health
- Band change
- Tower change
- Carrier Activity
- Final cellular radio information
- Success, Partial, or Failed status

## Test Summary

The Test Summary includes a **Date Range** control with:

- All History
- Last 12 Hours
- Last 24 Hours
- Last 3 Days
- Older than 3 Days

The selected range updates Summary tiles, Trends, per-engine statistics, and speed graphs before the existing interface filters are applied.

Each interface filter group always retains at least one selected interface.

<img width="1629" height="609" alt="Speedtest Analyzer History and Reports all-tests summary with WAN filters and aggregate statistics" src="https://github.com/user-attachments/assets/9561853a-c41d-4c99-b575-1812cb3c73c1" />

<img width="1333" height="818" alt="Speedtest Analyzer trend analysis comparing iPerf3 and Netperf across Ethernet and cellular WAN interfaces" src="https://github.com/user-attachments/assets/e2d68d9d-2af8-4073-ba06-856f0aa3ce7b" />


## Test Log

The Test Log provides independent filters for:

- **Interfaces**
- **Status** — Complete, Partial, or Failed
- **Date**
- **Reset**

Pagination can display:

- 10
- 25
- 50
- 100

matching results per page, with the newest 10 shown by default.

The Test Summary Date Range and Test Log filters are independent.

<img width="1336" height="546" alt="Speedtest Analyzer Test Log with interface, status, date filters, cellular details, and pagination" src="https://github.com/user-attachments/assets/7da3bd05-2ee0-4fe7-83c0-1523db362af4" />


## Time display

History timestamps are stored in UTC and displayed using the viewer's browser timezone and normal regional 12-hour or 24-hour convention.

Test Log timestamps, Summary range dates, graph timestamps, and graph tooltips display browser-local time.

CSV exports remain in UTC for portability and consistent downstream processing.

## Graphs and expandable details

Throughput history is displayed using connected Downlink and Uplink line graphs.

<img width="1326" height="787" alt="Speedtest Analyzer iPerf3 throughput history showing Downlink and Upload trends over time" src="https://github.com/user-attachments/assets/b7f151e0-a2a9-4ecc-b54c-c4e9ff9b6665" />


Graph points provide immediate details and identify the friendly WAN interface associated with each plotted result.

The Test Log provides expandable details for items such as:

- Engine
- Status
- Carrier Aggregation
- Cell Stats

Only one detail section is open for a given test at a time, while details from different tests can remain open for comparison.

## Carrier Activity Details

For successful cellular tests, the **CA** field in the Test Log can be expanded.

The detailed view is organized into **Baseline**, **Progress**, and **Peak**:

- **Baseline** — the last known carrier state immediately before successful throughput begins.
- **Progress** — carrier information observed during successful Downlink and Uplink traffic.
- **Peak** — the strongest carrier state observed during successful traffic.

<img width="1322" height="637" alt="Speedtest Analyzer Carrier Activity detail showing Baseline, Progress, Peak, and uplink CA limitations" src="https://github.com/user-attachments/assets/5f1e8946-008c-4d19-8b98-fff8b4c5e58c" />

Setup delays, failed iPerf3 listener attempts, and unsuccessful throughput attempts are not promoted into the successful traffic timeline.

### Observed Downlink Bandwidth

**Observed Downlink Bandwidth** is the sum of positive bandwidth values reported for active RX/downlink serving carriers.

It describes modem-reported serving-carrier bandwidth. It is **not** the measured speed-test throughput and does not prove that every displayed carrier carried test traffic.

An active carrier explicitly reporting `0 MHz` remains part of the active-carrier count but contributes zero to the bandwidth total.

### Uplink Carrier Aggregation

NCOS currently does not expose the TX-channel and uplink component-carrier information required for the app to determine active Uplink CA.

The detailed result can therefore show an **Observed Uplink Anchor** and a **Published Maximum Uplink CA** reference, but it does not claim to show active Uplink CA.

When displayed:

- **Observed Uplink Anchor** is a serving-carrier observation captured during Uplink traffic.
- **Current Uplink CA: Not reported by NCOS** means active uplink component-carrier participation cannot currently be determined.
- **Published Maximum Uplink CA** is a modem capability reference, not a measurement of currently active uplink carriers.

### Published modem capabilities

When a supported modem variant is identified, the expanded Carrier Activity view can show published LTE, 5G NSA, and 5G SA maximum Carrier Aggregation references.

These are capability references only. They do not change or override the serving carriers observed during a test.

If the device model is known but the exact modem variant cannot be confirmed, the application can show available published variants so the user can identify the correct one manually.

## Reports and Exports

Supported report formats include:

- CSV
- HTML

### HTML reports

HTML reports honor the interface selections currently applied in the **All Test Summary**.

If the All Test Summary is filtered to one or more specific interfaces, the HTML report is generated using only those selected interfaces. The interface filter is carried throughout the exported report, including summary statistics, trend analysis, graphs, and reported test results.

To include results from all available interfaces, select all desired interfaces in the All Test Summary before generating the HTML report.

Reports can be useful for:

- Comparing WAN performance
- Reviewing performance over time
- Recording failover behavior
- Troubleshooting intermittent connectivity
- Reviewing cellular carrier activation under load
- Sharing results outside the router

CSV exports retain UTC timestamps.

Published modem capability references are intentionally excluded from CSV because they are reference data rather than measurements from the test itself.

---

# Outputs

The **Outputs** page controls whether successful test summaries are written to NCOS-accessible fields.

Multiple outputs can be enabled at the same time.

Available targets may include:

- System Description
- Asset ID
- SDK data
- Custom path

Example result format:

```text
DL:96.82Mbps UL:46.74Mbps Lat:12.5ms Jit:2.1ms Iface:T-Mobile Engine:iperf3 2026-06-13T11:30:00Z
```

Only enable outputs appropriate for your environment.

Writing results to fields such as **System Description** or **Asset ID** changes router configuration data and may not be desirable on production-managed devices.

---

# Settings and Configuration Management

The **Settings** page is the application-wide administration area for Speedtest Analyzer.

Feature configuration — such as Scheduled Tests, Servers, GeoView, and Outputs — remains on the page where that feature is used. Settings is where you review **where those settings come from**, manage Device overrides, and control the relationship between an individual device and its NCM Group configuration.

## How configuration works

Speedtest Analyzer configuration can come from three levels:

- **This Device** — configuration saved locally for one router.
- **NCM Group** — shared configuration applied to devices through an NCM Group.
- **Built-in Default** — the application's default behavior when neither the Device nor Group has configured that area.

Configuration is resolved independently for each setting area using this priority:

**This Device → NCM Group → Built-in Default**

The configurable areas include:

- Scheduled Testing
- Outputs
- iPerf3 Server Mode
- User iPerf3 Servers
- Netperf Servers
- GeoView

This means a device does not have to be entirely Device-managed or entirely Group-managed.

For example, a router can inherit its iPerf3 Server Mode and User Server List from the NCM Group while maintaining its own Scheduled Testing or GeoView configuration.

The **Configuration State** summarizes the overall relationship:

- **Unconfigured** — no Device or Group configuration is saved; Built-in Defaults are in effect.
- **Device Managed** — configuration exists only on this device.
- **NCM Group** — configuration is supplied by the NCM Group with no local Device overrides.
- **NCM Group + Device Overrides** — the device inherits Group configuration but has one or more locally configured areas taking precedence.

The **Effective Configuration Sources** list shows the active source for every configuration area so you can immediately see which settings come from **This Device**, the **NCM Group**, or the **Built-in Default**.

<img width="850" height="375" alt="Configuration sources and management state" src="https://github.com/user-attachments/assets/9ac97339-c627-48d8-b450-95289aaede1f" />

## Device Overrides

When a Group-managed device is changed locally, only the configuration area being changed becomes a **Device Override**.

The Device override takes precedence over the corresponding NCM Group setting while all other configuration areas continue to inherit normally.

For example, a device could have:

- Scheduled Testing from **This Device**
- GeoView from **This Device**
- iPerf3 Server Mode from the **NCM Group**
- User iPerf3 Servers from the **NCM Group**
- Netperf Servers from the **Built-in Default**

The **Device Overrides** section lists each locally configured area, provides a short summary of its current value, and shows where the setting will return if the override is removed.

### Resetting a Device Override

Select **Reset to Group** to remove a Device override and return that configuration area to the value supplied by the NCM Group.

Speedtest Analyzer does not copy the Group configuration over the Device configuration.

Instead, the locally configured section is removed from the Device App Data document. Once that Device override no longer exists, the normal configuration priority automatically exposes the NCM Group value underneath it.

If the NCM Group does not configure that area, the setting returns to the **Built-in Default** instead. The Settings page identifies the reset destination before the change is made.

Resetting one Device override does not affect unrelated Device overrides and never modifies the NCM Group configuration.

If the last remaining Device override is removed, Speedtest Analyzer no longer needs a local Device configuration document and removes the `speedtest_analyzer_device` App Data entry. The device then operates entirely from its NCM Group configuration and Built-in Defaults.

<img width="724" height="391" alt="Device Overrides with Reset to Group controls" src="https://github.com/user-attachments/assets/f961758d-93cf-4149-9770-520b7e98b23d" />

### Reset All Device Overrides

**Reset All Device Overrides** removes every locally configured override at once.

After the Device overrides are removed, each configuration area is supplied by the NCM Group when that section exists there, or by the Built-in Default when it does not.

Some configuration areas depend on one another. For example, a scheduled iPerf3 test can depend on the configured iPerf3 Server Mode.

If resetting one area by itself would create an incompatible configuration, Speedtest Analyzer explains the dependency and offers to reset the related areas together. You can cancel the operation without making any changes.

## Update NCM Group Configuration

When a device is already Group-managed and has Device overrides, **Update NCM Group Configuration** can be used to promote selected Device settings into the existing NCM Group standard.

This is useful when a setting was first tested or customized on one device and you later decide that it should become the standard for the entire Group.

The wizard shows the current Device overrides and lets you choose which ones should be promoted.

Selected areas are added to or replace the corresponding areas in the Group configuration.

Areas that are not selected:

- remain Device overrides;
- do not modify the existing Group value;
- continue to take precedence only on that device.

The wizard controls **where configuration is stored**. It does not provide another place to edit the underlying feature values.

<img width="811" height="312" alt="Update NCM Group Configuration wizard" src="https://github.com/user-attachments/assets/74182d33-d871-44a7-9c5c-e028d6302727" />

Speedtest Analyzer does not directly write the NCM Group configuration. Instead, the wizard generates the complete revised Group JSON for you to apply in NCM.

The workflow is:

1. Select the Device overrides that should become part of the NCM Group standard.
2. Review which settings will be promoted, which existing Group settings will remain unchanged, and which settings will stay as Device overrides.
3. Generate the revised Group configuration.
4. Update the existing `speedtest_analyzer_group` SDK Data value in the NCM Group with the generated JSON.
5. Return to Speedtest Analyzer and select **Validate**.
6. After the new Group configuration is confirmed on the device, Speedtest Analyzer removes the promoted sections from the local Device configuration.

Once the promoted Device sections are removed, those settings are supplied by the NCM Group instead.

This preserves the normal configuration hierarchy rather than keeping duplicate copies of the same setting at both Device and Group scope.

### GeoView promotion safety

GeoView includes device-specific location information that should not automatically become a shared Group value.

A **Device GPS location policy** can be promoted to the Group, but actual GPS coordinates are not copied into the Group configuration.

Manually entered Site Addresses and Manual Coordinates are also device-specific and are not promoted as shared Group location data.

If GeoView contains a location configuration that cannot safely be promoted, the wizard explains what must be changed before that section can become part of the Group standard.

If the Device or Group configuration changes while the wizard is open, Speedtest Analyzer stops the workflow and requires it to be restarted. This prevents an older staged configuration from overwriting newer changes.

## Migrate to NCM Group

**Migrate to NCM Group** is used when a router is currently **Device Managed** and no NCM Group configuration exists yet.

This is the first-time workflow for turning an existing Device configuration into a shared Group standard.

The migration process prepares the Device configuration for use as the new NCM Group configuration, provides the Group JSON that must be applied through NCM, and then validates that the Group configuration has arrived on the device.

After the Group configuration is successfully validated, the corresponding local Device configuration is removed so the router begins inheriting those settings from the NCM Group.

A device that is already Group-managed does not use **Migrate to NCM Group**. It uses **Update NCM Group Configuration** to promote new Device overrides into the existing Group standard.

## Configuration from an earlier version

If Speedtest Analyzer detects configuration created by an earlier application version that has not yet been converted to the current configuration format, the Settings page displays **Configuration Upgrade Required**.

Existing configuration remains active while the upgrade is pending, and normal testing, history, and reporting continue to operate.

Configuration changes are temporarily paused until **Convert Configuration** is used to create the current Device configuration format.

The conversion process preserves the existing settings rather than requiring the application to be configured again from scratch.

## Factory Reset

**Factory Reset** is a separate destructive operation and is intentionally kept apart from normal Device Override controls.

Factory Reset removes Speedtest Analyzer's locally stored configuration, Device overrides, and local test history while leaving the application installed.

Factory Reset does **not** remove or modify the NCM Group configuration.

If the router belongs to an NCM Group, the Group configuration becomes effective again after the local Device data is cleared.

---

# Basic Troubleshooting

## Web interface does not open

If using NCM LAN Manager:

- Verify the SDK app is running.
- Verify LAN Manager can reach the device.

If connecting directly from the local LAN:

- Verify the SDK app is running.
- Verify the client is behind the router.
- Verify Primary LAN Zone to Router Zone forwarding is allowed.
- Verify Router Zone to Primary LAN Zone forwarding is allowed.
- Verify TCP port `8000` is reachable.

## iPerf3 cannot connect

Check:

- Selected server
- Hostname/IP
- Server availability
- Configured port or port range
- Internet connectivity from the selected WAN

A failed public listener does not automatically mean the WAN is down. Public servers can be busy or unavailable.

The application can retry eligible listener failures, but it deliberately does not hide general WAN, DNS, routing, or system failures behind repeated port attempts.

## A test engine is disabled

Review the **Known engine limitations** table near the top of this README.

The application can disable an engine for a specific platform or controller + captive-modem combination when a confirmed defect is known.

## Selected secondary WAN cannot be tested

Verify that the selected WAN is connected and has a valid IPv4 address and gateway.

The application will not silently run the test over another WAN when the explicitly selected path cannot be established.

Some platforms may not support the additional routing behavior required for non-primary iPerf3 steering.

## Netperf reports no WAN connection

Confirm that the selected WAN remains connected for the full test.

A cellular reconnect, SIM event, carrier transition, or WAN link-down can cause native NCOS Netperf to reject or terminate the test.

## Carrier Activity does not show additional carriers

Carrier Aggregation and 5G activation are controlled by the modem and network.

Additional carriers may activate only when traffic demand, radio conditions, subscription, network configuration, and tower capabilities support them.

The app reports the serving state exposed by NCOS; it does not force additional carriers to activate.

For detailed troubleshooting and implementation behavior, see [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).

---

# Requirements

- Cradlepoint router capable of running the SDK application
- NCOS 7.26.x recommended
- ARM64/aarch64 platform for the bundled iPerf3 binary
- LAN-to-Router firewall access for TCP port `8000`
- Reachable iPerf3 endpoint when using iPerf3
- Internet access to the native Cradlepoint Netperf service when using Netperf
- Compatible licensed Ookla binary for optional Ookla testing

---

# Documentation

- **README.md** — normal installation, configuration, operation, result interpretation, platform validation, common troubleshooting, and the current release-family changelog.
- **TECHNICAL_GUIDE.md** — implementation behavior, advanced platform details, validation and defect logic, Carrier Activity internals, iPerf3 routing and server architecture, Netperf lifecycle protection, persistence behavior, advanced troubleshooting, and the complete engineering changelog.

---

# Changelog — 1.x

The README keeps a concise, user-facing changelog for the current Speedtest Analyzer `1.1.x` release family. The complete engineering history, including the pre-release Speed Test 2.x development lineage, is maintained in [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).

## v1.1.3

- Added **Geolocation Services** to Site Cellular GeoView while preserving **Local Only** as the no-external-lookup mode.
- Added OpenCellID **Estimated Serving Cell Location** resolution using the complete primary serving identity: LTE primary for LTE-only, LTE anchor for NSA, and NR primary for SA. PCI, band, and channel values are never substituted for ECI/NCI.
- Added the interactive **Google Maps JavaScript** GeoView with Site and resolved serving-cell markers, carrier-aware styling, Site-to-cell distance/direction, marker popups, and multi-cell presentation.
- Added **Google Site Address geocoding** on Save using a separate server-side Google key.
- Added split encrypted Device credential storage for the Google Server key, Google Maps JavaScript key, and OpenCellID key using NCOS `certmgmt` and on-router `cp.decrypt()`.
- Added the persistent OpenCellID serving-cell cache with 30-day resolved and 6-hour `not_found` defaults.
- Added optional **OpenCellID Contributions**, Off by default, with Device-GPS automatic contribution after eligible completed cellular tests, Manual Site Location contribution from retained history, Internal/Captive-only eligibility, and a persistent 20-meter same-cell dedupe ledger.
- Added **Reset Credentials** to clear all three GeoView credentials, turn contribution Off, and return to Local Only while preserving Site Location, history, and cached serving-cell locations.
- Updated Cellular Analysis HTML/PDF export to replace the live Google map with a self-contained SVG Site/serving-cell schematic containing no provider credentials or external Google runtime assets.
- Validated live multi-cell resolution and contribution behavior on the E400, including two distinct T-Mobile serving-cell locations and successful multi-cell OpenCellID contribution.
- Added automatic iPerf3 **TCP RTT** and TCP retransmission reporting.
- Added the ability to capture **Jitter** for Manual and Scheduled iPerf3 tests.
- Updated live results, History, and CSV reporting for the new iPerf3 measurements.

## v1.1.2

- Added the **Settings** page for application-wide administration, including Configuration State, per-area Effective Configuration Sources, Device Overrides, and configuration actions.
- Introduced **NCM Group + Device** configuration: each setting area uses the local Device value when set, otherwise the NCM Group value, otherwise the built-in default.
- Added **Update NCM Group Configuration** to promote selected Device overrides into an existing NCM Group standard, with a guided wizard that generates the revised Group JSON to apply in NCM and then removes the promoted local overrides after the Group is validated.
- Added dependency-aware **Reset**: resetting a setting area that would create an incompatible combination (such as a scheduled iPerf3 test versus the iPerf3 Server Mode) now asks to reset the related areas together, and reset messages name the correct destination (**NCM Group** or **Built-in Default**).
- Preserved the GeoView safety boundary during promotion: a Device GPS *policy* can be promoted, but actual GPS coordinates, manual coordinates, and site address remain device-specific.
- Clarified scheduler behavior: **Enable Schedule** and **Auto-start on boot** are independent. Saving an enabled schedule starts it immediately; after a restart with Auto-start off, the schedule stays configured and enabled but shows **Enabled — Not Running** until saved again. The status now distinguishes **Active**, **Enabled — Not Running**, and **Disabled**.
- Added **Factory Reset** as a separate destructive action that clears local Speedtest Analyzer data and history without removing the NCM Group configuration.
- Adjusted the Settings Device Overrides layout to be left-aligned and responsive, with the reset action beside each override title.
- This release was validated on a real E400 across User and Public iPerf3 server modes and Group- and Device-managed states.

## v1.1.1

- Added **Site Cellular GeoView** as the site-wide view at the top of Cellular Analysis.
- GeoView inventories identifiable serving cells across **all retained cellular interfaces and retained history**, independently from the lower Interface and History Range filters.
- Added a lightweight **local observation schematic** that requires no mapping framework and explicitly does not represent geographic cell position.
- Added carrier-aware serving-cell markers and carrier filters. All observed carriers start selected, deselected carriers and cells are dimmed, dimmed cells are non-interactive, and at least one carrier must remain selected.
- Added compact serving-cell popups with carrier, service role/band, Cell ID, PLMN, TAC, PCI, and **Observed Via** interface/test counts.
- Added aggregation of the same serving-cell identity across multiple cellular interfaces while retaining per-interface observation counts.
- Preserved handoff-only serving cells in the site-wide GeoView inventory and continued to exclude plain Ethernet history.
- Added **Configure GeoView** with provider-independent Site Location options for Device GPS, Manual Coordinates, or literal Site Address.
- Added explicit on-demand **Refresh GPS** behavior. GeoView does not continuously poll GPS.
- Added persistent GeoView configuration using NCOS SDK appdata, including independently retained Device GPS, Manual Coordinates, and Site Address values.
- **No Geo Provider** remains fully functional and performs no external cellular-location requests.
- Google and Unwired provider choices are shown as **Research Pending** and remain disabled in v1.1.1.
- v1.1.1 does not include provider API keys, address geocoding, external cell-location lookup, provider-derived geographic estimates, or provider map rendering.

## v1.1.0

- Added the new **Cellular Analysis** workspace for historical cellular-resource analysis using telemetry retained with Speedtest Analyzer test results.
- Added per-cellular-interface and retained-history analysis for **Serving Cell Distribution**, **Serving Cell Timeline**, **Cellular Change Activity**, **Serving Cell Details**, **RF Conditions**, **Technology Usage**, and **Peak Observed Radio Configurations**.
- Added explicit **LTE Only**, **LTE + 5G NR (NSA)**, and **5G SA** handling with mode-aware serving-primary and secondary-carrier presentation.
- Extended active-traffic telemetry so serving-cell identity is retained throughout Download and Upload instead of relying only on the final post-test cellular snapshot.
- Added traffic-aware serving-cell analysis that preserves cells observed only during an in-test handoff and does not invent transitions through unidentified telemetry.
- Added thin **in-test serving-cell handoff markers** to the long-term Serving Cell Timeline without representing temporary handoffs as false multi-hour attachment periods.
- Updated Serving Cell Distribution to distinguish **Tests Seen** from mutually exclusive **Active Traffic** percentage when timed traffic telemetry is available.
- Added selected-cell RF and radio-configuration analysis so each serving cell uses its own matching PCell/anchor telemetry and observed Peak configuration.
- Added conditional **+2 / +4 / +6 second post-test serving-cell stabilization checks** only after an identifiable in-test handoff, allowing the application to classify the post-test state as persisted, reverted, continued handoff, unstable, or inconclusive without adding continuous polling.
- Redesigned **History & Reports** cellular details into **Connection Health**, **Network**, and **Serving Cell** sections with Cell ID, PLMN, TAC, PCI, and mode-aware LTE/NR Channel reporting.
- Added transition-only **Serving Cell Activity** details to History & Reports, including Start, in-test handoff timing, End, and post-test stabilization status.
- Expanded CSV export with normalized **Cell ID**, **PLMN**, **TAC**, **PCI**, LTE/NR Channel fields, and a single chronological **Serving Cell Activity** field.
- Hardened local test-history persistence with atomic writes, flush/fsync, last-known-good backup recovery, corrupt-history protection, serialized history transactions, and the existing rolling 100-result retention behavior.
- Peak Observed radio configuration remains limited to valid active-traffic observations, and secondary-carrier telemetry is not interpreted as unsupported upload carrier aggregation.

## v1.0.2

- Corrected cellular telemetry handling for **5G Standalone (SA)** so the NR serving PCell is represented as the primary carrier instead of being mislabeled as an LTE anchor.
- Made live cellular radio details service-mode aware: LTE and 5G NSA retain the LTE / 5G NR presentation, while 5G SA displays the NR PCell and the first reported NR secondary carrier when available.
- Updated Carrier Activity and CSV labels to use **PCell (LTE Anchor)** only for 5G NSA and **PCell (Primary)** for LTE-only and 5G SA connections.
- Preserved native NCOS secondary-carrier numbering as **SCell0**, **SCell1**, **SCell2**, and later indexed carriers.
- Corrected mixed LTE/NR carrier normalization, duplicate physical-carrier handling, same-band carriers on different channels, and active carriers reporting `0 MHz`.
- Updated **Published Maximum Uplink CA** to use the modem capability configuration for the connection's current service mode.
- On 5G SA connections, **Cell Tower ID** and **Physical Cell ID** now prefer `NR_CELL_ID` and `PHY_CELL_ID_5G` when reported by NCOS, with existing generic identifiers retained as fallbacks.
- Throughput engines, WAN selection and routing, scheduling, server management, result persistence, and SDK appdata architecture are unchanged.

## v1.0.1

- Updated the Manual Tests WAN selector to match Scheduled Tests: **Active Primary WAN** remains the default, while each connected WAN interface is also selectable even on single-WAN devices.
- Kept the Manual Tests WAN selector enabled whenever at least one WAN interface is available; it is disabled only when no WAN exists or while a Manual Test is running.
- Moved the Light/Dark mode control out of the sidebar navigation and into the top-right device header beside Firmware.
- Replaced the theme menu label with the existing moon/sun icon and added an immediate hover/focus tooltip that identifies the view the button will switch to.
- Preserved the existing theme preference in browser local storage.

**Documentation updates:**

- Expanded the README with strategic screenshots covering Test Center configuration, live cellular results, Scheduled Tests, Public and User server management, server-mode switching, History & Reports, throughput graphs, Test Log filtering, and Carrier Activity details.
- Reorganized and expanded the Test Center, Test Engines, Servers, and History & Reports documentation to better match the application workflow and explain Public/User server modes, scheduled-test reset behavior, server reliability, and Carrier Activity interpretation.
- Clarified that HTML reports honor the interfaces selected in the All Test Summary and apply those interface filters throughout the generated report.
- Added guidance noting that device names, WAN labels, and private IP addresses shown in screenshots are example lab values and will vary by deployment.
- These documentation updates do not change backend APIs, test-engine behavior, scheduling, WAN resolution, routing, history, persistence, or SDK appdata behavior.

## v1.0.0

- Rebranded the application from **Speed Test** to **Speedtest Analyzer** and established a fresh `1.0.0` product version baseline before external publication.
- Introduced the new Speedtest Analyzer visual identity with a lightweight inline SVG gauge and performance-waveform mark.
- Added theme-aware branding optimized independently for Light Mode and Dark Mode.
- Updated the expanded sidebar to show the Speedtest Analyzer logo, product name, and version.
- Updated the collapsed sidebar to use the standalone application mark without the product name or version.
- Repositioned the collapsed sidebar expand control so it no longer overlaps or competes with the application logo.
- Replaced the top application header with the new **Speedtest Analyzer** wordmark.
- Renamed the primary **Manual Tests** navigation entry to **Test Center** to reflect that the page contains both Manual and Scheduled test configuration.
- Established the new `speedtest_analyzer` SDK package identity while preserving the existing backend appdata keys and data architecture.
- Updated report and export branding to use the Speedtest Analyzer product identity.
- Preserved the validated throughput engines, WAN-selection behavior, scheduling, history, cellular telemetry, Carrier Activity, server architecture, reliability tracking, validation logic, and existing backend/API implementation from the pre-release 2.7.6 baseline.
- Speedtest Analyzer 1.0.0 continues the engineering lineage of the unreleased **Speed Test 2.7.6** development build; the complete earlier engineering changelog remains in the Technical Guide.

---

# Validation Scope

Compatibility information reflects testing performed against the specific firmware versions listed in this README.

A later NCOS release may change native routing, Netperf, WAN, modem-diagnostic, or SDK behavior. When deploying to a different firmware version or device family, validate the required test engines manually before relying on scheduled or operational results.
