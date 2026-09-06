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

<img width="1414" height="489" alt="Speedtest Analyzer Test Center configured for a Public iPerf3 test" src="https://github.com/user-attachments/assets/075c505c-7003-416e-bedb-d97891c2ce37" />

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

<img width="1331" height="229" alt="Speedtest Analyzer live cellular results showing throughput, cellular health, service type, and Active Carriers" src="https://github.com/user-attachments/assets/2b4a476d-3b38-4249-ba73-fc64ce127b05" />

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

<img width="1317" height="726" alt="Speedtest Analyzer Scheduled Tests configured for hourly Public iPerf3 testing on the Active Primary WAN" src="https://github.com/user-attachments/assets/c55e65ab-f9eb-45e1-a441-f31b91e9f3d4" />

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

**Cellular Analysis** uses cellular telemetry retained with Speedtest Analyzer test history to show which cellular network resources the router has been using over time.

The page is designed for historical radio-resource analysis rather than throughput-correlation conclusions. Throughput can also be influenced by the selected test server, WAN path, internet congestion, server load, and other non-radio conditions.

The lower Cellular Analysis workspace can be scoped by:

- Cellular interface
- Available retained history
- Selected serving cell

Analysis includes:

- Tests Analyzed
- Serving Cells Observed
- LTE / 5G NSA / 5G SA technology usage
- Serving Cell Distribution
- Active Traffic percentage when timed telemetry is available
- Long-term Serving Cell Timeline
- In-test serving-cell handoff markers
- Serving Cell Changes
- Peak Radio Configuration Changes
- Observed Bandwidth Changes
- Network Mode Changes
- Selected-cell identity
- RSRP, RSRQ, and SINR summaries
- Cellular Health observations
- Peak Observed Radio Configurations

A serving cell may appear in more than one test or on more than one cellular interface. **Tests Seen** therefore is not a mutually exclusive percentage. When timed in-test telemetry exists, **Active Traffic** represents the mutually exclusive share of measured Download/Upload traffic time associated with each identifiable serving cell.

Unknown serving-cell observations are preserved when NCOS does not expose enough identity data. The application does not invent a handoff through an unidentified observation.

## Site Cellular GeoView

The top of Cellular Analysis contains **Site Cellular GeoView**. GeoView is intentionally **site-wide**: it uses identifiable serving cells observed across **all retained cellular interfaces and retained history**, independently from the Interface and History Range selections used by the lower Cellular Analysis workspace.

GeoView has two operating modes:

- **Local Only** — keeps Cellular Analysis fully local. No OpenCellID cell-location lookup is performed and no Google map is loaded. The local observation view remains available for the retained serving-cell inventory.
- **Geolocation Services** — adds geographic Site context, OpenCellID **Estimated Serving Cell Locations**, and an interactive Google map when the required credentials are configured.

Serving cells are aggregated by normalized serving-cell identity. If the same serving cell is observed through multiple cellular interfaces, GeoView represents it once while retaining the interfaces that observed it. Cells observed only during a retained in-test handoff remain eligible for the site inventory. Plain Ethernet and other non-cellular history are excluded.

> **GeoView estimates serving-cell locations, not the router location.** The router/Site location is a separate reference point supplied by Device GPS, a manually entered Site Address, or Manual Coordinates.

### Site Context

The **Site Context** panel summarizes:

- Serving Cells
- Carriers
- Cellular Interfaces
- Cell Location Source
- Active Site Location
- Carrier-level cell counts
- Resolved serving-cell details when Geolocation Services is enabled

When estimated locations are available, each resolved cell can show its carrier, primary service role and band, estimated coordinates, and the distance/direction from the configured Site.

### Serving-cell location identity

GeoView resolves only the primary serving identity observed by NCOS:

- **LTE Only** — LTE primary serving cell
- **5G NSA** — LTE anchor
- **5G SA** — NR primary serving cell

A complete MCC/MNC/TAC plus ECI or NCI is required. PCI, band, channel, EARFCN, and NR-ARFCN are never substituted for a missing Cell ID. Secondary/component carriers are not assigned geographic locations unless a complete independent serving identity is available.

