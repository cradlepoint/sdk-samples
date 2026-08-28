# Speedtest Analyzer Technical Guide

Engineering and advanced operational reference for the Cradlepoint Speedtest Analyzer SDK application.

**Documentation version:** 1.0.2
**Application release family:** 1.0.x
**Firmware family currently documented:** NCOS 7.26.x
**Architecture:** ARM64 (aarch64)

The normal user workflow is documented in [README.md](readme.md). This guide intentionally contains the implementation details, platform behaviors, error protections, validation logic, telemetry semantics, persistence behavior, and engineering history that would otherwise make the primary README difficult to use.

> **Product lineage:** Speedtest Analyzer 1.0.0 is the new pre-release product identity built from the validated Speed Test 2.7.6 development baseline. The application was not externally published under the Speed Test 2.x identity, so the product version and SDK package identity were reset before the first external release. Existing test-engine, WAN-routing, scheduling, history, server-management, cellular-telemetry, validation, and reporting behavior is preserved unless specifically documented otherwise.

---

# 1. Documentation and Design Principles

The application is designed around several operational principles:

- A user-selected WAN must not silently fall back to a different WAN.
- Known engine defects must be enforced independently from general platform validation.
- A failed or stale native test result must not be accepted as a fresh result.
- Application-created routing state must be cleaned up safely.
- A telemetry failure must not invalidate an otherwise successful throughput test.
- Public iPerf3 listener problems should be retried in a bounded way without hiding general WAN, DNS, routing, timeout, or system failures.
- Saved server identity, scheduled-test dependencies, and Reliability statistics must remain consistent when server configuration changes.
- User-facing Carrier Activity must distinguish observed serving-carrier state from published modem capability.
- Uplink CA must not be inferred when NCOS does not expose the required uplink component-carrier telemetry.

---

# 2. Application Components and Data

The documented application behavior uses several persistent or packaged data sources.

## 2.1 Version metadata

Application version information is carried in `package.ini`.

The current branded application release is `1.0.2`. Speedtest Analyzer 1.0.0 continues the engineering lineage of the unreleased Speed Test `2.7.6` development baseline.

## 2.2 Device validation catalog

`device_validation_catalog.json` maintains:

- Standalone platform validation.
- Controller + captive-modem validation.
- Pending versus validated combinations.
- Confirmed engine defects.
- Firmware information associated with confirmed defects.
- Optional `fixed_in` behavior for future firmware releases.

Validation status and known defects are intentionally independent.

## 2.3 Modem capability catalog

`modem_ca_capabilities.json` stores published modem Carrier Aggregation capability reference data and maps device/modem variants to reusable modem families.

The catalog is reference-only. It does not override observed serving-carrier telemetry.

## 2.4 Public iPerf3 catalog

`iperf3_public_servers.json` contains the bundled read-only Public iPerf3 server catalog.

The catalog is organized into:

- East
- Southeast
- Midwest
- Southwest
- West

The packaged list is sourced from the monitored public-server list at `iperf3serverlist.net`. The application does not continuously query that external site during normal operation.

## 2.5 SDK appdata

Configuration is stored through SDK appdata.

The 2.7.5 README documented configuration categories including:

| Appdata | Purpose |
|---|---|
| `speedtest_schedule` | Scheduled-test configuration |
| `speedtest_outputs` | Configured output targets |
| `netperf_servers` | Saved Netperf server entries |
| `iperf3_servers` | Saved iPerf3 server entries |

Exact internal JSON structures may change between application versions. Configuration should normally be managed through the web interface rather than edited directly.

---

# 3. Platform Validation and Known Defects

## 3.1 Historical cellular validation highlights

The carrier-activity features in v2.5.3 were validated across several different modem reporting behaviors:

- **E3000 / Verizon:** 5G NSA with LTE active and NR idle, including dynamic LTE secondary carriers under load.
- **R1900 / T-Mobile:** LTE B66 + NR n41 with dynamic LTE B2 activation. iPerf3 source-route steering was also validated with Ethernet as the primary WAN and cellular selected as the non-primary test WAN.
- **R980 / AT&T:** LTE carrier aggregation up to four active carriers, including multiple distinct carriers using the same LTE band.
- **W2255 / T-Mobile:** LTE B66 + NR n41 with an additional active NR carrier explicitly reporting `0 MHz`.
- **E400 / T-Mobile:** iPerf3 and Netperf validated on v2.5.3 with LTE B66 + dual NR n41 carrier activity, live carrier updates, and a 3-carrier / 150 MHz peak.

## 3.2 Device and captive-modem validation

Validation status is maintained in `device_validation_catalog.json` instead of a hard-coded model list. The app detects the base device and attached captive adapters from NCOS, counts both SIM records from one captive adapter only once, and builds an identity such as **E3000 + W1850**.

An entry marked `validated` suppresses the general notice. An entry marked `pending`, an unlisted combination, or an unavailable catalog displays:

> **Not yet validated** — E3000 + W1850 has not been fully tested with this app. Core functions may work, but results and feature behavior may vary.

This notice does not block tests. Confirmed engine defects are maintained separately in the `known_defects` section of `device_validation_catalog.json` and are enforced independently of validation status.

## 3.3 Known engine defects

Known engine defects use the same controller and captive-modem identity model as device validation. A defect can apply to a standalone device or to a specific controller + captive-modem combination, and only the matching test engine is restricted.

- `status: confirmed` means the catalog restriction is enforced.
- `confirmed_firmware` records the simple NCOS version where the defect was reproduced, such as `7.26.60`.
- `fixed_in: null` keeps the matching engine disabled on all firmware versions.
- When `fixed_in` is set, that NCOS version and newer are enabled automatically.
- Warning messages include the complete affected combination, such as **R2400 + RC1250 + Netperf**.

Current confirmed engine defects:

| Platform / Combination | Engine | Confirmed Firmware | Behavior | Workaround |
|---|---|---|---|---|
| **W2255** | Netperf | 7.26.60 | Native NCOS Netperf can hang or run indefinitely. | Use iPerf3. |
| **R2400 + RC1250** | Netperf | 7.26.60 | Native NCOS Netperf can continue beyond the requested duration and fail to produce results on the RC1250 captive WAN. | Use iPerf3. |
| **AER2200** | iPerf3 | 7.25.121 | The bundled iPerf3 executable cannot be launched on this platform. | Use Netperf. |

The AER2200 iPerf3 issue was confirmed during platform validation on 2026-08-20. A known defect does not by itself mark a platform as validated; validation status and engine restrictions remain independent.

The frontend disables a matching engine option for the selected WAN and the backend independently enforces the same rule for manual testing in Test Center, Scheduled Tests, and runtime Active Primary WAN resolution.

---

# 4. WAN Identity and Selection

The user interface presents friendly WAN labels while preserving the underlying NCOS identity used for testing, source routing, filtering, history, and reporting.

`Active Primary WAN` is a selector alias, not a persisted interface identity. It is resolved to one concrete NCOS interface before test execution proceeds.

Manual Tests and Scheduled Tests use the same selector presentation: **Active Primary WAN** is listed first, followed by every connected concrete WAN interface. This remains true when only one physical WAN is connected so users can choose between dynamic primary-WAN resolution and an explicitly pinned interface. This is frontend selector behavior only and does not change the existing backend Active Primary WAN resolver or persisted interface identity.

The implementation fails closed if NCOS cannot determine the current primary WAN. It does not silently choose another connection.

## 4.1 Friendly WAN interface names

The app converts NCOS interface identities into user-facing labels in interface selectors, history, filters, and reports:

- Ethernet WAN is displayed as **Ethernet WAN**.
- Wi-Fi WAN is displayed as **Wi-Fi as WAN**.
- Cellular labels identify the modem owner, such as **E3000 Internal - VZW-SIM1**, **W1850 Captive - TMO-SIM1**, or **W1850 - TMO-SIM1** on a standalone adapter.
- Unknown carriers or MVNOs retain the modem-owner label and available SIM slot.
- A validated Starlink or satellite connection uses **Satellite WAN-XXXX**, where `XXXX` is derived from the end of its stable NCOS WAN UID so multiple satellite connections can be distinguished.
- An `mdm-*` UID alone is not considered proof that an interface is cellular. Cellular naming requires carrier, SIM, LTE, 5G, NR, cellular, or WWAN evidence.
- Unknown future interface types retain the best NCOS-provided product, interface, or UID label.

These names are display-only. The original NCOS WAN UID, raw interface, source IP, active-primary status, and routing identity remain unchanged for test-engine selection and source routing. Existing CSV **Interface** values also remain unchanged.

A Satellite WAN remains selectable by every supported test engine and retains its raw NCOS interface, WAN UID, source IP, and routing identity. For statistics and reporting, it follows the same non-cellular path as Ethernet WAN:

- Cellular diagnostics and Carrier Activity are not collected.
- The live **Active Carriers** tile displays **No active cellular connection**, and the app does not create or poll a Carrier Activity collector.
- Test Log **Cell Health**, **Band Change**, **Tower Change**, and **CA** display `--`.
- **Cell Stats** and **Carrier Activity** expansion controls are not displayed.
- Cellular and Carrier Activity CSV fields remain empty.
- Previously saved Starlink results containing cellular-looking metadata are suppressed when displayed or exported.

# 5. Test Engine Behavior

## 5.1 iPerf3