## Configure GeoView

Select **Configure** in Site Cellular GeoView to manage GeoView mode, credentials, contribution preference, and Site Location.

### Geolocation mode

- **Local Only** is the default and performs no external serving-cell lookup.
- **Geolocation Services** enables the final v1.1.3 service combination:
  - **OpenCellID** — Estimated Serving Cell Location lookup and optional observation contribution.
  - **Google Maps JavaScript API** — interactive browser map.
  - **Google Geocoding API** — converts a manually entered Site Address into Site coordinates when saved.

Cellular serving-location estimates come from **OpenCellID**.

### Protected credentials

GeoView uses three independent credentials:

- **Google Server API Key** — Site Address geocoding only.
- **Google Maps JavaScript API Key** — interactive browser map only.
- **OpenCellID API Key** — serving-cell lookup and optional contribution.

Credentials are **Device-scoped** in v1.1.3 and are stored in NCOS encrypted certificate-management records rather than normal Speedtest Analyzer App Data.

The Google Server key and OpenCellID key remain server-side. The browser-restricted Maps JavaScript key is returned only through the dedicated map bootstrap path when the map is rendered.

Credential status is shown as Configured or Not Configured; existing secret values are never read back into the form.

For safest credential entry, access Speedtest Analyzer through **NCM LAN Manager** so the device-management session uses the NCM encrypted tunnel.

### Site Location

GeoView supports three Site Location sources. Their saved values are retained independently so switching methods does not erase the others.

#### Device GPS

**Refresh GPS** performs one explicit GPS query. GeoView does not continuously poll GPS.

A Device GPS Site Location is usable only when NCOS reports a valid GPS lock and nonzero coordinates. A later no-lock response does not overwrite previously saved valid coordinates.

When contribution is enabled and Device GPS is the active Site Location source, eligible completed cellular tests can contribute the position where the serving cell was observed automatically.

#### Manual Site Location — Site Address

Enter a Site Address and save GeoView. The address is forward-geocoded to latitude/longitude using the configured **Google Server API Key**.

The resolved Site coordinates are stored with the Site Address and are used for the map, distance/bearing calculations, static report, and manual contribution.

If the address cannot be resolved, use **Advanced: Use coordinates instead**.

#### Manual Site Location — Coordinates

Manual latitude/longitude must be within the normal geographic ranges and cannot use the `0.0, 0.0` no-fix sentinel.

### Resolve Cell Locations

In **Geolocation Services** mode, **Resolve Cell Locations** explicitly resolves eligible serving cells through OpenCellID.

The resolve process:

1. Reads the site-wide retained serving-cell inventory locally.
2. Keeps only cells with a complete eligible LTE/NR primary identity.
3. Reuses a valid cached OpenCellID result when available.
4. Calls OpenCellID only for cache misses that require a lookup.
5. Stores safe resolved or `not_found` results in the persistent GeoView cell-location cache.
6. Returns the updated resolved count to GeoView.

The default cache policy is 30 days for resolved locations and 6 hours for `not_found` results.

Authentication, quota, timeout, network, and provider errors are not persisted as reusable locations.

Provider failures are isolated to GeoView and never prevent Speedtest execution, retained-history access, or local Cellular Analysis.

### Interactive Google map

When Geolocation Services is enabled and a Google Maps JavaScript key is configured, GeoView renders an interactive Google map containing:

- The configured Site marker.
- Resolved serving-cell markers such as A/B/C.
- Site-to-cell relationship lines.
- Carrier-aware marker colors.
- Compact serving-cell popups with primary role/band, **Estimated Serving Cell Location**, distance/direction, and retained test usage.

The distance and direction shown by Speedtest Analyzer are calculated between the configured Site coordinates and the OpenCellID estimated serving-cell coordinates.

OpenCellID `range` metadata is not treated as Site distance or as a location-accuracy radius.

### OpenCellID Contributions

OpenCellID contribution is **Off by default** and must be explicitly enabled.

Contribution sends the geographic position where an eligible serving cell was **observed by the router**. It never submits the OpenCellID estimated serving-cell coordinates.