iPerf3 is bundled with the application and is the recommended general-purpose throughput engine.

The application supports TCP Downlink and Uplink, per-WAN source selection, primary and validated non-primary WAN testing, bounded listener retry, live port-attempt status, and controlled cancellation.

The detailed source-routing behavior is documented later in this guide.

## 5.2 Netperf

Netperf uses the router's native NCOS speed-test service.

The application adds stale-result protection, lifecycle protection, timeout handling, cleanup verification, and model-specific safeguards around the native service.

## 5.3 Ookla

Ookla is optional and requires a compatible licensed ARM64 Ookla/Speedtest binary to be included with the application.

The distributed app does not include a licensed Ookla binary by default.

Platform behavior should be treated as unvalidated unless separately tested.

# 6. Carrier Activity and Cellular Telemetry

## 6.1 Carrier Activity in the Test Log

For successful tests on a cellular WAN, the **CA** column can be expanded to show the radio state observed during successful throughput traffic.

The expansion is organized as:

```text
BASELINE | PROGRESS | PEAK
```

**Baseline** is the last known carrier state immediately before successful throughput begins.

**Progress** separates the directional information available during successful Downlink and Uplink traffic. Downlink uses a dynamic RX/downlink carrier timeline beginning at `0s`. Uplink uses one fixed serving-anchor snapshot captured from the first valid upload-phase sample. Setup delays, failed iPerf3 ports, and unsuccessful attempts are not included.

**Peak** is the strongest carrier state observed during successful Download or Upload traffic. Peak is selected by:

1. Greatest active carrier count.
2. Highest observed available bandwidth when carrier count is tied.

Carrier state is sampled approximately every two seconds, but timeline entries are only added when the serving-carrier configuration meaningfully changes. Normal RF measurement fluctuation alone does not create a new transition.



## 6.2 Observed Downlink Bandwidth

**Observed Downlink Bandwidth** is the sum of positive bandwidth values reported for the active RX/downlink serving carriers. An active carrier reporting `0 MHz` remains in the downlink carrier count but contributes zero to the bandwidth total.

NCOS currently exposes the RX channel and bandwidth associated with these serving carriers. The app can therefore display observed downlink carrier aggregation, but it cannot determine active uplink carrier aggregation from the currently available NCOS data.

This value describes the downlink bandwidth available in the serving-carrier state reported by NCOS. It does not prove that every displayed carrier transported test traffic or that the full bandwidth total was used by the speed test.

In the expanded **Progress** section:

- **Downlink** displays the dynamic RX/downlink carrier timeline captured during download traffic.
- **Observed Serving Primary** displays the first valid PCell or primary serving carrier observed while upload traffic was running, including its radio type, band, and reported bandwidth.
- The Uplink anchor remains fixed for the result and is not replaced as RX/downlink secondary carriers activate or disappear.
- **Current Uplink CA: Not reported by NCOS** identifies that active uplink component-carrier participation cannot currently be determined.
- **Published Maximum Uplink CA** uses the matched modem's published Upload configuration for the service mode observed during the test.
- The Uplink section does not display RX secondary carriers, aggregate RX/downlink bandwidth, timestamps, or transition snapshots as active Uplink CA.

The serving primary and its reported bandwidth are valid observations from the upload phase. They do not prove whether one or more additional uplink component carriers transported traffic.

The published maximum is a modem capability reference. It does not indicate the number of uplink carriers currently active.

If a future NCOS release exposes the TX channel and uplink component-carrier telemetry required to determine active uplink CA, a new version of the app can add active Uplink CA reporting.

## 6.3 Published modem capability reference

The expanded Carrier Activity row includes published modem capability information from `modem_ca_capabilities.json`:

- **Baseline** shows the matched modem variant and separate **LTE**, **5G NSA**, and **5G SA** maximums.
- Each mode displays **DL Max** and **UL Max** carrier totals.
- A mode or direction without a published numeric configuration displays **Not Supported**.
- **Peak** shows the compact **Max Support Configuration**, including the published LTE and NR carrier combinations for LTE, 5G NSA, and 5G SA.

The lookup follows the cellular interface used by the test. An internal modem uses the host device's matching modem capability. A captive modem uses the captive modem's identity and does not inherit the host router's internal-modem capability.

If the device model is known but its exact modem variant is not confirmed, the app shows **Available Modem Variants**, listing every published variant for that device so the user can match the correct entry manually.

These values describe published modem maximums. They do not change, validate, or override the serving carriers observed during a test.

## 6.4 Maintaining the modem capability catalog

Published capabilities are stored in:

```text
modem_ca_capabilities.json
```

The catalog separates reusable data from device matching:

- `modem_families` contains releases, maximum Download and Upload CA, supported configurations, notes, and source documents.
- `devices` maps device models and modem variants to those reusable modem families.

To add a model or capability without changing Python or JavaScript:

1. Add or update the modem family under `modem_families`.
2. Add the device and its variants under `devices`.
3. Make sure every variant's `family` matches a key in `modem_families`.
4. Put the most specific match tokens first.
5. Preserve unclear datasheet language in a `note` instead of inferring unsupported details.
6. Validate the JSON and restart the application so the catalog is reloaded.

If the catalog is missing or invalid, the app logs a nonfatal error and omits the published capability reference. Speed tests and carrier telemetry continue normally.

## 6.5 Carrier roles

Where NCOS provides enough information, Carrier Activity identifies roles such as:

- `PCell (LTE Anchor)` for the LTE primary in 5G NSA.
- `PCell (Primary)` for LTE-only and 5G SA.
- `SCell0`
- `SCell1`
- Later carriers continue the native zero-based NCOS numbering.
- `NR Carrier`

The app does not guess an NR secondary-carrier role when NCOS does not explicitly provide that relationship.

Two carriers using the same band remain separate when NCOS reports them as distinct component carriers.

## 6.6 0 MHz carriers

Some modem/firmware combinations can report an active carrier with an explicit bandwidth of `0 MHz`.

v2.5.3 preserves that carrier instead of discarding it.

An explicit `0 MHz` carrier:

- Counts toward the active-carrier total
- Contributes `0 MHz` to observed available bandwidth
- Is highlighted in orange in the Carrier Activity display
- Sets the CSV `CA 0MHz Reported` field to `Yes`

This behavior was validated on the W2255.

## 6.7 Reports

Results can be exported for later review.

Supported report formats include:

- CSV
- HTML

These reports are useful for:

- Comparing WAN performance
- Reviewing cellular performance over time
- Recording failover performance
- Troubleshooting intermittent connectivity
- Reviewing carrier activation under load
- Sharing test results outside the router

## 6.8 CSV Carrier Activity fields

CSV exports include Carrier Activity fields such as:

- CA Peak Carrier Count
- CA Baseline Carrier Count
- CA Baseline Carrier Set
- CA Baseline Bandwidth MHz
- CA Download Peak Carrier Count
- CA Download Peak Carrier Set
- CA Download Peak Bandwidth MHz
- CA Upload Peak Carrier Count
- CA Upload Peak Carrier Set
- CA Upload Peak Bandwidth MHz
- CA 0MHz Reported
- CA Download Progress
- CA Upload Progress

The Download and Upload progress fields preserve the phase timeline in a compact text format.

These existing CSV field names and values remain unchanged for compatibility. Carrier information recorded during the Upload traffic window represents the RX/downlink serving state observed at that time; it is not a measurement of active uplink CA.

v2.5.3 uses ASCII separators in these progress fields for better compatibility with spreadsheet applications.

Existing final Cell Stats / dynamic carrier columns remain available when the final cellular snapshot contains aggregation records.

Published modem capability references are intentionally excluded from CSV exports. Existing CSV columns and schema remain unchanged. Carrier role text uses the corrected mode-aware PCell terminology and native zero-based SCell numbering.

---

## 6.9 Cellular Details

When a test runs across a cellular WAN, the application captures additional modem and radio information when available.

### 6.9.1 Connection Health

May include:

- Carrier
- Service type
- Service detail
- Signal/health information

### 6.9.2 Serving radio sections

The radio-summary areas are service-mode aware.

For **LTE-only** connections, the primary section displays the serving LTE radio.

For **5G NSA** connections:

- The first section remains **LTE** and represents the LTE serving/anchor radio.
- The second section remains **5G NR** and represents the reported NR connection.
- If NCOS explicitly reports NR idle, the existing warning remains:

```text
NR idle — throughput came from LTE only
```

For **5G SA** connections:

- There is no LTE anchor.
- The first section is **5G NR** and represents the NR PCell.
- When an indexed NR secondary carrier is active, the second section represents the first reported NR SCell, such as **5G NR — SCell0**.
- The complete PCell/SCell topology remains visible in the Carrier Aggregation table.

### 6.9.3 RF measurement availability

RF values are displayed only when NCOS reports them. PCell measurements are not copied into an SCell when SCell-specific measurements are unavailable; those values remain `--`.

### 6.9.4 Carrier Aggregation / active carrier details

Component-carrier information may include:

- Carrier role
- RAT
- Band
- Bandwidth
- Channel
- RSSI
- RSRP
- RSRQ
- SINR
- PCI
- Carrier state

Carrier RAT is determined from the reported band value rather than from the diagnostic key family alone. NCOS may report an LTE band under an indexed `_5G_` PCell key during 5G NSA operation.

Normalized topology preserves:

- **PCell (LTE Anchor)** for the LTE primary in 5G NSA.
- **PCell (Primary)** for the serving primary in 5G SA.
- Native secondary identities such as **SCell0**, **SCell1**, and **SCell2**.
- Same-band carriers when they use different explicit channels.
- Active carriers that explicitly report `0 MHz`.
- One physical carrier when direct and indexed fields describe the same RAT, band, and channel.

### 6.9.5 Tower & Network

When reported by NCOS/modem status:

- Cell ID
- Physical Cell ID
- Active APN

For LTE and 5G NSA, the normal LTE serving-cell identifiers remain authoritative.

For 5G SA, the application prefers:

- `NR_CELL_ID` for **Cell Tower ID**
- `PHY_CELL_ID_5G` for **Physical Cell ID**

If an NR-specific identifier is unavailable, `CELL_ID` or `PHY_CELL_ID` remains the fallback.

Fields that are not reported by the modem are omitted or displayed as unavailable.

---

# 7. Carrier Activity Phase Timing and Safety

Carrier telemetry is optional and must never cause the throughput test itself to fail.

The collector begins before the test so it can observe the pre-traffic cellular state, but the user-facing Download and Upload timelines are reconstructed only after the engine confirms successful throughput.

## 7.1 iPerf3

The successful iPerf3 process launch becomes that phase's `0s` boundary.

Failed server-port attempts and retry delays are excluded.

Once Download succeeds on a port, Upload receives its own independent phase start on that same successful port.

## 7.2 Netperf

Netperf phase timing begins when NCOS exposes evidence that the fresh throughput operation is actually running.

The preferred start signal is:

- `status=running`, or
- Numeric progress greater than zero

If a successful platform never exposes a fresh running/progress transition, the app falls back to the successful `run=1` trigger timestamp.

Result-settle delays used on R980/E3000 are not included in the traffic window.

## 7.3 Ookla

When a compatible binary is present, phase timing is based on its streaming events:

- First Download event starts Download
- First Upload event closes Download and starts Upload
- Final result event closes the active phase

## 7.4 Clock-jump protection

Internal carrier samples and phase elapsed-time calculations use a monotonic clock.

This prevents router boot-time or NTP clock corrections from producing impossible phase durations if the system wall clock changes while a speed test is running.

Netperf result freshness checks still use the router's wall-clock result timestamps because those must be compared with NCOS `perf_results` time values.

---

# 8. iPerf3 WAN Selection and Source Routing

## 8.1 Primary WAN

The app determines the active primary WAN from NCOS status.

Where supported, iPerf3 is initially started using both:

```text
-B <source_ip>
--bind-dev <linux_interface>
```

Some Cradlepoint platforms do not permit SDK applications to use `SO_BINDTODEVICE`.

On those platforms, a primary-WAN test safely retries using source-IP binding only:

```text
-B <source_ip>
```

The primary routing table already provides the required forwarding path.

## 8.2 Non-primary WAN

Source-IP binding alone is not enough to guarantee that traffic leaves the selected non-primary WAN.

On validated platforms that support additional NCOS routing tables, the app temporarily creates a source-routing configuration for the selected WAN.

The process is:

1. Detect the selected WAN device UID and source IP.
2. Create a temporary `STWEB-*` routing table.
3. Configure the table to use the selected WAN with automatic gateway discovery.
4. Read the routing table `_id_`.
5. Create a source-IP routing policy referencing that table.
6. Verify the policy.
7. Run iPerf3 using `-B <selected_source_ip>`.
8. Delete the temporary routing policy.
9. Delete the temporary routing table.

The policy is intentionally deleted **before** the table.

This workflow was successfully validated on the R1900 in v2.5.3 with Ethernet remaining the active primary WAN while iPerf3 traffic was steered through the selected cellular WAN.

### 8.2.1 Stale route cleanup

Before creating a new temporary route, the app checks for stale `STWEB-*` routing tables left by interrupted tests.

Policies referencing those tables are removed before the tables themselves are deleted.

This prevents abandoned application-created routing objects from accumulating in NCOS.

### 8.2.2 W2255 routing limitation

On the tested W2255 firmware, the NCOS configuration API only permits the **Main** routing table.

Attempts to create an additional routing table return a platform validation error indicating that the device supports only the Main table.

The app does not modify the Main routing table to force secondary-WAN iPerf3 steering.

This protects the router's normal routing behavior.

---

# 9. Netperf Result Validation and Lifecycle Protection

## 9.1 Netperf Result Validation

NCOS Netperf exposes test state and result objects independently. A previous terminal result can remain visible while a new test is starting.

The application protects against accepting stale data by validating:

- Requested WAN
- Device UID
- Test direction
- Result timestamp
- Test start time

A result belonging to the wrong WAN or an older test is ignored.

Only a result associated with the current test is accepted.

## 9.2 Netperf timeouts

Netperf is a router-wide resource and only one native speed test should run at a time.

If a native test remains active beyond the application's timeout:

1. The test is marked as timed out.
2. The app sends a cancel/kill request.
3. The process state is checked to confirm that it stopped.
4. The failure is returned rather than reusing an old result.

Timeout deadlines use a monotonic clock so normal system/NTP clock corrections cannot prematurely expire or extend the application's internal timeout window.

---

## 9.3 Enhanced Netperf Lifecycle — R980 and E3000

Repeated testing showed that R980 and E3000 can occasionally expose timing differences between native Netperf process state and result publication.

The app includes enhanced lifecycle handling specifically for these model families.

Before each direction the app:

1. Checks whether a previous Netperf process is still running or connecting.
2. Cancels it if required.
3. Verifies that the old process has stopped.
4. Captures the previous result timestamp as a baseline.
5. Starts the new test.
6. Requires a fresh-run state transition before accepting results.
7. Waits for the native test to complete.
8. Uses a short bounded settle/re-read window before consuming the result.
9. Verifies Download is fully stopped before starting Upload.

If a direction times out:

1. The app cancels the native test.
2. Confirms the process stopped.
3. Waits briefly for cleanup.
4. Retries that direction once.
5. Never retries indefinitely.

This improves consistency without masking genuine WAN failures.

For example, if the cellular WAN actually disconnects during a test, the application may retry once but will still report the failure if NCOS reports that no WAN connection is available.

---

## 9.4 W2255 Netperf Limitation

Netperf is intentionally disabled on the W2255 in v2.5.3.

During validation, Netperf tests were observed to remain active well beyond the expected test duration. The same behavior was reproduced using the router's native NCOS speed-test interface without the `speedtest_web` application involved.

Because the behavior occurs in the native NCOS test service, the app does not attempt to work around it by extending timeouts or repeatedly restarting the test.

The UI displays a model-specific notice and prevents W2255 Netperf jobs from being started or scheduled.

Use iPerf3 or an available licensed Ookla test instead.

---

# 10. iPerf3 Server Architecture, Retry, Reliability, and Editing

## 10.1 iPerf3 Server Sources and Reliability

Version 2.7.0 introduces a new source-aware iPerf3 server architecture, bounded listener retry, endpoint reliability tracking, and improved server-management workflows.

The feature is designed to provide usable public iPerf3 endpoints while still allowing operators to maintain their own private or trusted server list.

Existing Netperf execution, cellular telemetry, Carrier Aggregation monitoring, WAN source-routing behavior, and device-validation behavior remain separate from the new iPerf3 server-management features.

### 10.1.1 iPerf3 Server List Modes

The application provides two iPerf3 server-list modes:

- **Public iPerf3 Servers**
- **User Server List**

The selected mode controls which saved iPerf3 servers are loaded and presented to the manual test controls in Test Center, Scheduled Tests, and the Servers page.

Only the active source needs to be maintained in the application's active server cache.

Changing between Public and User modes does not delete the User Server List.

If an existing iPerf3 scheduled job is tied to the previous server source, changing modes warns the operator and resets only the incompatible iPerf3 schedule. Netperf schedules are not affected by changing the iPerf3 server source.

### 10.1.2 Public iPerf3 Servers

Public mode is the default server source for new 2.7.0 installations and for the initial migration into 2.7.0.

Existing User Server List data is preserved during migration even though Public mode becomes active.

The Public server catalog is bundled with the application as:

`iperf3_public_servers.json`

The file is read-only from the web interface and is not copied into SDK appdata.

The bundled Public iPerf3 catalog is organized into five United States regions. Each region contains its own set of unique packaged server endpoints:

- East
- Southeast
- Midwest
- Southwest
- West

The exact packaged server membership may change as individual public endpoints are validated, removed, replaced, or become unavailable. The regional model remains independent of the number of servers currently packaged in each region.

The catalog is sourced from the monitored public server list at:

`https://iperf3serverlist.net/`

The application uses its bundled catalog and does not continuously query the external website during normal operation.

Each Public entry contains:

- Friendly Server Name
- Hostname or IP address
- Starting Port
- Ending Port
- City
- Country
- Region

The Friendly Server Name is displayed in the user interface while the actual hostname/IP and actual test ports are retained in test results.

#### 10.1.2.1 Manual Public Tests

Manual Public testing provides:

1. Region selection.
2. Friendly server selection within that Region.
3. A Custom Server option for ad-hoc testing.

Custom Server allows an operator to test an endpoint without permanently adding it to either server list.

Custom Server results are intentionally excluded from persistent iPerf3 Reliability statistics because an ad-hoc server does not have a stable saved server identity.

If long-term Reliability statistics are desired for a private endpoint, add that endpoint to the User Server List instead.

#### 10.1.2.2 Scheduled Public Tests

Scheduled Public testing uses its own Region and server selection.

The Scheduled Region is independent from the Region currently selected for manual testing in Test Center.

Changing the Scheduled Region clears the selected scheduled server so the operator must explicitly select a server from the new Region.

Custom Server is not available for Scheduled Tests.

### 10.1.3 User Server List

User mode uses the persistent SDK appdata User Server List.

The User Server List supports:

- Add Server
- Delete Server
- Delete All Servers
- Download Server List Template
- Export My Server List
- Import Server List
- Merge Lists
- Replace List

The list remains stored when the application is switched to Public mode.

#### 10.1.3.1 User Server Identity

A saved User server is identified by its normalized endpoint:

- Hostname or IP address
- Starting Port
- Ending Port

The Friendly Server Name is descriptive and is not part of endpoint identity.

This allows cosmetic changes to a server name without changing the underlying endpoint identity.

The Friendly Server Name field supports a maximum of 120 characters.

### 10.1.4 User Server JSON Format

New 2.7.0 templates and exports use canonical schema version 1.

Each server entry contains all of the following fields:

- `server_name`
- `host`
- `port_start`
- `port_end`
- `city`
- `country`

A port-range server uses different starting and ending port values.

Example:

    {
      "server_name": "Corporate Chicago",
      "host": "iperf01.example.com",
      "port_start": 5201,
      "port_end": 5210,
      "city": "Chicago",
      "country": "United States"
    }

A single-port server uses the same value for both port fields.

Example:

    {
      "server_name": "Lab Single Port",
      "host": "iperf02.example.com",
      "port_start": 5201,
      "port_end": 5201,
      "city": "Indianapolis",
      "country": "United States"
    }

The complete canonical file uses:

    {
      "schema_version": 1,
      "servers": [
        ...
      ]
    }

The downloadable template includes both a port-range example and a single-port example.

The generated filenames are:

- `speedtest_analyzer_iperf3_user_server_list_template.json`
- `speedtest_analyzer_iperf3_user_server_list.json`

### 10.1.5 Legacy User Server Import

Version 2.7.0 includes import compatibility for supported pre-2.7 User Server List JSON files.

Legacy input can be normalized when supplied as:

- A raw JSON array of server records.
- A JSON object containing a `servers` array.
- A JSON object containing an `iperf3_servers` array.

Legacy endpoint fields such as `server` and `port` are normalized into the 2.7 canonical format before the normal import validation is performed.

Canonical 2.7 files remain subject to the strict schema-version-1 validation.

Legacy support is import-only.

New templates and exports always use the canonical 2.7 format.

### 10.1.6 Import Workflow

The 2.7.0 import workflow is file-first.

1. Select **Import Server List**.
2. Choose the JSON file.
3. Select **Merge Lists** or **Replace List** in the import dialog.
4. Confirm the import.

Neither Merge nor Replace is selected by default.

The Import button remains disabled until an action is selected.

#### 10.1.6.1 Merge Lists

Merge preserves the current User Server List and appends unique imported endpoints.

Duplicate endpoints are skipped.

Existing server order is preserved and new unique entries are appended.

The operation reports how many entries were added and how many duplicates were skipped.

#### 10.1.6.2 Replace List

Replace substitutes the complete User Server List with the imported list.

The interface clearly identifies Replace as a destructive list operation.

Existing iPerf3 schedule safeguards still apply.

If the scheduled endpoint would no longer exist after Replace, the application warns the operator before resetting the affected iPerf3 schedule.

### 10.1.7 Delete and Schedule Protection

Deleting a User server that is currently used by the saved iPerf3 schedule requires confirmation.

If confirmed, the incompatible iPerf3 schedule is reset.

Delete All uses the same schedule-safety behavior.

These protections apply to iPerf3 schedule dependencies only and do not remove unrelated Netperf configuration.

## 10.2 iPerf3 Port Selection and Retry

Public and User iPerf3 servers can define either a single port or a port range.

Version 2.7.0 uses bounded randomized port selection to improve success when a public iPerf3 listener is busy or unavailable.

### 10.2.1 Five-Port Maximum

One complete test can use a maximum of five unique ports on a server.

The five-port budget is shared across Downlink and Uplink for that server.

The implementation selects unique random ports without building the complete configured port range in memory.

This keeps retry behavior bounded and minimizes memory usage on the router.

### 10.2.2 Retryable Listener Failures

Another port can be attempted when the failure is attributable to the iPerf3 listener, including conditions such as:

- Server busy
- Connection refused
- Server not running
- Listener unavailable

These failures can also be counted by the iPerf3 Reliability system.

### 10.2.3 Hard Network and System Failures

The application deliberately does not treat generic connectivity failures as iPerf3 listener failures.

Conditions such as the following do not cause broad random-port retry:

- Generic timeout
- DNS failure
- WAN failure
- Routing failure
- Source-routing failure
- Interface binding failure
- Process or operating-system failure

This prevents a WAN or routing problem from being hidden by repeated attempts against unrelated ports.

### 10.2.4 Downlink Behavior

The selected server is attempted using unique ports from its configured port or range.

If a retryable listener failure occurs, another unused port may be tried.

The server receives at most five unique port attempts for the complete test.

### 10.2.5 Public Backup Server

Public mode provides one additional server-level recovery mechanism.

If:

1. Downlink has never successfully started, and
2. The primary Public server exhausts five retryable listener failures,

the application can attempt exactly one backup Public server.

The backup is the next configured server in the same Region, with wrap-around when necessary.

The backup receives its own five-port maximum.

The application does not continue cycling through every Public server.

### 10.2.6 User Server Behavior

User Server List tests do not automatically move to another server.

If a saved User server exhausts its eligible listener retry budget, the test stops against that configured endpoint.

This avoids unexpectedly sending traffic to a different private or operator-defined server.

### 10.2.7 Uplink Behavior

After Downlink succeeds, the successful server becomes locked for the remainder of the test.

Uplink first uses the exact port that successfully completed Downlink.

If that Uplink attempt receives a retryable listener failure, another unused port may be selected from the same locked server while remaining inside the shared five-port budget.

Uplink never changes to another server after Downlink has succeeded.

### 10.2.8 WAN Binding and Source Routing

The existing WAN execution behavior remains in place.

Primary-WAN iPerf3 tests retain the validated bind-device behavior and fallback handling.

Non-primary WAN tests retain the existing temporary source-routing setup and cleanup lifecycle.

The new server retry architecture does not create a separate routing lifecycle for each port attempt.

## 10.3 History and CSV Endpoint Reporting

Version 2.7.0 records the actual iPerf3 endpoint used by the completed test rather than only the originally configured endpoint.

iPerf3 History and CSV include:

- Server Name
- Hostname/IP
- Downlink Port
- Uplink Port

This is especially important when a test uses a randomized listener port or a Public backup server.

The recorded Downlink and Uplink ports show the actual ports used by that execution.

Public/User source mode, Region, and backup metadata are not added as additional History fields.

Netperf results continue to use the existing Netperf reporting behavior.

CSV Cellular Health values are exported to one decimal place to match the user-facing Cellular Health display.

## 10.4 iPerf3 Server Reliability

Version 2.7.0 adds lightweight Reliability statistics for saved iPerf3 servers.

Reliability is displayed at the bottom of the Servers page for the currently active Public or User source.

The summary includes:

- Successful Tests
- Endpoint Failures
- Failure Rate
- Most Failed Port

The per-server table includes only endpoints that have recorded activity.

A newly added saved server is available for Reliability tracking immediately but does not appear in the table until it records at least one successful test or endpoint failure.

### 10.4.1 Successful Tests

A Successful Test is counted after a complete successful iPerf3 test.

The success is attributed to the actual saved endpoint used by the test.

For Public backup operation, a backup-server success is attributed to the backup endpoint rather than the original primary endpoint.

### 10.4.2 Endpoint Failures

Only retryable listener-attributable failures increment Endpoint Failures.

Network, WAN, DNS, routing, generic timeout, and system failures are deliberately excluded.

Per-port listener failures are retained so the interface can identify the Most Failed Port.

### 10.4.3 Failure Rate

Failure Rate is calculated from tracked Reliability events:

`Endpoint Failures / (Successful Tests + Endpoint Failures)`

This is an operational endpoint metric and is not intended to represent the overall success rate of every WAN or application execution attempt.

### 10.4.4 Custom Server Exclusion

Manual Custom Server tests are intentionally not persisted in Reliability statistics.

Custom endpoints do not have a stable saved server reference.

To track Reliability for a private or custom server, save it in the User Server List before testing.

### 10.4.5 Reliability Persistence

Reliability statistics are accumulated in memory and marked dirty only when they change.

The existing scheduler thread checks for dirty Reliability data every 30 minutes.

SDK appdata is written only when statistics are dirty.

If no tests have changed Reliability data, the 30-minute check does not create an SDK appdata write.

This reduces unnecessary configuration/appdata writes on the router.

Because Reliability data can remain in RAM until the next dirty checkpoint, a router or application restart before that checkpoint can lose the most recent Reliability increments.

Test History is independent from the Reliability checkpoint.

### 10.4.6 Reset Reliability Statistics

The Servers page provides **Reset Reliability Statistics**.

Reset requires confirmation.