Eligibility is intentionally narrow:

- Internal or captive cellular modem observations only.
- LTE primary, NSA LTE anchor, or SA NR primary identity only.
- Complete serving identity required.
- Ethernet, Wi-Fi as WAN, satellite, external/generic modem observations, and secondary/component-carrier-only records are excluded.

With **Device GPS**, contribution can occur automatically after a completed eligible cellular test when a valid GPS fix exists.

With **Manual Site Location**, the **Contribute Observations** action scans retained history and submits the most recent eligible observation for each unique primary serving cell using the current validated manual Site coordinates.

A persistent contribution ledger prevents repeated same-cell submissions from nearly the same place.

- The same serving identity is skipped when the new observation is less than 20 meters from its last successfully contributed position.
- Movement of 20 meters or more makes the same serving identity eligible again.
- A different serving cell is eligible immediately.

The ledger is updated only after OpenCellID acknowledges a successful submission and stores no credentials.

### Reset Credentials

**Reset Credentials**:

- Clears the Google Server, Google Maps JavaScript, and OpenCellID keys.
- Turns OpenCellID contribution Off.
- Switches GeoView to **Local Only**.
- Preserves the configured Site Location.
- Preserves Speedtest history.
- Preserves the existing OpenCellID serving-cell location cache.

Preserving the cache allows previously resolved cell locations to be reused if Geolocation Services is configured again later.

## Exporting Cellular Analysis reports

Cellular Analysis includes an **Export HTML Report** option for sharing or archiving the current analysis. The exported file is a self-contained HTML report that can be opened locally in a standard web browser without requiring continued access to the router.

When geographic GeoView data is available, the interactive Google map is replaced in the report by a self-contained SVG engineering schematic showing the Site, resolved serving-cell locations, relative direction/distance, carrier-aware markers, a scale reference, and serving-cell location details.

The export does not require Google Maps runtime assets, provider credentials, or Internet access.

The report also includes the selected cellular interface and history range, Cellular Overview, serving-cell distribution and timeline, change activity, in-test handoff events when present, and detailed RF/radio-resource information for each identifiable serving cell.

Use the browser's **Print** function and select **Save as PDF** to create a portable PDF copy. The print layout is optimized for **US Letter landscape**.

The router does not generate or store the PDF.

## GeoView persistence and privacy

Non-secret GeoView settings are persisted as the `geoview` section of Speedtest Analyzer's canonical configuration and participate in the normal **Device > NCM Group > Built-in Default** configuration model introduced in v1.1.2.

The historical standalone `geoview_settings` key is migration input only.

Persisted GeoView configuration includes:

- Selected GeoView mode.
- Contribution preference.
- Active Site Location source.
- Independently retained Site Location values.
- Optional non-secret provider/cache tuning.

Provider credentials are never stored in canonical configuration documents.

Current GPS lock, satellite count, and runtime fix state are transient.

In **Local Only** mode, GeoView performs no OpenCellID serving-location request and does not load the Google geographic map. Cached serving-cell locations are retained but hidden from the local-only presentation.

In **Geolocation Services** mode, only the minimum information required for the requested operation is sent externally:

- OpenCellID serving-cell lookup receives the eligible cellular identity required to locate that serving cell.
- Google Site Address geocoding receives the manually entered Site Address.
- OpenCellID contribution receives the eligible serving identity plus the geographic position where it was observed.

The Google Server key and OpenCellID key remain server-side and are never written to reports or exports.

The browser Maps JavaScript key is a separate browser-restricted credential used only to load the interactive map.

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

The **Settings** page is the application-wide administration area. Feature configuration
(Scheduled Tests, Servers, GeoView, Outputs) remains on its own page; Settings is where you
review how the application is configured and manage the relationship between this device and
its NCM Group.

## How configuration works

Speedtest Analyzer configuration can come from two places:

- **NCM Group configuration** provides a shared baseline for every device in the Group.
- **Device configuration** is set locally on an individual device.