Reset affects only the currently active Public or User Reliability source.

Saved server definitions are not deleted by resetting Reliability statistics.

## 10.5 Scheduled Test Behavior

Manual and Scheduled iPerf3 selections are intentionally independent.

A saved scheduled job stores its own iPerf3 server reference.

Changing or deleting server configuration that makes the scheduled endpoint invalid requires the schedule to be reset before the incompatible change is completed.

### 10.5.1 Auto-start on Boot

Schedule configuration remains saved across application and router restarts.

Runtime schedule enablement after restart follows the **Auto-start on boot** setting.

- Auto-start enabled: the saved schedule resumes after restart.
- Auto-start disabled: the schedule configuration remains saved but execution starts disabled.

This prevents a previously enabled schedule from automatically resuming after reboot when Auto-start on boot is not selected.

## 10.6 iPerf3 Stop and User Server Editing

Version 2.7.1 adds targeted lifecycle and User Server List improvements without changing the validated 2.7.0 server-source, retry, routing, scheduling, or Reliability architecture.

### 10.6.1 iPerf3 Stop and Cancellation

iPerf3 tests run through a local application-owned `iperf3` subprocess.

In earlier releases, the Stop action updated the application test state and invoked the native NCOS Netperf stop control, but that NCOS control does not terminate an already-running local iPerf3 subprocess. As a result, Stop could appear to succeed in the web interface while an active iPerf3 Downlink or Uplink phase continued until its configured duration completed.

Version 2.7.1 adds a protected reference to the currently active local iPerf3 subprocess.

When Stop is requested:

- The application test state is marked cancelled.
- An active local iPerf3 subprocess is terminated directly.
- The existing NCOS Netperf stop action is still invoked so native Netperf cancellation behavior is preserved.
- Cancellation is returned as **Test cancelled** before normal iPerf3 listener-retry or primary-WAN bind-fallback processing.
- Cancellation does not consume additional listener retry ports or trigger Public backup-server selection.
- If Downlink completed successfully before Uplink is cancelled, the completed Downlink result is intended to be retained as a **Partial** result with the cancelled Uplink identified as **Test cancelled**.
- The execution slot remains reserved until normal worker cleanup completes so another Manual or Scheduled test cannot overlap cleanup from the cancelled test.

The iPerf3 retry budget, randomized port selection, Public backup behavior, Uplink server lock, WAN binding, and source-routing lifecycle are unchanged.

### 10.6.2 User Server Editing

The User Server List now separates **Add** and **Edit** behavior.

**Add Server** is Add-only.

A saved User endpoint is identified by its normalized Hostname/IP and Port/Range. Attempting to add an endpoint that already exists returns explicit duplicate feedback instead of silently replacing the existing entry.

Existing saved User servers can be edited from the Server Management page.

Editable fields are:

- Friendly Server Name
- Hostname/IP
- Port or Port Range
- City
- Country

The existing form is reused for editing. Selecting **Edit** loads the saved values into the form, changes **Save** to **Update**, and provides **Cancel Edit** to return to normal Add mode.

### 10.6.3 Metadata and Endpoint Identity

Changing only the following fields does not change endpoint identity:

- Friendly Server Name
- City
- Country

Metadata-only edits preserve the existing deterministic User server reference. Existing schedule association and Reliability history therefore remain associated with that endpoint.

Changing either of the following creates a new endpoint identity:

- Hostname/IP
- Port or Port Range

Endpoint identity changes:

- Are checked against all other saved User servers to prevent duplicate Hostname/IP and Port/Range combinations.
- Preserve the server's position in the User Server List.
- Use the existing scheduled-server protection workflow.
- Require confirmation before resetting a scheduled iPerf3 job that references the old endpoint.
- Do not migrate Reliability history from the old endpoint identity to the new endpoint identity.
- Begin Reliability tracking for the new endpoint as a fresh saved server identity.

The updated User Server List is still persisted with a single SDK appdata write after validation succeeds.

### 10.6.4 2.7.1 Validation Status

The 2.7.1 code changes have passed local Python compilation and static source validation.

Full runtime validation across the supported device/platform matrix is pending. Runtime validation should include active iPerf3 cancellation, partial-result handling, duplicate Add feedback, metadata-only edits, endpoint edits, duplicate endpoint rejection, scheduled-endpoint protection, and existing Netperf/iPerf3 regression checks.

## 10.7 2.7.0 Operational Compatibility

The 2.7.0 changes are additive to the existing Speed Test application.

The release preserves the previously validated behavior for:

- Netperf
- Existing iPerf3 WAN binding
- Non-primary WAN source routing and cleanup
- Cellular telemetry
- Carrier Aggregation monitoring
- Cellular Health
- Device validation catalog
- Modem CA capability catalog
- Test History
- Scheduled test framework

# 11. Test History, Failures, and Reporting Semantics

## 11.1 Test History and Failures

The app records successful tests and tracks failed tests separately.

A failed test may occur because of:

- Test server unavailable
- iPerf3 server port busy
- WAN disconnect during testing
- No usable WAN connection
- Native test engine timeout
- Model-specific platform limitation

A failed test should not automatically be interpreted as a WAN performance problem. Review the failure reason and router logs before drawing conclusions.

Carrier Activity from a failed setup or unsuccessful throughput attempt is not promoted into the successful Download/Upload timeline.

---

## 11.2 History & Reports

The **History & Reports** section provides results from completed and failed tests.

Available information may include:

- Download throughput
- Upload throughput
- Latency
- Jitter
- WAN/interface used
- Test engine
- Server
- Test time
- Cellular Health
- Band change
- Tower change
- Carrier Activity
- Final cellular radio information
- Success/failure status

The interface provides overall and per-engine statistics and chronological result graphs.

### 11.2.1 History filtering, pagination, and local time

Version 2.7.5 adds independent controls for the Test Summary and Test Log.

**Test Summary:**

- **Date Range** provides All History, Last 12 Hours, Last 24 Hours, Last 3 Days, and Older than 3 Days.
- The selected range updates Summary tiles, Trends, per-engine statistics, and speed graphs.
- Existing per-section interface filters are applied after the selected Date Range.
- Each interface filter group always retains at least one selected interface.

**Test Log:**

- **Interfaces** supports multi-select filtering while always retaining at least one selected interface.
- **Status** filters Complete, Partial, or Failed results.
- **Date** provides the same All History, 12-hour, 24-hour, 3-day, and Older than 3 Days ranges.
- **Reset** clears only the Test Log filters.
- Pagination defaults to the newest 10 matching results and can display 10, 25, 50, or 100 results per page.

The Test Summary Date Range and Test Log filters are independent. Changing one does not alter the other.

History timestamps are stored in UTC but displayed using the viewer's browser timezone and normal regional 12-hour or 24-hour time convention. Test Log timestamps, Summary range dates, graph timestamps, and graph tooltips use browser-local time. CSV exports remain in UTC for portability and consistent downstream processing.

Graph tooltips also identify the friendly WAN interface associated with each plotted result.

# 12. Error Handling Principles

The application is designed to fail safely rather than silently return misleading results.

Examples include:

- Do not accept stale Netperf results.
- Do not silently fall back to the primary WAN when a non-primary WAN was explicitly selected.
- Do not leave temporary routing policies/tables behind after a completed test.
- Do not run indefinitely when the native Netperf process hangs.
- Do not repeatedly retry a failing native test forever.
- Do not force unsupported routing changes on platforms such as W2255.
- Do not block unknown device models solely because they have not yet been validated.
- Do not let telemetry collection failure cause an otherwise valid throughput test to fail.
- Do not let wall-clock corrections corrupt Carrier Activity elapsed timing.

---

# 13. Advanced Troubleshooting

## 13.1 Web interface does not open

If using NCM LAN Manager, verify that the SDK app is running and that LAN Manager can reach the device.

If connecting directly from the local LAN, verify:

- The SDK app is running.
- The client is connected behind the router.
- Primary LAN Zone to Router Zone forwarding is allowed.
- Router Zone to Primary LAN Zone forwarding is allowed.
- TCP port `8000` is reachable.

## 13.2 iPerf3 cannot connect

Check:

- Server hostname/IP
- Server availability
- Configured port or port range
- Internet connectivity from the selected WAN

A failure on one public iPerf3 port does not necessarily mean the WAN is down. The server may simply be busy.

If the server has a configured port range, watch the live status message to confirm whether the app is advancing through the available ports.

## 13.3 Selected secondary WAN cannot be tested

Verify that the WAN is currently connected and has a valid IPv4 address and gateway.

The app will not silently run the test on another WAN if source routing cannot be established for the selected connection.

On platforms that do not support additional routing tables, such as the validated W2255 firmware, non-primary iPerf3 steering may not be available.

## 13.4 Netperf reports no WAN connection

Confirm the selected WAN remains connected for the full test.

A cellular modem reconnect, SIM event, carrier transition, or WAN link-down during a test can cause native NCOS Netperf to reject or terminate the job.

## 13.5 Carrier Activity does not show additional carriers

Additional carriers are controlled by the modem/network and may only activate when traffic demand and radio conditions require them.

A successful speed test does not guarantee that carrier aggregation or an NR leg will activate.

The app reports what NCOS exposes; it does not force the modem to enable additional component carriers.

---

# 14. Maintenance Procedures

## 14.1 Maintaining the device validation catalog

To approve a tested entry in `device_validation_catalog.json`:

1. Locate the standalone model or exact captive combination.
2. Change `status` from `pending` to `validated`.
3. Set `validated_date` to the test date using `YYYY-MM-DD`.
4. Update `notes` and the top-level catalog dates.
5. Validate the JSON and rebuild the app.

Example validated entry:

    "W1850": {
      "status": "validated",
      "validated_date": "2026-08-18",
      "notes": "Validated with iPerf3 and Netperf on the selected captive WAN."
    }

Additional copy-ready examples for standalone and multiple-captive entries are included in the JSON file. An invalid catalog logs a nonfatal error and does not present the hardware as validated.

---

## 14.2 Maintaining the modem capability catalog

The detailed modem capability catalog procedure is documented in **6.4 Maintaining the modem capability catalog**.

## 14.3 Documentation release policy

Beginning with Speedtest Analyzer 1.0.0:

- `README.md` carries the concise user-facing changelog for the current Speedtest Analyzer release family.
- `TECHNICAL_GUIDE.md` carries the permanent detailed engineering history.
- The unreleased Speed Test 2.x development history remains permanently preserved here as the engineering lineage that preceded Speedtest Analyzer 1.0.0.
- When development moves to a new Speedtest Analyzer release family, the README changelog may reset to that active family while prior detailed history remains in this Technical Guide.
- Release tar files remain immutable snapshots of the documentation that shipped with each build, but they are not the primary historical documentation source.

# 15. Release Family Summary

| Release Family | Major Focus |
|---|---|
| **1.0.x — Speedtest Analyzer** | New product identity and visual branding, Test Center navigation, theme-aware SVG application mark, fresh SDK package identity, and continuation of the validated pre-release 2.7.6 runtime architecture. |
| **2.7.x — Speed Test pre-release** | Public/User iPerf3 server architecture, bounded listener retry, endpoint Reliability, User Server editing, iPerf3 cancellation, History & Reports usability, expanded platform validation, and the 2.7.6 documentation split. |
| **2.6.x** | External modem capability catalog, device-validation catalog, known-defect framework, WAN identity improvements, Active Primary WAN behavior, and expanded Netperf lifecycle protection. |
| **2.5.x** | Carrier Activity, cellular telemetry, phase-aware CA timelines, source-routing validation, engine-reported data-volume accounting, and early platform-specific protections. |
| **2.4.x** | Model-family capability detection, compatibility states, shared Manual/Scheduled compatibility alerts, and early enhanced Netperf lifecycle behavior. |

---

# 16. Detailed Engineering Changelog

This section is the permanent engineering history for Speedtest Analyzer and its unreleased Speed Test development lineage.

Speedtest Analyzer `1.0.0` was created from the validated Speed Test `2.7.6` development baseline before external publication. The version reset represents a product-brand and SDK-package identity reset rather than a rewrite of the throughput, routing, scheduling, telemetry, history, or server architectures.

## v1.0.2

- Corrected **5G Standalone (SA)** serving-carrier normalization so an NR serving PCell is no longer interpreted or displayed as an LTE anchor.
- Added support for unnumbered indexed NCOS PCell fields such as `BAND_5G_PCELL`, `BANDWIDTH_5G_PCELL`, and `CHANNEL_5G_PCELL`.
- Carrier radio type is now determined from the reported band value rather than assuming that an `_5G_` diagnostic key always represents NR. This supports NSA states where indexed 5G-family keys contain an LTE PCell.
- Preserved native NCOS secondary-carrier identities as **SCell0**, **SCell1**, **SCell2**, and later zero-based indexes.
- Preserved distinct same-band carriers when they have different explicit channels and retained active carriers reporting `0 MHz`.
- Normalized direct and indexed representations of the same physical carrier to prevent duplicate carrier counting.
- Made live cellular radio summaries service-mode aware: LTE and 5G NSA retain LTE / 5G NR presentation, while 5G SA presents the NR PCell and first reported NR SCell when available.
- Updated Carrier Activity and CSV role presentation to use **PCell (LTE Anchor)** only for the LTE primary in 5G NSA and **PCell (Primary)** for LTE-only and 5G SA.
- Changed the Carrier Activity uplink label from **Observed Uplink Anchor** to **Observed Serving Primary** while preserving the rule that active uplink CA is not inferred when NCOS does not expose uplink component-carrier telemetry.
- Corrected **Published Maximum Uplink CA** to use the published upload configuration for the service mode observed during the test instead of a generic modem-wide maximum.
- For 5G SA, tower identity now prefers `NR_CELL_ID` and `PHY_CELL_ID_5G`, with `CELL_ID` and `PHY_CELL_ID` retained as fallbacks.
- Validated the normalization logic against captured W1855-5GC 5G SA telemetry and W2255-5GF 5G NSA telemetry, including mixed LTE/NR component carriers and an active `0 MHz` NR carrier.
- No throughput-engine, WAN-selection, routing, scheduler, server-management, persistence, or SDK appdata architecture changes were made.

## v1.0.1

- Aligned Manual Tests WAN-selection presentation with Scheduled Tests.
- Manual Tests now presents **Active Primary WAN** plus every connected concrete WAN interface even when the device has only one connected WAN.
- Updated the Manual interface enable/disable guard so the selector remains available with one or more connected WANs and is disabled only with zero connected WANs or while a Manual Test is running.
- Preserved the existing `__active_wan__` alias, backend Active Primary WAN resolver, concrete interface values, capability evaluation, source routing, history identity, and reporting behavior.
- Removed the Light/Dark mode control from the sidebar navigation because it is an action rather than a navigation destination.
- Added an icon-only theme button beside Firmware in the top-right header using the existing moon/sun icon state.
- Added an immediate CSS hover/focus tooltip with dynamically updated **Switch to Dark Mode** / **Switch to Light Mode** text and matching accessibility label.
- Preserved existing `localStorage` theme persistence.
- Scope is frontend presentation/interaction, package version metadata, and documentation only. No backend Python, API route, test-engine, scheduler, routing, persistence, or SDK appdata changes were made.

## v1.0.0 — Speedtest Analyzer

- Rebranded the application from **Speed Test** to **Speedtest Analyzer** before the first external product release.
- Reset the public product version from the unreleased Speed Test `2.7.6` development baseline to **Speedtest Analyzer 1.0.0**.
- Renamed the SDK application source directory from `apps/speedtest_web` to `apps/speedtest_analyzer`.
- Established the new `[speedtest_analyzer]` SDK package identity and generated a new application UUID.
- Preserved established backend filenames, API paths, SDK appdata keys, JavaScript implementation names, throughput engines, and runtime architecture where renaming would add regression risk without user benefit.
- Lab validation on E400 confirmed that existing SDK appdata remained available after installing the rebranded application, including saved User iPerf3 servers, endpoint Reliability statistics, and test history.
- Added a lightweight inline SVG Speedtest Analyzer application mark combining a performance gauge and waveform.
- Added separate theme-aware SVG presentation for Light Mode and Dark Mode without external image, font, or runtime dependencies.
- Updated the expanded sidebar branding to display the Speedtest Analyzer application mark, product name, and application version.
- Updated the collapsed sidebar to display only the standalone application mark and hide the product name and version.
- Repositioned the collapsed sidebar expand control into its own row below the application mark so the control does not overlap or compete with the logo.
- Replaced the top application header with the **Speedtest Analyzer** wordmark.
- Renamed the primary **Manual Tests** navigation destination to **Test Center** because the page contains both Manual Tests and Scheduled Tests configuration.
- Retained **Manual Tests** and **Scheduled Tests** as the functional subsection terminology inside Test Center.
- Updated browser-title, report, CSV/export, README, Technical Guide, package metadata, and other appropriate user-facing branding to use Speedtest Analyzer terminology.
- Reset the user-facing README changelog to the Speedtest Analyzer `1.0.x` release family.
- Preserved the complete Speed Test 2.x pre-release engineering history below for traceability.
- The 1.0.0 rebrand is intentionally scoped to product identity, presentation, documentation, and packaging. It does not intentionally alter throughput execution, WAN selection, source routing, scheduling behavior, history schema, cellular telemetry, Carrier Activity, server selection, endpoint Reliability, device validation, or test-engine lifecycle protections.

## Pre-release Speed Test Development History

The following releases were internal development builds that preceded the Speedtest Analyzer product identity and were not externally published as customer releases.

## v2.7.6

- Split application documentation into a normal-user `README.md` and an engineering-focused `TECHNICAL_GUIDE.md`.
- Reworked the README around user workflows: installation, access, Manual Tests, test-engine selection, Public/User/Custom iPerf3 server usage, scheduling, results, Carrier Activity interpretation, reports, outputs, common troubleshooting, validation, and known limitations.
- Corrected outdated Quick Start guidance that required a user to add an iPerf3 server before testing; the README now reflects the bundled Public iPerf3 catalog introduced by the 2.7 server architecture.
- Consolidated validated standalone devices, validated controller + captive-modem combinations, and known engine limitations into concise user-facing tables.
- Moved detailed device-validation catalog behavior, known-defect matching, firmware gating, modem capability catalog maintenance, Carrier Activity internals, source routing, Netperf lifecycle handling, endpoint identity, listener retry, Reliability persistence, and advanced troubleshooting into the Technical Guide.
- Corrected the documentation hierarchy that previously placed the 2.7.0 iPerf3 server architecture underneath the Troubleshooting heading.
- Changed README changelog policy so the primary README contains only concise entries for the active `2.7.x` release family.
- Added a permanent release-family summary and retained the complete detailed engineering changelog in the Technical Guide.
- Defined the future documentation policy: when development moves to `2.8.x`, the README changelog resets to the `2.8.x` family while 2.7.x history remains in the Technical Guide.
- No intentional runtime, backend, frontend, test-engine, WAN-routing, scheduling, history-schema, cellular-telemetry, catalog, server-management, Reliability, or SDK appdata behavior changes.