The application combines them one setting-area at a time. For each area — Scheduled Testing,
Outputs, iPerf3 Server Mode, User iPerf3 Servers, Netperf Servers, and GeoView — a local
Device value takes precedence over the Group value, and the Group value takes precedence over
the built-in default. Areas you have not configured locally simply inherit the Group value,
or the built-in default when the Group does not configure them either.

The **Configuration State** shown on the Settings page reflects this relationship:

- **Unconfigured** — no saved configuration; built-in defaults are in effect.
- **Device Managed** — configured locally on this device.
- **NCM Group** — managed by the NCM Group with no local overrides.
- **NCM Group + Device Overrides** — managed by the Group, with one or more areas overridden
  locally on this device.

The **Effective Configuration Sources** list shows, for each area, whether the value currently
comes from **This Device**, the **NCM Group**, or the **Built-in Default**.

## Device Overrides

When a device is Group-managed, any area you configure locally appears under **Device
Overrides**. Each override shows a short summary and where it will return to if you reset it —
either the **NCM Group** value or the **Built-in Default**.

- **Reset to Group** / **Reset to Built-in Default** returns a single area to the inherited
  value.
- **Reset All Device Overrides** returns every locally overridden area at once.

Some settings depend on each other. For example, a scheduled iPerf3 test depends on the iPerf3
Server Mode. If resetting one area by itself would leave an incompatible combination — such as
inheriting a Group schedule that expects a different server mode than the device is using —
Speedtest Analyzer shows a confirmation explaining the dependency and offers to reset the
related areas together so the result stays consistent. You can cancel without changing
anything.

## Update NCM Group Configuration

Once a device is Group-managed and has local overrides, administrators can promote selected
overrides into the existing NCM Group standard using **Update NCM Group Configuration**.

The wizard lets you choose which current Device overrides to promote. Selected areas are added
to (or replace) the corresponding areas in the Group; areas you do not select stay as Device
overrides and leave the current Group configuration unchanged. The wizard does not let you edit
values — it only decides placement.

Because the application never writes the Group configuration itself, the wizard generates the
complete revised Group JSON for you to update in NCM:

1. Select the Device overrides to promote and review the summary of what will change, what
   stays unchanged in the Group, and what remains a Device override.
2. Generate the revised Group configuration. The wizard shows the SDK Data name
   (`speedtest_analyzer_group`), the current and new Group revision, and the complete JSON.
3. **Update the existing `speedtest_analyzer_group` value** in the NCM Group configuration with
   the generated JSON. Do not create a second entry with the same name.
4. Return to the wizard and **Validate**. Once the revised Group configuration is confirmed on
   the device, the promoted local overrides are removed automatically, so the promoted settings
   are then served from the Group.

GeoView has a safety rule: a Device GPS location *policy* can be promoted, but a device's actual
GPS coordinates and any manually entered coordinates or site address remain device-specific and
are not copied into the shared Group configuration.

If the device configuration changes while the wizard is open, the workflow is cancelled and asks
you to start again, so stale changes are never merged.

## Migrate to NCM Group

For a device that is Device Managed (no Group configuration yet), **Migrate to NCM Group**
provides the first-time conversion of the device's configuration into a new Group standard. This
action is offered only in the Device Managed state; a device that is already Group-managed uses
**Update NCM Group Configuration** instead.

## Configuration from an earlier version

If a device still has configuration created by an earlier version of the application, Settings
shows a **Configuration Upgrade Required** notice. Testing, history, and reports continue to
work; only configuration changes are paused until you convert the existing settings to the
current format using **Convert Configuration**. Your existing settings remain active during this
step.

## Factory Reset

**Factory Reset** is a separate, clearly marked destructive action. It removes Speedtest
Analyzer's locally stored configuration, overrides, and local test history, but leaves the
application installed and never removes the NCM Group configuration. On a Group-managed device,
the Group configuration is used again after the local data is cleared.

## Developer Mode note

In Developer Mode, reinstalling or reloading the SDK package can clear the application's local
retained test history, and a device reboot can remove a manually installed development build. A
normal router reboot on a production-installed application preserves both the app and its
configuration. Saved configuration in NCM Group or Device SDK appdata is not affected by a
reboot.

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