## v2.7.5

- Added an independent Test Summary Date Range control with All History, Last 12 Hours, Last 24 Hours, Last 3 Days, and Older than 3 Days views. The selected range updates Summary tiles, Trends, per-engine sections, and speed graphs before the existing interface filters are applied.
- Added independent Test Log filters for Interfaces, Status, and Date with a Reset control. Test Log filters do not affect Test Summary data.
- Added Test Log pagination with 10, 25, 50, or 100 results per page, defaulting to the newest 10 matching tests.
- Updated History & Reports timestamp presentation to automatically use the viewer's browser timezone and regional 12-hour or 24-hour time convention. Test Log timestamps, Summary range dates, graph timestamps, and graph tooltips display local time while persisted history and CSV exports remain UTC.
- Preserved original persisted history indexes through Test Log filtering and pagination so Delete, Engine, Status, Carrier Aggregation, Cell Stats, tooltips, and Expand All actions continue to target the correct tests.
- Updated the device validation catalog for the current tested platform set, including validated standalone E400, E3000, R1900, R980, R2400, W1850, W1855, and W2255 platforms plus validated E3000 + W1850 and R2400 + RC1250 combinations.
- Added the confirmed **AER2200 + iPerf3** known defect reproduced on NCOS 7.25.121. iPerf3 is disabled for AER2200 while Netperf remains the documented workaround.
- Retained the existing **W2255 + Netperf** and **R2400 + RC1250 + Netperf** known-defect restrictions independently of overall device-validation status.
- Refreshed the bundled Public iPerf3 server catalog while retaining the five-region East, Southeast, Midwest, Southwest, and West structure. Individual packaged endpoints can be maintained without changing the documented regional architecture.


## v2.7.4

- Updated History & Reports interface filters so each All Tests, iPerf3, and Netperf filter group always retains at least one selected interface.
- Added the tested interface display name to graph point tooltips so results remain identifiable when multiple WAN interfaces are displayed together.


## v2.7.3

- Improved the History & Reports line graphs with immediate point tooltips, pointer-based interaction, and click-to-pin behavior so test details can be viewed without waiting for the browser's native hover tooltip.
- Added keyboard-accessible graph points and click-away behavior for pinned graph tooltips.
- Improved graph presentation by reserving additional space for the final timestamp and showing the actual number of plotted results while retaining the latest-10 maximum.
- Improved **Test Log expandable details** with clearer chevron indicators and pointer-based interaction for Engine, Status, Carrier Aggregation, and Cell Stats.
- Added immediate explanatory tooltips to expandable Test Log values, including Carrier Aggregation peak-carrier information and guidance to open the detailed CA view.
- Changed Test Log detail behavior so only one detail section is open for a given test while details from different test results may remain open for comparison.
- Retained the Engine, Status, Carrier Aggregation, and Cell Stats **Expand All** controls while enforcing the one-detail-section-per-test behavior.


## v2.7.2

- Replaced the History & Reports throughput bar charts with connected **Download** and **Upload line graphs** for easier performance-trend visualization.
- The graph continues to show the latest 10 test results in chronological order with throughput plotted in Mbps.
- Failed test measurements are plotted at `0 Mbps`, including `0 / 0` for fully failed tests, while partial tests preserve the successful measurement and plot the failed direction at zero.
- Added interactive Download and Upload legend controls that dim the unselected series for focused viewing while keeping both series available for comparison.
- Prevented both graph series from being deselected at the same time.


## v2.7.1

- Added direct termination of the active local iPerf3 subprocess when Stop is requested.
- Preserved the existing NCOS Netperf stop path while separating local iPerf3 process cancellation from native Netperf cancellation.
- Added protected active-iPerf3 process tracking so an in-progress Downlink or Uplink phase can be stopped instead of continuing to the configured duration.
- Added explicit **Test cancelled** handling before normal iPerf3 listener retry and primary-WAN bind-fallback processing.
- Preserved completed Downlink data for the intended Partial-result workflow when Uplink is cancelled.
- Kept the existing iPerf3 five-port retry budget, Public backup selection, Uplink server lock, WAN binding, source routing, and execution-slot cleanup behavior unchanged.
- Changed User Server **Save** behavior to Add-only.
- Added explicit duplicate feedback when a saved User endpoint already uses the same normalized Hostname/IP and Port/Range.
- Added an **Edit** action for saved User iPerf3 servers.
- Added editing for Friendly Server Name, Hostname/IP, Port/Range, City, and Country using the existing User Server form.
- Added **Update** and **Cancel Edit** form states.
- Preserved endpoint identity, schedule association, and Reliability history for Friendly Name, City, and Country-only edits.
- Treated Hostname/IP or Port/Range changes as endpoint identity changes.
- Added duplicate-endpoint protection for edited Hostname/IP and Port/Range combinations.
- Reused existing scheduled-server protection so changing a scheduled endpoint requires confirmation before the iPerf3 schedule is reset.
- Preserved User Server list order during edits and retained a single SDK appdata write after successful validation.
- Endpoint identity changes begin with fresh Reliability identity rather than transferring statistics from the previous endpoint.
- Full 2.7.1 runtime and platform validation remains pending.

## v2.7.0

- Added Public and User iPerf3 server-list modes.
- Added bundled read-only Public iPerf3 catalog sourced from `iperf3serverlist.net`.
- Added five Public regions: East, Southeast, Midwest, Southwest, and West.
- Added friendly Public server selection with actual endpoint information retained in History.
- Added Manual Custom Server support without adding ad-hoc endpoints to Reliability statistics.
- Added independent Public Region/server selection for Scheduled Tests.
- Added persistent User Server List management with add, delete, delete-all, template, import, and export.
- Added canonical User Server List JSON schema version 1.
- Added port-range and single-port examples to the downloadable User Server template.
- Added import-only compatibility for supported pre-2.7 User Server JSON formats.
- Changed User Server import workflow to select the JSON file first and then explicitly choose Merge or Replace.
- Added duplicate endpoint handling for Merge and schedule protection for Replace/Delete operations.
- Added a 120-character Friendly Server Name limit.
- Updated User Server template/export filenames to identify the Speed Test application.
- Added randomized unique-port selection with a maximum five-port budget per server.
- Added listener-attributable port retry without retrying generic WAN, DNS, routing, timeout, or system failures.
- Added one deterministic same-Region Public backup server after primary Downlink exhausts five eligible listener failures.
- Kept User Server tests locked to the configured server with no automatic server backup.
- Locked Uplink to the successful Downlink server and attempted the successful Downlink port first.
- Added actual Server Name, Hostname/IP, Downlink Port, and Uplink Port to iPerf3 History and CSV reporting.
- Added iPerf3 Reliability statistics for Successful Tests, Endpoint Failures, Failure Rate, and Most Failed Port.
- Limited Reliability table rows to saved servers that have actual test activity.
- Excluded Custom Server, WAN, DNS, routing, generic timeout, and system failures from Reliability endpoint-failure statistics.
- Added active-source Reliability reset with confirmation.
- Changed Reliability persistence to a 30-minute dirty-only checkpoint using the existing scheduler thread.
- Corrected schedule restart behavior so Auto-start on boot controls whether a persisted schedule resumes after restart.
- Rounded CSV Cellular Health values to one decimal place.
- Preserved existing Netperf, cellular telemetry, Carrier Aggregation, source-routing, validation-catalog, and modem-capability behavior.

## v2.6.5

- Added Carrier highlighting in expanded Cellular Details when the carrier differs from the previous cellular test, using the existing changed-field highlighting without adding Test Log columns, CSV fields, or history schema changes.
- Marked **R2400 + RC1250** as fully validated after physical testing. The confirmed **R2400 + RC1250 + Netperf** native NCOS defect remains tracked separately and Netperf is safely disabled only for that affected captive-modem selection.

- Replaced WAN-interface byte-counter deltas with engine-reported test byte totals so production/user traffic on the selected WAN is not counted as speed-test data.
- iPerf3 now records `end.sum_received.bytes` for download and `end.sum_sent.bytes` for upload; Netperf records local receive/send byte totals from the validated native result; Ookla records its native result byte totals when available.
- Failed directions no longer inherit unrelated WAN traffic as transferred data. The result tiles and saved history show data only for directions that produced valid engine-specific results.
- Test Log details now show **Data Downloaded**, **Data Uploaded**, and **Total Test Data** separately. Existing saved-history field names and the CSV layout remain unchanged for compatibility.

- Added a catalog-driven `known_defects` section to `device_validation_catalog.json` so confirmed test-engine defects can be maintained without hard-coded model restrictions in Python.
- Added simple NCOS firmware tracking using `major.minor.patch` values such as `7.26.60`; full build hashes are not required for defect matching.
- Added `fixed_in` handling: a confirmed defect with `fixed_in: null` remains restricted on all firmware, while the specified fixed release and newer automatically re-enable the affected engine.
- Migrated the existing standalone **W2255 + Netperf** restriction from hard-coded Python logic into the validation catalog while retaining the existing W2255 Netperf lifecycle safeguards.
- Added the confirmed **R2400 + RC1250 + Netperf** defect reproduced on NCOS 7.26.60. The restriction applies only when the RC1250 captive WAN is selected; R2400 internal and other WAN interfaces remain unaffected.
- Added selected-WAN defect evaluation using logical controller/captive identity rather than hardware-specific `rm_*` interface identifiers.
- Manual and Scheduled engine selectors now disable catalog-restricted engines dynamically for the selected interface and automatically move to an available engine when the current selection becomes restricted.
- Added persistent known-defect warning banners that display the full affected combination, such as **R2400 + RC1250 + Netperf**, even after the UI switches away from the disabled engine.
- Added backend enforcement for Manual Tests, enabled Scheduled Tests, and runtime Active Primary WAN resolution so UI restrictions cannot be bypassed through direct API requests.

## v2.6.4

- Added a generic Netperf watchdog and cleanup policy for all supported devices so an application-owned Netperf test that exceeds its requested duration plus 30 seconds is automatically cancelled and verified stopped.
- Added shared Netperf service preflight handling to prevent a legitimate Netperf test started from NCOS, NCM, or another client from being interrupted while still allowing clearly stale jobs to be reclaimed.
- Added stale-job detection using the native Netperf command duration when available, with a conservative 120-second fallback when the original duration cannot be determined.
- Replaced the previous `duration + 60` progress-based zombie threshold with bounded lifecycle handling that can recover hung native Netperf jobs before they remain active for several minutes.
- Updated user cancellation and TCP_RR timeout handling to use the same native `control/netperf/run = -1` kill-and-verify cleanup path.
- Cleanup now performs a five-second verification window followed by one final kill and short verification if NCOS still reports the native Netperf service as active.

- Added **Active Primary WAN** as the first and default interface selection for Manual Tests, matching the existing Scheduled Tests behavior.

- When only one connected WAN exists, Manual Tests now shows only **Active Primary WAN** instead of duplicating the same physical WAN in the selector. The existing Primary WAN indicator continues to show the actual interface name and IP address.

- When multiple WANs exist, **Active Primary WAN** remains the default while all concrete WAN interfaces remain available for explicitly pinned tests.

- Active Primary WAN is resolved at test execution time to exactly one concrete NCOS interface before WAN counters, carrier telemetry, Netperf/iPerf3 execution, history, CSV, and reporting logic run.

- The `__active_wan__` selector alias is never persisted as interface identity. Results, history, and reporting continue to use the actual tested interface and existing friendly WAN labels.

- Active Primary WAN resolution fails closed if NCOS cannot identify the current primary interface. No alternate WAN, automatic interface selection, or fallback path is attempted.

- Manual and Scheduled Tests now use the same backend Active Primary WAN resolver for consistent interface-selection behavior.

- Added generic Netperf fresh-run protection to prevent terminal output from a previous Netperf phase from being accepted as the result of a newly requested phase while NCOS is still starting the new native test.

- Netperf now snapshots the native output state before each run and waits for fresh `running` or numeric-progress evidence before trusting inherited terminal errors.

- Previous-phase terminal errors are ignored when they match the pre-run snapshot, identify the opposite Netperf direction, or reference a different WAN device.

- Added a bounded five-second startup grace for ambiguous Netperf terminal errors so legitimate immediate failures are still reported while delayed NCOS startup does not orphan the newly started native process.

## v2.6.3

- Added RC1250 to the modem CA capability catalog using the existing 5GF family and Ericsson RC1250 datasheet reference, allowing Expanded CA Information to resolve the captive modem as RC1250 instead of the R2400 controller.
- Corrected R2400 internal-modem detection when NCOS exposes the internal modem through the captive/remote data model with `internal_captive: true`, preventing R2400SDX from being treated as a physical captive modem.
- Updated cellular WAN ownership labels so NCOS internal-captive records display as the controller's **Internal** modem while true attached modem devices continue to display as **Captive**.
- Preserved standalone R2400 validation behavior and physical captive-modem deduplication across multiple SIM records.

## v2.6.2

- Added modem ownership to cellular WAN labels so overlapping SIM numbers can be distinguished without changing routing identities.
- Standardized the **Ethernet WAN** and **Wi-Fi as WAN** display labels; stable **Satellite WAN-XXXX** identities are unchanged.

## v2.6.1

- Added the maintainable `device_validation_catalog.json` for standalone and captive-modem validation.
- Added live controller-plus-captive detection with dual-SIM physical-adapter grouping.
- Added validated standalone W1850 and W1855 entries while preserving code-based technical safeguards.
- Added safe handling and maintenance guidance for pending, unlisted, missing, or malformed validation data.

## v2.6.0

- Added the external `modem_ca_capabilities.json` catalog for published modem carrier-aggregation capability references.
- Added internal and captive modem matching with exact-variant and available-variant fallback behavior.
- Added separate **LTE**, **5G NSA**, and **5G SA** maximum CA rows with **DL Max** and **UL Max** carrier totals.
- Added **Not Supported** handling when a mode or direction does not have a published numeric configuration.
- Retained detailed LTE and NR maximum support combinations in the Peak section.
- Clarified that NCOS RX channel telemetry represents observed Downlink CA.
- Renamed the expanded Progress headings from Download and Upload to Downlink and Uplink.
- Retained the dynamic carrier timeline only for observed Downlink activity.
- Added a fixed **Observed Uplink Anchor** from the first valid upload-phase serving-carrier snapshot.
- Added **Current Uplink CA: Not reported by NCOS** and retained the published maximum Uplink CA reference.
- Documented that active Uplink CA can be added when NCOS exposes the required TX channel and uplink component-carrier telemetry.
- Added `RFBANDWIDTH_5G` as the preferred source for the upper 5G NR bandwidth field while retaining alternate NCOS field names.
- Added friendly display labels for Ethernet WAN, Wi-Fi as WAN, supported cellular carriers, unknown-carrier SIM slots, and satellite WANs.
- Added stable **Satellite WAN-XXXX** labels so multiple Starlink connections can be distinguished.
- Prevented an `mdm-*` UID by itself from being treated as proof of a cellular WAN.
- Routed Satellite WAN statistics through the Ethernet/non-cellular reporting path, suppressing cellular diagnostics, Carrier Activity, Cell Stats controls, and cellular CSV values.
- Prevented non-cellular WAN tests from creating or polling a live Carrier Activity collector and added the **No active cellular connection** tile state.
- Added display and export protection for existing Starlink history that contains previously saved cellular-looking metadata.
- Preserved raw interface, WAN UID, source-routing, filtering, scheduling, and CSV identities.
- Added a resilient HTTP-server hostname lookup fallback for NCOS devices whose internal hostname cannot be encoded as a DNS label.

## v2.5.3

- Added live **Active Carriers** status to Manual Tests.
- Added fresh cellular-state loading on page load and page refresh.
- Added Carrier Activity history with **Baseline / Progress / Peak** views.
- Added independent Download and Upload carrier timelines.
- Added approximately two-second carrier polling during tests.
- Added phase-aware timing so failed iPerf3 ports, setup delays, and Netperf result-settle delays are excluded from successful traffic timelines.
- Added monotonic-clock protection against router/NTP wall-clock jumps.
- Added role-aware carrier display including PCell, SCell, and direct NR carrier handling.
- Preserved same-band carriers when NCOS reports them as distinct component carriers.
- Preserved active carriers that explicitly report `0 MHz` and added orange warning/display behavior.
- Added NR-idle Cell Stats handling with the `NR idle — throughput came from LTE only` warning.
- Added Carrier Activity data to CSV exports.
- Updated CSV Carrier Activity progress text to use spreadsheet-friendly ASCII separators.
- Added live iPerf3 server-port attempt and retry status messages.
- Validated R1900 iPerf3 source-route steering to a non-primary cellular WAN.
- Retained enhanced Netperf lifecycle handling for R980 and E3000.
- Retained the W2255 native Netperf disable due to the reproduced NCOS hang/runaway behavior.
- Validated 2.5.3 Carrier Activity behavior on E400, E3000, R1900, R980, and W2255 across T-Mobile, Verizon, and AT&T radio behaviors.

## v2.4.2

- Added model-family capability detection.
- Added `/api/capabilities`.
- Added validated/limited/unvalidated UI states.
- Disabled Netperf on W2255.
- Added enhanced Netperf lifecycle handling for R980 and E3000.
- Added fresh-run detection and result settle validation.
- Added bounded Netperf timeout cleanup and one retry.
- Added shared compatibility alerts to Manual Tests and Scheduled Tests.
- Renamed **Run Tests** to **Manual Tests**.
- Updated **Scheduled Tests** heading and UI consistency.
- Removed obsolete iPerf3 primary-WAN-only warnings.
- Scheduled WAN selection now defaults to the active primary WAN.
- Preserved existing iPerf3 routing, cleanup, and port-retry behavior.

---

# 17. Validation Scope

The compatibility information in this README reflects testing performed against the specific firmware versions listed near the top of this document.

A later NCOS release may change native routing, Netperf, WAN, modem-diagnostic, or SDK behavior. When deploying to a different firmware version or device family, validate the required test engines manually before relying on scheduled results.
