# Speedtest Analyzer Technical Guide

Engineering and advanced operational reference for the Cradlepoint Speedtest Analyzer SDK application.

**Documentation version:** 1.1.3
**Application release family:** 1.1.x
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

The current branded application release is `1.1.3`. Speedtest Analyzer 1.1.3 continues the engineering lineage of the unreleased Speed Test `2.7.6` development baseline. Release `1.1.3` adds optional, Device-scoped GeoView provider enrichment (see [Section 19](#19-geoview-provider-enrichment-113)); all other `1.1.2` behavior is preserved.

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

Configuration is stored through SDK appdata. As of `1.1.2`, normal configuration
uses a **two-key canonical model** (see [Section 18](#18-two-layer-configuration-management-112)
for the full architecture):

| Appdata | Purpose | Written locally by the app |
|---|---|---|
| `speedtest_analyzer_group` | NCM Group configuration standard. Read/validated only. | **Never** |
| `speedtest_analyzer_device` | Locally managed Device configuration and Device overrides. | Yes (only canonical key the app writes/deletes) |

Both canonical documents are schema-versioned, section-sparse, and carry
**independent** revisions (`group_revision` / `device_revision`). The effective
configuration in RAM is a whole-section merge of `DEVICE > GROUP > DEFAULT`.

Runtime/statistics values are intentionally **not** configuration and are stored separately:

| Appdata | Purpose |
|---|---|
| `iperf_server_stats` | iPerf3 endpoint Reliability statistics (dirty-only checkpoint) |
| `speedtest_results` | Output target when result-write outputs are enabled |

The following fragmented keys are **migration inputs only** and are never written by
`1.1.2`. They are read once, if present, to convert an earlier installation into a
Device document, then left untouched:

| Legacy appdata | Historical purpose |
|---|---|
| `speedtest_schedule` | Scheduled-test configuration |
| `iperf_server_settings` | iPerf3 server source/mode |
| `iperf3_servers` | User Server List |
| `netperf_servers` | Saved Netperf server entries |
| `speedtest_outputs` | Configured output targets |
| `geoview_settings` | GeoView configuration (schema 2) |
| `speedtest_analyzer` | Abandoned experimental single-key document |

GeoView configuration that previously lived in the standalone `geoview_settings` key is
now embedded as the `geoview` section inside the canonical documents (see [Section 11.6](#116-geoview-settings-persistence)).
`cellular_geo.py` still owns GeoView schema-2 validation; the canonical layer delegates
to it and strips runtime GPS coordinates before persistence.

Exact internal JSON structures may change between application versions. Configuration
should normally be managed through the web interface rather than edited directly. The
`speedtest_analyzer_group` value is authored in NCM (or pasted by an administrator), never
written by the device.

---

## 2.6 Cellular Analysis and GeoView modules

The v1.1.x architecture separates retained-history analysis, configuration, serving-location enrichment, protected credentials, contribution, HTTP orchestration, and presentation.

Primary components are:

- `cellular_analysis.py`
  - Normalizes retained serving-cell telemetry.
  - Builds interface/history-scoped Cellular Analysis.
  - Builds the site-wide serving-cell inventory consumed by GeoView.
  - Preserves traffic-time handoffs and identifiable serving cells that may not be present in the final post-test snapshot.

- `cellular_geo.py`
  - Owns the non-secret GeoView configuration schema.
  - Normalizes `provider` (`none` / `opencellid`), `contribution_enabled`, Site Location sources/values, and optional provider/cache tuning.
  - Integrates with the canonical v1.1.2 Configuration Manager.
  - Contains no protected credential values and makes no external network calls.

- `geo_identity.py`
  - Converts site-inventory cells into provider-ready primary serving identities.
  - LTE-only resolves the LTE primary ECI; NSA resolves the LTE anchor ECI; SA resolves the NR primary NCI.
  - Requires MCC/MNC/TAC plus ECI/NCI and never substitutes PCI, band, or channel for Cell ID.

- `geo_providers.py`
  - Implements OpenCellID serving-cell lookup (`/cell/get`).
  - Implements OpenCellID observation submission (`/measure/add`).
  - Implements Google Geocoding for Site Address forward geocoding.

- `geo_secrets.py`
  - The only module permitted to access `config/certmgmt/certs` or call `cp.decrypt()`.
  - Stores server-side Google/OpenCellID keys separately from the browser Maps JavaScript key.
  - Exposes metadata-only credential status and write-only mutation paths.

- `geo_cache.py`
  - Maintains persistent `tmp/geoview_cell_cache.json`.
  - Uses provider + full normalized serving identity as the cache key.
  - Defaults to 30-day positive and 6-hour `not_found` TTLs.

- `geo_contributions.py`
  - Implements optional OpenCellID observation contribution.
  - Enforces Internal/Captive cellular eligibility, primary-identity-only submission, observed-position semantics, and persistent 20-meter same-cell dedupe in `tmp/geoview_contribution_ledger.json`.

- `geo_resolver.py`
  - Owns the single bounded OpenCellID resolution job and all lookup failure containment.

- `speedtest_web.py`
  - Serves Cellular Analysis and GeoView data.
  - Performs Site Address geocoding on Save.
  - Exposes resolve/status, credential, map-bootstrap, reset, and manual-contribution endpoints.
  - Invokes the completed-test Device-GPS contribution hook after eligible cellular tests.
  - Keeps `GET /api/cellular_analysis` local-only; it never initiates a serving-location lookup.

- `index.html`
  - Renders Local Only and Geolocation Services modes.
  - Loads Google Maps JavaScript only for the interactive geographic view.
  - Renders Site and resolved serving-cell markers, popups, Site Context, Configure GeoView, contributions, and the self-contained SVG report replacement.

GeoView does not introduce a second continuous cellular telemetry collector. It reuses retained Speedtest Analyzer history and the Cellular Analysis normalization model.

Non-secret GeoView configuration is persisted inside the canonical configuration documents as the `geoview` section. The old standalone `geoview_settings` key is migration input only.

Protected provider credentials are stored separately in NCOS certificate management. The cell-location cache and contribution ledger are local runtime files under `tmp/`.

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

Beginning with v1.1.3, the existing iPerf3 JSON result is also used to retain additional TCP measurement telemetry. The Uplink phase provides automatic TCP RTT average/minimum/maximum and device-side retransmission counts. The Downlink phase retains remote sender retransmission totals where iPerf3 reports them.

An optional supplemental jitter probe can run after a successful TCP test. This measurement does not replace or alter the validated TCP throughput, retry, server-selection, source-routing, or WAN-guard architecture.

TCP RTT is observed while the TCP Uplink is actively transferring data and is therefore a loaded measurement rather than an idle or pre-transfer latency sample.

The detailed source-routing behavior is documented later in this guide. The v1.1.3 RTT, retransmission, jitter, and compact telemetry architecture is documented in Section 20.

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

Beginning with v1.1.3, completed iPerf3 results can additionally persist:

- `latency_ms` — average device-side Uplink TCP RTT.
- `latency_min_ms` — minimum sampled TCP smoothed RTT during Uplink.
- `latency_max_ms` — maximum sampled TCP smoothed RTT during Uplink.
- `jitter_ms` — jitter when the optional supplemental probe succeeds.
- `retransmissions` — device-side TCP Uplink sender retransmission count.
- `iperf3_tcp` — compact engineering telemetry for Downlink and Uplink.

CSV continues to use the existing `Latency_ms` and `Jitter_ms` columns and adds `TCP_Retransmissions`.

The compact `iperf3_tcp` object is intentionally not flattened into the normal CSV export. It remains available as engineering evidence for future correlation, KPI, and event-analysis features.

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

Beginning with v1.1.3, the persisted `include_latency` field has engine-specific meaning while retaining the existing configuration schema:

- For **iPerf3**, `include_latency=true` requests the supplemental Jitter measurement. TCP RTT is automatic and does not depend on this field.
- For **Netperf**, `include_latency=true` retains the existing Latency/Jitter behavior.

The Scheduled Tests UI therefore labels the same persisted control **Jitter** for iPerf3 and **Latency/Jitter** for Netperf.

### 10.5.1 Persisted `enabled` / `autostart` versus runtime `running`

As of `1.1.2`, schedule enablement is modeled with three distinct values. The two
persisted fields are **independent**; the runtime field is derived and never persisted:

| Field | Kind | Meaning |
|---|---|---|
| `enabled` | persisted | The schedule is configured to run. |
| `autostart` | persisted | The schedule should resume automatically when the application starts. |
| `running` | runtime-only | Whether the scheduler thread currently fires this schedule. |

The scheduler thread checks `running`, not `enabled`. `running` is computed by the shared
helper `configuration_manager.compute_schedule_running(enabled, autostart, is_startup)`,
which both the config hot-reload path and the tests use as the single source of truth:

- **Startup / boot apply** (`is_startup=True`): `running = enabled AND autostart`.
  An enabled-but-not-autostart schedule does **not** auto-start after an application or
  router restart.
- **Interactive save / apply** (`is_startup=False`): `running = enabled`.
  An explicit user Save runs the schedule immediately, regardless of `autostart`.
- `enabled = false` never runs, regardless of `autostart` or startup.

The boot rule is applied to the runtime `running` value only. Persisted `enabled` is
**never** coerced to `false` at startup, so an enabled-but-not-autostart schedule survives
a restart as `enabled = true` (Enable stays checked in the UI) while `running = false`.

**No-op save that still applies runtime.** After a restart, a persisted
`enabled = true / autostart = false` schedule is `running = false`. An explicit unchanged
Save of that schedule is a persistence **no-op** — the manager returns `no_change`, writes
nothing, and does not increment `device_revision`. The schedule save path treats an explicit
Save as an apply/runtime action, so it sets `running = enabled` directly even on the no-op
result. This lets the user start the schedule without forcing a write or a revision. This
behavior is schedule-specific and does not change the global no-op persistence semantics.

`GET /api/schedule` returns `enabled`, `autostart`, and `running` so the UI can present three
honest states: **Active** (`running`), **Enabled — Not Running** (`enabled && !running`,
e.g. after a restart with Auto-start off), and **Disabled** (`!enabled`). The countdown and
"next run" derive from `running`.

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

## 11.3 Cellular Analysis scope versus GeoView scope

The lower Cellular Analysis workspace and Site Cellular GeoView intentionally use different scopes.

Lower Cellular Analysis:

- Applies the selected cellular Interface.
- Applies the selected retained-history range.
- Applies the selected serving-cell scope when requested.
- Answers questions about the selected interface/history context.

Site Cellular GeoView:

- Uses every retained cellular test available to the application.
- Includes all retained cellular interfaces.
- Excludes plain Ethernet/non-cellular records.
- Ignores the lower page Interface and History Range selectors.
- Shows which identifiable serving cells have been observed at the Site and, when enabled, where those serving cells are estimated to be located relative to the configured Site.

GeoView does not trigger a second modem-telemetry collection pass.

## 11.4 Site-wide serving-cell inventory and identity

`build_site_cell_inventory(history)` constructs the site-wide GeoView inventory.

The builder:

1. Filters retained history to cellular records.
2. Sorts cellular records chronologically.
3. Reuses the traffic-aware serving-cell normalization/distribution engine.
4. Excludes the aggregate Unknown identity from GeoView markers.
5. Preserves identifiable cells observed only during an in-test handoff.
6. Deduplicates each serving cell once per test for observation counts.
7. Aggregates the same normalized serving-cell identity across cellular interfaces.
8. Returns site-wide tests, identifiable cells, and observed cellular interfaces.

Geographic lookup is primary-serving-cell only:

- LTE-only -> LTE primary ECI.
- NSA -> LTE anchor ECI.
- SA -> NR primary NCI.

Lookup requires MCC, MNC, TAC, and the complete ECI/NCI.

PCI, band, channel, EARFCN, and NR-ARFCN are descriptive radio fields and are never substituted for Cell ID.

NCOS remains authoritative for the observed serving identity and radio mode. OpenCellID enriches that identity with an estimated geographic position.

## 11.5 GeoView presentation modes

GeoView has two user-facing modes.

### 11.5.1 Local Only

`provider = none` is **Local Only** and remains the default.

Local Only:

- Performs no OpenCellID serving-location lookup.
- Does not load the Google geographic map.
- Keeps local Cellular Analysis and the retained site-wide serving-cell inventory functional.
- Hides cached geographic enrichment without deleting the cache.

### 11.5.2 Geolocation Services

`provider = opencellid` is **Geolocation Services**.

The final v1.1.3 service roles are separate:

- **OpenCellID** -> Estimated Serving Cell Location lookup and optional contribution.
- **Google Geocoding API** -> Site Address forward geocoding only.
- **Google Maps JavaScript API** -> browser-side interactive map only.

When the Maps JavaScript key is available, the browser map renders the configured Site plus already-resolved serving-cell markers.

The compact marker popup emphasizes:

- Stable A/B/C label and carrier.
- Primary role and band.
- **Estimated Serving Cell Location**.
- Distance and compass direction from the configured Site.
- Retained test usage count.

Detailed PLMN/TAC/PCI/Cell ID/RF history remains in the lower Cellular Analysis workspace.

The right-side Estimated Serving Cell Location panel shows carrier/label, primary role/band, coordinates, Copy, and Site distance/direction.

Provider metadata such as OpenCellID range/sample/changeable values is not repeated in the operator-focused presentation.

## 11.6 GeoView configuration, Site Location, and persistence

`cellular_geo.py` owns the schema-v2 non-secret GeoView configuration.

GeoView is persisted as the `geoview` section inside the canonical v1.1.2 configuration documents (`speedtest_analyzer_device` / `speedtest_analyzer_group`).

The old standalone `geoview_settings` key is migration input only.

Current normalized fields include:

    {
      "schema_version": 2,
      "configured": false,
      "provider": "none",
      "contribution_enabled": false,
      "active_location_source": "device_gps",
      "locations": {
        "device_gps": {
          "latitude": null,
          "longitude": null
        },
        "manual_coordinates": {
          "latitude": null,
          "longitude": null
        },
        "site_address": {
          "address": "",
          "latitude": null,
          "longitude": null
        }
      }
    }

Supported mode values are:

- `none` — Local Only
- `opencellid` — Geolocation Services

The three Site Location methods are stored independently:

- `device_gps` — last explicitly saved valid Device GPS coordinates.
- `manual_coordinates` — fixed user-entered latitude/longitude.
- `site_address` — literal address plus coordinates derived by Google forward geocoding when saved.

Site Address geocoding occurs on Save/Apply using the private Google Server API key. It does not run on every page load.

Device GPS remains explicit/on-demand. NCOS `0.0, 0.0`, no-lock, or invalid coordinate states are not accepted as a usable current fix.

Protected provider credentials are not stored in canonical GeoView configuration.

## 11.7 GeoView HTTP API

The current v1.1.3 UI uses:

| Method / Path | Purpose |
|---|---|
| `GET /api/cellular_analysis` | Returns local Cellular Analysis plus site-wide GeoView inventory and cached enrichment. Never initiates a serving-location lookup. |
| `GET /api/geo_settings` | Returns normalized effective GeoView settings. |
| `POST /api/geo_settings` | Validates and persists GeoView settings and performs Site Address forward geocoding when required. |
| `GET /api/geo_gps` | Performs one explicit NCOS GPS-status request. |
| `GET /api/geo/status` | Returns metadata-only OpenCellID resolve-job state/counts. |
| `POST /api/geo/resolve` | Starts or reuses the single bounded OpenCellID resolution job. |
| `GET /api/geo/creds/status` | Returns metadata-only protected-credential status. |
| `POST /api/geo/creds/record/update` | Write-only update of a server or browser-key certmgmt record. |
| `POST /api/geo/creds/record/clear` | Clears one protected field or record. |
| `POST /api/geo/creds/reset` | Clears all three credentials, disables contribution, switches to Local Only, and preserves Site Location/history/cache. |
| `GET /api/geo/mapjs` | Returns only the browser-restricted Maps JavaScript key plus Site/cached serving-cell marker data. |
| `POST /api/geo/contribute` | Manual OpenCellID contribution for a validated Manual Site Location. |

`GET /api/geo/mapjs` never returns the Google Server key or OpenCellID key and never initiates serving-cell resolution.

## 11.8 Credential, cache, contribution, and export boundaries

### Protected credentials

`geo_secrets.py` splits credentials across two stable NCOS certmgmt records:

- `speedtest_analyzer_geo_server`
  - `api_key` -> private Google Server API key for Site Address geocoding.
  - `opencellid_key` -> OpenCellID lookup/contribution key.

- `speedtest_analyzer_geo_mapjs`
  - `maps_js_api_key` -> browser-restricted Google Maps JavaScript key.

NCOS stores the certmgmt `key` field encrypted at rest and `cp.decrypt()` recovers the bundle on-router only when needed.

Server/OpenCellID keys are never returned to the browser.

The separate browser Maps JavaScript key is intentionally returned only by `/api/geo/mapjs` when rendering the map.

### OpenCellID lookup cache

`geo_cache.py` persists safe results in:

    tmp/geoview_cell_cache.json

Default TTLs:

- Resolved location: 30 days.
- `not_found`: 6 hours.

Authentication, quota, timeout, no-Internet, and provider errors are not persisted as reusable locations.

Reset Credentials intentionally preserves this cache.

### OpenCellID contribution

Contribution is `false` by default.

`geo_contributions.py` sends where the router observed an eligible primary serving cell. It never submits the provider-estimated serving-cell coordinates.

Eligibility is restricted to Internal/Captive cellular observations with complete LTE-primary, NSA-anchor, or SA-NR-primary identity.

With Device GPS, the completed-test hook can submit automatically after an eligible completed cellular test when the required conditions are met.

With Manual Site Location, `/api/geo/contribute` scans retained history and submits the most recent eligible observation for each unique primary serving cell using the current validated manual Site coordinates.

The persistent ledger:

    tmp/geoview_contribution_ledger.json

stores identity plus last successful latitude/longitude/timestamp.

The same identity within 20 meters is skipped. Movement of 20 meters or more makes it eligible again. A different identity is eligible immediately.

### Static report/export

The live Google Maps DOM is never copied into the standalone report.

Export replaces it with a deterministic self-contained SVG showing Site and resolved serving-cell locations, relative vectors, carrier-aware labels, scale, and location details.

Google Maps runtime CSS referencing external Google assets is excluded from the exported CSS.

The integrity validator remains strict. The report contains no provider credential and requires no Google Maps runtime asset or network access.

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
| **1.1.x — Cellular Analysis, GeoView, configuration, and measurement telemetry** | Historical serving-cell analysis, traffic-aware handoff preservation, selected-cell RF/radio-resource summaries, self-contained HTML/PDF-ready reporting, site-wide GeoView with Local Only and Geolocation Services modes, OpenCellID estimated serving-cell locations/contribution, Google Site Address geocoding and interactive Maps JavaScript presentation, protected Device credentials, the two-key NCM Group / Device configuration model introduced in v1.1.2, and v1.1.3 iPerf3 TCP RTT, retransmission, Jitter, and compact interval telemetry. |
| **1.0.x — Speedtest Analyzer** | New product identity and visual branding, Test Center navigation, theme-aware SVG application mark, fresh SDK package identity, and continuation of the validated pre-release 2.7.6 runtime architecture. |
| **2.7.x — Speed Test pre-release** | Public/User iPerf3 server architecture, bounded listener retry, endpoint Reliability, User Server editing, iPerf3 cancellation, History & Reports usability, expanded platform validation, and the 2.7.6 documentation split. |
| **2.6.x** | External modem capability catalog, device-validation catalog, known-defect framework, WAN identity improvements, Active Primary WAN behavior, and expanded Netperf lifecycle protection. |
| **2.5.x** | Carrier Activity, cellular telemetry, phase-aware CA timelines, source-routing validation, engine-reported data-volume accounting, and early platform-specific protections. |
| **2.4.x** | Model-family capability detection, compatibility states, shared Manual/Scheduled compatibility alerts, and early enhanced Netperf lifecycle behavior. |

---

# 16. Detailed Engineering Changelog

This section is the permanent engineering history for Speedtest Analyzer and its unreleased Speed Test development lineage.

Speedtest Analyzer `1.0.0` was created from the validated Speed Test `2.7.6` development baseline before external publication. The version reset represents a product-brand and SDK-package identity reset rather than a rewrite of the throughput, routing, scheduling, telemetry, history, or server architectures.

## v1.1.3

Completed the geographic GeoView feature on top of the v1.1.2 configuration foundation. v1.1.3 resolves **cellular serving infrastructure** through OpenCellID and keeps router/Site location as an independent reference point. See [Section 19](#19-geoview-geolocation-services-and-opencellid-contributions-113).

- Added **Local Only** (`provider=none`) and **Geolocation Services** (`provider=opencellid`) modes.
- Added OpenCellID `/cell/get` serving-location resolution for eligible primary serving identities.
- Locked the primary identity model: LTE -> LTE primary ECI; NSA -> LTE anchor ECI; SA -> NR primary NCI.
- Split GeoView secrets into `speedtest_analyzer_geo_server` and `speedtest_analyzer_geo_mapjs`.
- Added Site Address forward geocoding using Google Geocoding.
- Added the interactive Google Maps JavaScript GeoView with Site plus cached/resolved serving-cell markers, carrier-aware labels, distance/direction, and operator-focused popups.
- Added persistent OpenCellID cache `tmp/geoview_cell_cache.json` with 30-day resolved and 6-hour `not_found` defaults.
- Added `geo_contributions.py` and optional OpenCellID observation contribution, Off by default.
- Added Device-GPS automatic contribution after eligible completed cellular tests and Manual Site Location contribution from retained history.
- Added persistent 20-meter same-cell dedupe in `tmp/geoview_contribution_ledger.json`.
- Restricted contribution to Internal/Captive cellular observations and primary serving identity only.
- Added **Reset Credentials** while preserving Site Location, history, and cached serving-cell locations.
- Hardened standalone Cellular Analysis export by replacing the live Google map with an inline SVG and excluding Google Maps runtime resources.
- Live E400 validation confirmed multi-cell geographic rendering and OpenCellID contribution, including `2 submitted · 0 duplicates skipped`.
- Preserved v1.1.2 configuration inheritance/migration behavior and non-GeoView Speedtest functionality.
- Added automatic iPerf3 TCP RTT reporting from the device-side Uplink sender, including average, minimum, and maximum smoothed RTT.
- Added device-side Uplink TCP retransmission reporting and retained remote Downlink sender retransmissions inside the compact engineering telemetry block.
- Added compact per-interval iPerf3 telemetry for future correlation, including throughput, RTT, RTT variation, retransmissions, congestion window, and send-window observations.
- Added an optional one-shot jitter measurement after successful TCP throughput using the same selected server, successful port, source IP, and bind device.
- Kept the supplemental jitter phase outside the existing TCP listener retry/failover budget and non-fatal to the already-completed TCP test.
- Added pre-measurement and post-measurement WAN-path validation so a path change causes supplemental Jitter to be skipped or discarded without invalidating the completed TCP test.
- Added engine-aware Manual and Scheduled controls: **Jitter** for iPerf3 and **Latency/Jitter** for Netperf.
- Updated iPerf3 live results to identify loaded RTT as **TCP RTT**, History to show average/minimum/maximum TCP RTT and retransmissions, and CSV to populate `Latency_ms`, `Jitter_ms`, and `TCP_Retransmissions`.
- Validated Manual iPerf3 operation with Jitter disabled and enabled on Ethernet and cellular WANs, Scheduled iPerf3 Jitter execution, History persistence, compact hidden telemetry, and CSV export.

## v1.1.2

### Two-layer configuration management

- Introduced the two canonical SDK appdata documents `speedtest_analyzer_group` (read/validated only; never written locally) and `speedtest_analyzer_device` (the only canonical key the app writes/deletes), replacing the fragmented per-feature keys as the source of truth. See [Section 18](#18-two-layer-configuration-management-112).
- Effective configuration is a whole-section merge `DEVICE > GROUP > DEFAULT` resolved by section-key presence, including authoritative falsey values (`[]`, `{}`, `false`, `""`).
- Documents are section-sparse with independent `group_revision` / `device_revision`; management state is derived from key presence rather than stored metadata.
- Added exact-name appdata matching, read-back verified Device writes, and normalized no-op detection (identical proposed body → zero writes, no revision increment, no hot reload).
- Migrated GeoView persistence from the standalone `geoview_settings` key into the canonical `geoview` section, delegating schema-2 validation to `cellular_geo.py` and stripping runtime GPS coordinates before persistence.
- Fragmented legacy keys and the abandoned experimental `speedtest_analyzer` single key are migration inputs only; conversion builds a schema-1 Device document and never modifies the source keys.
- Added a Settings page exposing derived configuration state, per-section effective sources, Device Overrides, Migrate to NCM Group, Update NCM Group Configuration, Reset, and a separate Factory Reset. Factory Reset never touches `speedtest_analyzer_group`.

### Reset dependency validation

- Section reset now validates the proposed effective configuration before persisting. When resetting one section alone would create an incompatible configuration (iPerf3 schedule server family versus effective server mode), the backend returns `dependency_reset_required` with `required_reset_sections`, a human-readable reason, and `reset_target`, and writes nothing.
- Added confirmed atomic coupled reset: removing the coupled overrides in one transaction (one `device_revision` increment or a single Device-key delete), one hot reload, Group untouched, with the final effective configuration re-validated before write.
- Fixed reset success wording to use the backend-derived `reset_target` so the message names the true destination (NCM Group versus Built-in Default). Reset All validates the final `GROUP + DEFAULT` effective configuration before deleting the Device key.

### Update NCM Group Configuration

- Added promotion of selected current Device overrides into an existing NCM Group standard, offered only in the `group_with_device_overrides` state and distinct from the pure Device-to-Group migration.
- The candidate is a deep copy of the current Group document with only the selected sections replaced/added, `group_revision = current + 1`; unrelated Group sections and unselected overrides are preserved. Nothing is written locally.
- Dependency validation runs against the proposed revised Group; GeoView promotes the Device-GPS policy with runtime coordinates stripped and blocks non-promotable manual/site sources.
- Added a `(group_revision, device_revision)` reconciliation token that aborts validate and cleanup if either layer changes mid-workflow, with a distinct `reconcile_aborted` result that requires restarting the workflow.
- After the revised Group validates on the device, only the promoted sections are trimmed from the Device document; an emptied Device document is deleted. A cleanup failure leaves the Group intact, keeps Device precedence, and returns `cleanup_incomplete` with a Retry option.

### Scheduler enabled / autostart / running model

- Separated persisted `enabled` and `autostart` (independent fields) from a runtime-only `running` state the scheduler thread checks. See [Section 10.5.1](#1051-persisted-enabled--autostart-versus-runtime-running).
- Startup computes `running = enabled AND autostart`; an explicit interactive Save computes `running = enabled`. Persisted `enabled` is never coerced to `false` at startup, so an enabled-but-not-autostart schedule survives a restart as enabled while not running.
- An explicit unchanged Save after a restart starts the runtime schedule even when persistence is a no-op, without forcing a write or a `device_revision` increment. This runtime-apply behavior is schedule-specific and does not change global no-op semantics.
- `GET /api/schedule` now returns `running` alongside `enabled`/`autostart`, and the Scheduled Tests status distinguishes Active, Enabled — Not Running, and Disabled.

### Device Overrides presentation

- Reworked the Settings Device Overrides cards to be left-aligned and responsive with the reset action beside each override title, wrapping cleanly at narrow widths without clipping or horizontal overflow.

### Validation

- Added permanent off-router regression coverage in `test_configuration_manager.py` for the reset dependency cases and wording, the Update NCM Group candidate/preserve/promote/trim/token/GeoView/dependency/button-visibility behavior, and the scheduler `enabled`/`autostart`/`running` combinations, alongside an appdata write/delete audit confirming zero lifetime writes to the Group, experimental, and legacy keys.
- Validated end-to-end on a real E400 across User and Public server modes and Group- and Device-managed states, including the reset dependency modal, the full Update NCM Group wizard (Device key removed after Group validation), and the enabled/autostart/running behavior across fresh application startups.

## v1.1.1

### Cellular Analysis report export architecture

- Added **Export HTML Report** directly beside **Refresh Data** in the Cellular Analysis scope controls.
- Report generation is browser-side. NCOS does not create, retain, or manage report files and does not generate PDF documents.
- The exported artifact is a self-contained HTML document intended for local viewing, sharing, archival use, and browser-based **Print / Save as PDF**.
- PDF print styling targets **US Letter landscape** while still allowing the browser print dialog to control the final output settings.
- Report scope is frozen when export begins so the selected cellular interface, history range, generated timestamp, device label, application version, and theme remain internally consistent throughout report construction.
- Cellular Analysis scope controls and Refresh are temporarily disabled while the report is generated to prevent a live-page refresh or scope change from racing the export.
- The top-level Cellular Analysis API response is deep-copied at export start so overview, timeline, change activity, and report metadata come from one consistent analysis snapshot.
- All identifiable serving cells in the selected analysis scope are loaded sequentially and rendered into the artifact. An individual serving-cell detail failure does not discard the remainder of the report.
- Unknown serving-cell observations remain represented in overview, distribution, and timeline data but do not generate fabricated serving-cell identity detail sections.
- In-test handoff observations are materialized as a static engineering table containing timestamp, test phase, phase offset, and from/to serving-cell information when available.
- Interactive Cellular Analysis controls, configuration UI, JavaScript behavior, live tooltip bindings, and other browser-only controls are removed from the exported artifact.
- Network Mode and Technology Usage donut visualizations are converted from CSS-gradient rendering to embedded SVG for consistent standalone HTML and Chromium PDF output.
- Application CSS and required Font Awesome Solid, Regular, and Brands fonts are embedded directly into the report. The finished artifact does not depend on router-hosted stylesheets or font files.
- A final offline-integrity validation rejects report generation if executable script content, unresolved stylesheet/resource URLs, unresolved CSS resources, duplicate DOM IDs, unconverted report donuts, or interactive Cellular Analysis controls remain.
- Report filenames include the selected interface and generation timestamp so repeated exports do not overwrite or ambiguously reuse the same filename.
- Print-specific rendering uses deterministic light-paper colors and removes gradient/shadow effects that were found to rasterize inconsistently in Chromium PDF output.
- Print pagination allows major analysis sections to flow naturally through available page space while avoiding unnecessary internal card splits. Subsequent serving-cell analysis blocks may begin on clean page boundaries.
- Serving-cell identifiers, PLMN, TAC, PCI, bands, channels, RF measurements, carrier aggregation information, Site Location, and other analysis data already displayed by Cellular Analysis may be included in the artifact.
- Credentials, authentication/session data, API keys, cookies, IMEI, ICCID, router serial numbers, and other hidden security-sensitive values are not intentionally exported.
- PDF creation remains a client/browser responsibility: the recipient opens the standalone HTML and uses the browser's normal **Print → Save as PDF** workflow.

### Site-wide GeoView inventory

- Added **Site Cellular GeoView** above the lower interface/history-scoped Cellular Analysis workspace.
- GeoView is intentionally site-wide and evaluates all retained cellular history across every cellular interface.
- Added `build_site_cell_inventory(history)` to reuse the existing traffic-aware serving-cell model without modifying the public `build_cellular_analysis()` response contract used by the existing regression suite.
- Plain Ethernet/non-cellular history is excluded.
- Identifiable serving cells observed only during an in-test handoff remain represented.
- The same normalized serving-cell identity observed through multiple cellular interfaces is aggregated into one GeoView cell with per-interface test counts.
- Per-test serving-cell/interface counting is deduplicated so two-second telemetry sampling does not inflate the number of tests associated with a cell.
- Matching final cellular data can supplement missing display metadata for the same cell but cannot create a different serving-cell identity.

### Local observation schematic and carrier focus

- Replaced the earlier GeoView placeholder with a lightweight provider-independent local observation schematic.
- The schematic explicitly states that marker positions are **not geographic**.
- Added balanced radial placement for multiple observed cells without adding a mapping library or interactive map runtime.
- Added carrier-specific color accents for T-Mobile, Verizon, AT&T, and a theme-default fallback without embedding carrier logos or marks.
- Added carrier focus controls with all observed carriers selected initially.
- Deselecting a carrier dims its serving-cell markers and disables marker interaction.
- The final selected carrier cannot be deselected.
- Added compact serving-cell popups containing Cell ID, PLMN, TAC, PCI, role/band, carrier, and Observed Via interface/test counts.
- Clicking the already-open serving-cell marker a second time closes its popup while retaining the explicit close control.

### GeoView configuration

- Added the **Configure GeoView** modal.
- The first saved configuration changes the header action to the smaller gear-style **Configure** control.
- Added Site Location choices for Device GPS, Manual Coordinates, and literal Site Address.
- Site Address is descriptive text only and is not automatically geocoded.
- Manual coordinate input is validated for valid latitude/longitude ranges.
- **No Geo Provider** remains the enabled v1.1.1 provider mode.
- Google and Unwired choices are displayed as **Research Pending** and remain disabled until their current APIs/service models are separately researched and validated.

### Local settings persistence

- Added `cellular_geo.py` as the provider-independent GeoView settings layer.
- Added persistent NCOS SDK appdata key `geoview_settings`.
- Moved GeoView configuration out of the replaceable application `tmp/` filesystem so saved Site Location settings can survive SDK package upgrades.
- Advanced the GeoView settings model to schema version 2.
- Device GPS, Manual Coordinates, and Site Address are retained independently.
- Added `active_location_source` so one location method is authoritative without deleting the alternatives.
- GPS lock, satellites, accuracy, and other current-fix state remain transient and are not persisted.
- Appdata is written only after an explicit **Save GeoView** action; application defaults are not automatically seeded into NCOS configuration.
- GeoView appdata writes are immediately read back, normalized, and verified before Save reports success.
- Added in-memory normalization support for the earlier schema-v1 single-location model.
- Missing, corrupt, or invalid appdata falls back to a safe default state.
- GeoView configuration remains independent from the rolling Speedtest Analyzer test-history files.

### GeoView API and GPS

- Added `GET /api/geo_settings`.
- Added `POST /api/geo_settings`.
- Configure GeoView now explicitly reloads persisted settings from `/api/geo_settings` whenever the modal is opened.
- Successful GeoView saves synchronize the frontend's complete schema-v2 settings state before the page is re-rendered.
- Added explicit `GET /api/geo_gps`.
- `/api/cellular_analysis` now attaches site-wide GeoView inventory at the HTTP layer while preserving lower Cellular Analysis interface/history scoping.
- GPS is queried only when the user explicitly presses **Refresh GPS**.
- No continuous GPS polling, GPS worker, or additional per-test GPS collection was introduced.
- GPS query failure is nonfatal and does not affect speed testing or local Cellular Analysis.
- Hardened Device GPS validity so a usable fix requires an active NCOS GPS lock plus valid numeric latitude/longitude.
- Added explicit rejection of the NCOS `0.0, 0.0` no-fix sentinel.
- A no-fix refresh or GPS query failure preserves previously saved valid Device GPS coordinates rather than replacing them with invalid coordinates.
- The frontend distinguishes a current GPS fix from retained saved coordinates and no longer presents an unlocked `0.0, 0.0` response as **GPS Fix Available**.
- Added shared `gps_fix_is_usable()` production validation in `cellular_geo.py` so the HTTP API and regression suite enforce the same GPS validity rule.

### Provider and security boundary

- No external Geo Provider calls are implemented in v1.1.1.
- No provider API keys, credentials, or secrets are stored.
- No automatic address geocoding is performed.
- No provider-derived serving-cell geographic estimates or static provider maps are rendered.
- Local GeoView does not require ICCID, IMEI, APN, router serial number, or similar modem identity values.
- Future provider integration must use an explicit minimum-data outbound allowlist and remain isolated from the local test/analysis path.

### Development validation

- Existing Cellular Analysis regression coverage remained green after the GeoView foundation was added.
- Added dedicated provider-independent GeoView regression coverage for site inventory, multi-interface aggregation, handoff-only cells, Ethernet exclusion, settings defaults, literal Site Address, coordinate validation, and Device GPS fix validity.
- Added real-device-derived GPS regression cases covering unlocked `0.0, 0.0`, unlocked nonzero coordinates, locked `0.0, 0.0`, and a locked valid coordinate pair.
- Final v1.1.1 regression checkpoint after GPS and appdata-persistence hardening: **83 tests passing** — 70 core Cellular Analysis tests plus 13 GeoView/GPS tests.
- Real Chromium validation confirmed schema-v2 modal rehydration, Site Address → Manual Coordinates → Device GPS active-source switching, preservation of inactive saved location methods, and immediate Site Context updates after Save.
- Live E400 validation confirmed `geoview_settings` persists in NCOS SDK appdata across Speedtest Analyzer SDK package replacement and is subsequently reloaded into Configure GeoView with the saved active Site Location restored.
- Complete inline JavaScript parses successfully with the macOS JavaScript engine.
- The current frontend was rendered and exercised in Chromium with a multi-carrier fixture covering carrier focus, disabled markers, serving-cell popups, settings persistence, Device GPS state, and responsive layout.
- Live E400 validation confirmed the no-fix protection requirement when NCOS returned GPS enabled/running with `lock: false` and `0.0, 0.0`.
- Loading a new SDK application build clears the app's retained local test history, so device reloads remain deliberate validation events.

## v1.1.0

### Cellular Analysis

- Added a new **Cellular Analysis** page focused on the question: **What cellular network resources has this device been using?**
- Analysis is scoped by cellular interface and retained-history range. Ethernet and other non-cellular WAN results are excluded from Cellular Analysis.
- Added serving-cell distribution using stable view labels such as A, B, and C while retaining the underlying Cell ID, PLMN, TAC, PCI, band, and channel where available.
- Unknown serving-cell observations remain represented when identity telemetry is unavailable rather than being silently converted into a known cell.
- Updated distribution semantics for traffic-aware history: **Tests Seen** may overlap when one test observes multiple cells, while **Active Traffic** is derived from mutually exclusive timed traffic intervals.
- Added a chronological Serving Cell Timeline using real elapsed test timestamps and midpoint boundaries between sparse scheduled observations.
- Added thin in-test handoff event markers to the long-term timeline. These markers identify a proven traffic-time transition without falsely implying that the temporary cell remained serving until the next scheduled test.
- Added aggregate **Serving Cell Changes**, **Peak Config Changes**, **Bandwidth Changes**, and **Network Mode Changes**.
- Serving Cell Changes distinguish in-test handoffs from between-test serving-cell changes and avoid double-counting when a test ends on the same cell where the next test begins.
- Added selected-serving-cell RF summaries for RSRP, RSRQ, SINR, and retained Cellular Health observations.
- Added **Technology Usage** and **Peak Observed Radio Configurations** as the consolidated radio-resource summary.

### Traffic-aware serving-cell telemetry

- Extended the existing two-second in-test carrier telemetry collector to retain serving-cell identity alongside carrier configuration without introducing a second continuous NCOS polling loop.
- LTE and NSA observations use the LTE PCell / serving anchor Cell ID and PCI.
- 5G Standalone observations prefer NR Cell ID and 5G PCI.
- Traffic-phase serving-cell intervals are retained separately for Download and Upload.
- Added per-test serving-cell summaries containing the traffic start cell, traffic end cell, unique cells observed, ordered handoffs, and total active-traffic time.
- Missing/Unknown identity does not bridge two known observations into an invented serving-cell handoff.
- Download-to-Upload boundary changes are preserved as boundary events because the exact transition second is not known.
- Cells observed only during an in-test handoff remain eligible for Cellular Analysis distribution and selected-cell analysis.
- The final post-test cellular snapshot supplements traffic-time observations rather than replacing them.

### Post-test serving-cell stabilization

- Added a conditional post-test stabilization window that runs only after traffic telemetry proves an identifiable serving-cell handoff.
- The application captures the immediate final cellular state and performs additional modem observations at approximately **+2, +4, and +6 seconds**.
- Post-test observations are stored separately from active-traffic telemetry and do not modify Peak Observed carrier configuration, RF conditions, bandwidth-change calculations, or throughput results.
- Post-test state is classified as **persisted**, **reverted**, **continued handoff**, **unstable**, or **inconclusive**.
- Stable tests incur no additional post-test polling delay.
- History is still written once per completed test after the conditional stabilization workflow finishes.

### Serving-cell-specific RF and radio configuration

- Selected-cell analysis recognizes every identifiable traffic-active serving cell rather than only the final post-test cell.
- Each selected cell uses the strongest matching Peak snapshot for that cell within each test, preferring the greatest usable carrier count and then total observed bandwidth.
- NSA selected-cell primary RF is matched to the LTE serving anchor.
- 5G SA selected-cell primary RF is matched to the NR PCell.
- Legacy single-cell history retains compatible top-level RF and Cellular Health fallback behavior.
- Multi-cell tests keep final Cellular Health associated only with the final identified cell to prevent cross-cell contamination.
- Peak configuration supplementation may fill missing channel/PCI identity only when RAT, band, and bandwidth match unambiguously; it never adds carriers or changes the observed Peak configuration.
- Active carriers reporting `0 MHz` remain excluded from usable Peak configuration totals.

### History & Reports integration

- Redesigned cellular test details into three responsive identity areas: **Connection Health**, **Network**, and **Serving Cell**.
- Network details now present Carrier, Service Detail, Service Type, and APN in a compact fluid layout.
- Serving Cell details now expose Cell ID, PLMN, TAC, and PCI separately from radio-resource information.
- Added explicit Channel columns to the LTE and 5G NR radio summaries.
- NSA 5G NR summary data prefers the active normalized NR SCell while retaining top-level NR compatibility fallbacks.
- 5G SA primary NR summary prefers the normalized NR PCell, while a secondary NR summary uses an available NR SCell.
- Radio generation is determined from the normalized reported band rather than assuming every `_5G_` NCOS diagnostic field represents NR.
- Added transition-only **Serving Cell Activity** presentation with Start, chronological in-test handoffs, End, and compact post-test stabilization status.
- Stable tests do not display an unnecessary Serving Cell Activity section.

### CSV and reporting

- Added normalized primary **Cell ID**, **PLMN**, **TAC**, and **PCI** columns.
- Added LTE Channel and 5G NR Channel fields.
- Added a single combined **Serving Cell Activity** field containing the chronological transition narrative instead of expanding handoff state across many CSV columns.
- Stable tests leave the Serving Cell Activity field blank.
- Serving Cell Activity intentionally omits band, bandwidth, and channel details already represented elsewhere in the report.

### History persistence

- Replaced direct in-place history writes with temporary-file creation, flush/fsync, validation, and atomic promotion.
- Added one last-known-good local history backup and recovery from valid temporary or backup history files.
- Added protection against replacing a valid backup with a corrupt primary history file.
- Added corrupt-primary quarantine behavior.
- Added a history transaction lock around add, delete, clear, and recovery operations.
- Clear History intentionally removes primary, backup, temporary, and quarantined recovery files before creating a new empty history.
- The existing rolling 100-result retention behavior remains unchanged.

### Compatibility and telemetry boundaries

- Peak Observed remains the most complete valid component-carrier configuration observed during active test traffic.
- Secondary-carrier telemetry is treated as active/downlink observation only; the application does not infer unsupported uplink carrier aggregation.
- Cellular Analysis uses retained local test history and does not require a new continuous polling service.

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

---

# 18. Two-Layer Configuration Management (1.1.2)

Speedtest Analyzer `1.1.2` manages normal configuration with two canonical SDK appdata
documents and a section-level merge. This section describes how the two documents combine,
how configuration is read and written, and the reset, Update NCM Group, and migration
behaviors built on top of them.

## 18.1 Canonical documents

There are exactly two canonical configuration keys:

- `speedtest_analyzer_group` — the NCM Group standard. **Read and validated only.** The
  application never writes or deletes this key during normal operation; it normally arrives
  through NCM Group SDK/Application Data delivery.
- `speedtest_analyzer_device` — locally managed Device configuration and Device overrides.
  This is the only canonical key the application itself writes or deletes.

Each document is schema-versioned and **section-sparse** — a section is present only when
its key exists in the document. Both carry **independent** revisions:

    {
      "schema_version": 1,
      "document_type": "device",          // or "group"
      "device_revision": 4,               // or "group_revision"
      "config": {
        "schedule": { ... },              // only sections that are configured
        "iperf3_server_settings": { ... }
      }
    }

The supported sections are `schedule`, `outputs`, `iperf3_server_settings`,
`iperf3_user_servers`, `netperf_servers`, and `geoview`.

Management state is **derived from which keys exist**, never stored in JSON. There is no
`management.origin`, no `management.mode`, and no single `config_revision`.

## 18.2 Effective configuration: DEVICE > GROUP > DEFAULT

The effective configuration held in RAM is a whole-section merge with precedence
`DEVICE > GROUP > DEFAULT`:

- A section comes from the Device document when its **key exists** there.
- Otherwise from the Group document when its **key exists** there.
- Otherwise from the built-in defaults.

Section ownership is decided by **key presence, not truthiness**. A falsey value such as
`[]`, `{}`, `false`, or `""` in a higher layer is authoritative and still overrides the
layer below. The merge is section-atomic; sections are never deep-merged field-by-field.

Derived management states: `unconfigured` (neither key), `device` (Device only),
`group` (Group only), `group_with_device_overrides` (both), plus `upgrade_required`,
`unsupported_schema`, and `error` for migration/schema/corruption handling.

## 18.3 App Data access rules

- **Exact-name matching.** The canonical loader inspects the full appdata entry list and
  accepts an entry only when `entry['name']` matches exactly. This avoids the loose/substring
  matching that would otherwise confuse `speedtest_analyzer`, `speedtest_analyzer_group`, and
  `speedtest_analyzer_device`.
- **Read-back verified writes.** A Device write serializes the document, writes it, re-reads
  it by exact name, and verifies `document_type`, schema, and the expected revision before the
  operation is reported successful. A failed read-back fails closed and does not update
  effective RAM.
- **No defaults on startup.** The app never writes defaults to appdata merely because it
  started; doing so would override NCM Group inheritance.

## 18.4 No-op persistence semantics

An ordinary Device save compares the proposed persistent `device.config` body against the
currently persisted body (normalized). If identical, the save is a **no-op**: zero writes,
no `device_revision` increment, no key create/delete, and no hot reload. Runtime-only values
(for example a fresh device-GPS fix, which is stripped before persistence) therefore never
count as a configuration change. The schedule save path layers an explicit runtime-apply on
top of this (see [Section 10.5.1](#1051-persisted-enabled--autostart-versus-runtime-running)).

## 18.5 Validation before persistence — reset dependency handling

Before any reset persists, the manager builds the **proposed** Device document, recomputes the
**proposed** effective configuration (`DEVICE > GROUP > DEFAULT`), and runs dependency
validation. It persists only if the proposed effective configuration is internally consistent.

The one dependency enforced in `1.1.2` is the iPerf3 scheduled-test coupling: a configured
iPerf3 schedule records `params.server_source` (`public` or `user`), and the effective
`iperf3_server_settings.server_mode` must use the same server family. Netperf and non-iPerf3
schedules have no such coupling and are never affected.

When resetting one section alone would produce an inconsistent effective configuration
(the confirmed E400 defect: reset the Device schedule override while the Device still forces
a different server mode), the reset does **not** persist. The backend returns:

    status = dependency_reset_required
    requested_section = schedule
    required_reset_sections = [schedule, iperf3_server_settings]
    reason = <human-readable dependency>
    reset_target = group | default

The UI presents a themed confirmation. On confirm, the caller re-invokes the reset with the
full `required_reset_sections` set, and the manager removes all coupled overrides in **one
atomic transaction** — one `device_revision` increment (or a single Device-key delete when the
document is emptied), one hot reload, Group untouched. The final effective configuration is
validated again before the write. "Reset All Device Overrides" likewise validates the final
`GROUP + DEFAULT` effective configuration before deleting the Device key.

`reset_target` (`group` when the section also exists in the Group layer, else `default`) is
backend-derived so the success message names the true destination — "reset to the NCM Group
configuration" versus "reset to the Built-in Default" — rather than always claiming Group.

## 18.6 Update NCM Group Configuration

"Update NCM Group Configuration" promotes selected current Device overrides into an
**existing** Group standard. It is offered only in the `group_with_device_overrides` state; it
never reappears as "Migrate to NCM Group" (the pure Device-to-Group first migration).

The candidate is built from a **deep copy of the current** `speedtest_analyzer_group` document.
Only the selected Device sections replace/add into that copy; unselected sections and unrelated
Group sections are left exactly as-is. Built-in defaults are never copied into the Group. The
candidate's `group_revision` is `current + 1`. Nothing is written locally — the administrator
updates the Group value in NCM.

- **Dependency validation runs against the proposed revised Group.** For example, a promoted
  iPerf3 schedule that references a User server requires the revised Group's effective server
  mode to be User with a non-empty user-server list (already present in the Group, or also
  promoted).
- **GeoView safety.** A Device-GPS policy is promotable with runtime coordinates stripped;
  manual-coordinate and site-address GeoView are device-specific and are not promotable.
- **Reconciliation token.** The candidate captures `(group_revision, device_revision)`. If
  either changes during the staged workflow, validate and cleanup abort with a distinct
  `reconcile_aborted` status; the UI discards the staged candidate, refreshes authoritative
  state, and requires restarting the workflow. Stale admin work is never auto-merged.
- **Validate then trim.** After the revised Group is validated present on the device (exact
  key, `document_type=group`, schema, expected `group_revision`), only the promoted sections
  are removed from the Device document. If the Device document is emptied, the Device key is
  deleted. If cleanup fails, the Group is left intact, Device still wins by precedence, and the
  workflow returns `cleanup_incomplete` with a Retry option.

Validation proves the payload is present on the device; it does not claim NCM provenance
(a value could in principle be authored at Device scope). The wording is deliberately
"validated on device," not "NCM Group provenance verified."

## 18.7 Migration inputs and legacy conversion

The abandoned experimental single key `speedtest_analyzer` and the fragmented legacy keys
(`speedtest_schedule`, `iperf_server_settings`, `iperf3_servers`, `netperf_servers`,
`speedtest_outputs`, `geoview_settings`) are **migration inputs only**. When no canonical key
exists but a valid migration source does, the derived state is `upgrade_required` and ordinary
configuration mutation is blocked until the user converts. Conversion reads the source, builds a
schema-1 Device document (`device_revision = 1`), read-back verifies it, and unblocks editing.
Migration sources are never modified or deleted.

## 18.8 Factory Reset and GeoView boundary

Factory Reset removes Speedtest Analyzer-owned local state (the Device key, the experimental
key, legacy keys, runtime/results/stats keys, and local history files) and **never** touches
`speedtest_analyzer_group`. When a Group is present, the Group configuration becomes effective
again after local data is cleared.

GeoView is persisted as the `geoview` section inside the canonical documents. Runtime device-GPS
coordinates are stripped before persistence and before Group promotion, so canonical
configuration never carries one device's live fix.

---

# 19. GeoView Geolocation Services and OpenCellID Contributions (1.1.3)

Release `1.1.3` completes the geographic GeoView feature.

The architectural distinction is fundamental:

- **Site location** is the router/site reference point supplied by Device GPS, Site Address geocoding, or Manual Coordinates.
- **Estimated Serving Cell Location** is the geographic enrichment of the cellular serving identity observed by NCOS.

The feature estimates serving-cell locations. It does not use the cellular network to estimate where the router is located.

## 19.1 Final service responsibilities

| Service | v1.1.3 responsibility |
|---|---|
| OpenCellID `/cell/get` | Estimate the geographic location of an eligible primary serving cell. |
| OpenCellID `/measure/add` | Optional contribution of where an eligible serving cell was observed. |
| Google Geocoding API | Forward-geocode a manually entered Site Address on Save. |
| Google Maps JavaScript API | Render the interactive browser map. |

The final UI exposes **Local Only** and **Geolocation Services**, not a menu of interchangeable cellular-location providers.

## 19.2 Serving identity and OpenCellID lookup

NCOS observation is authoritative.

Provider data enriches the observed identity with coordinates; it does not redefine PLMN, TAC, Cell ID, or RAT.

| Network mode | Identity resolved | OpenCellID radio |
|---|---|---|
| LTE Only | LTE primary MCC/MNC/TAC/ECI | `LTE` |
| 5G NSA | LTE anchor MCC/MNC/TAC/ECI | `LTE` |
| 5G SA | NR primary MCC/MNC/TAC/NCI | `NR` |

The full ECI/NCI is required.

PCI, band, channel, EARFCN, and NR-ARFCN are not unique geographic cell identities and are never substituted.

Secondary/component carriers remain RF/configuration observations unless they independently carry a complete serving identity.

OpenCellID response identity is validated against the requested MCC/MNC/TAC/cell ID.

Provider-returned range/sample/changeable metadata is not interpreted as Site distance or a location-accuracy radius.

## 19.3 Protected credential architecture

`geo_secrets.py` is the only module permitted to access:

    config/certmgmt/certs

or call:

    cp.decrypt()

Two stable app-owned records separate server credentials from the browser key:

    speedtest_analyzer_geo_server
      schema_version: 1
      api_key:          Google Server API key
      opencellid_key:   OpenCellID lookup/contribution key

    speedtest_analyzer_geo_mapjs
      schema_version: 1
      maps_js_api_key:  Google Maps JavaScript browser key

NCOS stores the certmgmt `key` field encrypted at rest.

Security rules:

- Google Server and OpenCellID keys never leave the router through normal API responses.
- Credential-status APIs return metadata/presence only.
- Credential forms are write-only.
- The browser Maps JavaScript key is intentionally separate and returned only through `/api/geo/mapjs`.
- Credentials are never stored in canonical App Data, test history, GeoView cache, contribution ledger, reports, or exports.
- Credentials remain Device-scoped in v1.1.3.

The historical `speedtest_analyzer_geo_google` record is migration input only.

## 19.4 Site Location

GeoView stores three Site Location methods independently:

- Device GPS.
- Manual Coordinates.
- Site Address plus derived coordinates.

Device GPS must have a valid lock and nonzero coordinate pair.

Site Address is forward-geocoded on Save/Apply through Google Geocoding using the private Google Server key.

The resulting Site coordinates are stored with the address.

The configured Site is used as the reference point for:

- Map placement.
- Site-to-cell distance/bearing.
- Static SVG export.
- Contribution position when Manual Site Location is active.

## 19.5 Resolution job and persistent cache

`POST /api/geo/resolve` is the explicit cellular serving-location resolution trigger.

Resolution flow:

1. Build the site-wide retained serving-cell inventory locally.
2. Normalize and validate each primary identity.
3. Check `tmp/geoview_cell_cache.json`.
4. Call OpenCellID `/cell/get` only on an eligible cache miss.
5. Validate and normalize the response.
6. Persist only safe resolved or `not_found` outcomes.
7. Aggregate metadata-only status/counts.

Only one resolution job runs at a time.

Default cache policy:

- Resolved location — 30 days.
- `not_found` — 6 hours.
- Auth/quota/timeout/no-Internet/provider-error — not persisted as reusable locations.

The cache is atomic, schema-guarded, and contains no credentials.

`GET /api/cellular_analysis` and `/api/geo/mapjs` may read cached enrichment but never initiate serving-cell lookup.

## 19.6 Interactive map

The live geographic map is browser-side Google Maps JavaScript.

`GET /api/geo/mapjs` returns only:

- The separate browser-restricted Maps JavaScript key.
- Browser-safe Site and cached/resolved A/B/C marker data.

It does not return the Google Server key, OpenCellID key, or decrypted cert bundle.

Map behavior includes:

- Site and serving-cell markers.
- Carrier-aware colors.
- Site-to-cell relationship lines.
- Reset View.
- Google pan/zoom/fullscreen controls.
- Marker popup toggle.
- Compact role/band, estimated-location, distance/direction, and test-usage presentation.

Site-to-cell distance/bearing is calculated from the configured Site coordinates and OpenCellID estimated serving-cell coordinates.

OpenCellID `range` is not used as that distance and is not treated as positional accuracy.

## 19.7 OpenCellID observation contribution

Contribution is independent from lookup and is Off by default:

    contribution_enabled = false

The submitted position is **where the router observed the serving cell**, not the provider-estimated serving-cell location.

Eligibility:

- Internal or captive cellular WAN only.
- LTE primary, NSA LTE anchor, or SA NR primary identity only.
- Complete identity required.
- No Ethernet, Wi-Fi, Satellite, external/generic modem, or SCell-only submission.

### Device GPS automatic contribution

After a completed eligible cellular test, contribution can run automatically only when:

- Geolocation Services is active.
- Contribution is enabled.
- Device GPS is the active Site Location source.
- NCOS reports a usable current GPS fix.
- The OpenCellID key is configured.
- The test WAN is authoritatively classified as cellular.

The hook is best-effort and never changes the result of the speed test.

### Manual Site Location contribution

With Site Address or Manual Coordinates active, **Contribute Observations** is available when contribution is enabled.

The handler scans retained history, hard-filters eligible Internal/Captive observations, and submits the most recent observation for each unique primary serving identity using the current validated manual Site coordinates.

### Persistent dedupe ledger

The ledger is:

    tmp/geoview_contribution_ledger.json

It stores no credentials.

Rules:

- Same identity less than 20 meters from the last successful position -> skip.
- Same identity 20 meters or more away -> eligible again.
- Different identity -> immediately eligible.
- Ledger update occurs only after OpenCellID acknowledges successful insertion.

## 19.8 Reset Credentials and mode transition

Reset Credentials:

- Clears all three protected keys.
- Sets `contribution_enabled=false`.
- Sets `provider=none`.
- Returns GeoView to Local Only.

It preserves:

- Site Location configuration.
- Speedtest history.
- `tmp/geoview_cell_cache.json`.

Preserving the cache allows a later return to Geolocation Services to reuse valid OpenCellID locations.

## 19.9 Standalone HTML/PDF export

The standalone report never clones the live Google Maps runtime into the artifact.

Export builds a deterministic inline SVG from frozen Site and resolved serving-cell data.

The SVG includes:

- Site marker.
- A/B/C serving-cell markers.
- Carrier colors.
- Relative vectors.
- Distance/direction labels.
- Scale.
- Location Summary.
- Serving Cell Details.

The report CSS collector excludes Google Maps-injected runtime styles referencing external Google assets.

The integrity validator remains strict.

No Google Maps runtime asset, provider credential, or credentialed provider URL is required by the saved HTML or PDF-ready report.

## 19.10 Validation status

Final v1.1.3 validation included:

- Python compile checks for GeoView backend modules.
- Browser JavaScript/runtime validation during iterative deployment.
- E400 live application startup and HTTP validation on NCOS 7.26.60.
- Encrypted certmgmt proof with masked at-rest reads and successful on-router `cp.decrypt()` recovery.
- OpenCellID serving-location lookup.
- Google Maps JavaScript rendering of Site plus multiple resolved serving-cell markers.
- Correct Site-to-cell distance/bearing.
- Local Only / Geolocation Services switching and cache reuse.
- Credential status/update/remove/reset behavior.
- Site Address geocoding and Manual Coordinates.
- Standalone HTML export and browser Save-as-PDF rendering with Google runtime assets excluded.
- OpenCellID manual contribution for one serving cell and later two unique serving cells.
- Confirmed multi-cell contribution result: `2 submitted · 0 duplicates skipped`.
- Contribution Opt Out and Manual Contribution button behavior.

The E400 GPS subsystem was also observed in a legitimate **No Lock** state during validation. That NCOS state is handled safely and does not represent a GeoView code failure.

# 20. iPerf3 TCP RTT, Jitter, and Compact Telemetry (1.1.3)

v1.1.3 extends the existing iPerf3 execution path with additional measurement telemetry without redesigning the validated throughput engine.

The existing TCP behavior remains authoritative for throughput:

- The router is the iPerf3 client.
- Downlink uses iPerf3 reverse mode (`-R`), so the remote server is the TCP payload sender.
- Uplink uses normal client-send mode, so the router is the TCP payload sender.
- Existing listener retry, Public backup-server behavior, shared port budgets, source routing, WAN guards, and cancellation remain unchanged.

The additional telemetry is extracted from the JSON already returned by the bundled iPerf3 binary.

## 20.1 TCP RTT measurement

For Uplink, iPerf3 exposes TCP sender RTT through Linux `TCP_INFO`.

Speedtest Analyzer converts the iPerf3 microsecond values to milliseconds and records:

- `latency_ms` — average TCP RTT.
- `latency_min_ms` — minimum sampled TCP RTT.
- `latency_max_ms` — maximum sampled TCP RTT.

The user interface labels this measurement **TCP RTT** for iPerf3.

This is a loaded TCP RTT measurement. The values are observed while the router is actively transmitting the Uplink throughput test. They are not equivalent to an idle ping or a pre-transfer latency sample.

Loaded TCP RTT can be significantly higher than idle latency because the access network and path are carrying sustained test traffic. Cellular uplinks can show particularly large increases due to radio scheduling, buffering, congestion, RF conditions, and limited upstream capacity. Ethernet or other higher-capacity WANs often show less inflation because the throughput test consumes a smaller fraction of the available path capacity.

History presents:

`TCP RTT: <average> ms avg (<minimum> - <maximum> ms)`

The minimum and maximum values are the minimum and maximum sampled TCP smoothed-RTT observations reported during Uplink. They are not individual packet-latency extrema.

iPerf3 also reports TCP RTT variation (`rttvar`). Speedtest Analyzer can retain that value inside compact engineering telemetry, but **TCP `rttvar` is never presented as Jitter**.

## 20.2 TCP retransmissions

Retransmission ownership follows the TCP sender.

For Uplink:

- The router is the sender.
- `end.sum_sent.retransmits` represents device-side TCP sender retransmissions.
- This value is promoted to the top-level `retransmissions` result field.
- History presents the value as **Retransmissions**.
- CSV exports the value as `TCP_Retransmissions`.

For Downlink:

- `-R` makes the remote iPerf3 server the TCP sender.
- The remote sender retransmission total is retained in `iperf3_tcp.download.retransmissions`.
- It is not substituted for the top-level device-side Uplink retransmission value.

A retransmission count is a TCP event count. It is **not a packet-loss percentage**.

## 20.3 Compact TCP telemetry

The persisted `iperf3_tcp` object retains engineering evidence for future analysis while keeping normal History concise.

The Downlink object can contain:

- `direction`
- `sender_scope=remote`
- total remote sender retransmissions
- stream count
- per-interval start/end time
- per-interval throughput

The Uplink object can contain:

- `direction`
- `sender_scope=device`
- total device sender retransmissions
- stream count
- TCP MSS
- RTT minimum/average/maximum
- maximum congestion window
- maximum send window
- per-interval throughput
- per-interval retransmissions
- per-interval RTT
- per-interval RTT variation
- per-interval congestion window
- per-interval send window

This object is deliberately hidden from normal History detail and CSV export. It is retained as source evidence for future correlation, event detection, KPI development, and engineering analysis.

A zero-throughput interval is retained as an observation when reported by iPerf3. It is not automatically classified as a disconnect or failure; future analysis must correlate it with RTT, retransmissions, congestion-window behavior, WAN state, and cellular observations.

## 20.4 Optional Jitter measurement

The iPerf3 **Jitter** control does not enable TCP RTT. TCP RTT is automatic.

When Jitter is enabled and the normal TCP Downlink and Uplink test completes successfully, Speedtest Analyzer appends one lightweight UDP iPerf3 probe to the same successful server and port.

The probe uses the equivalent of:

`iperf3 -c <server> -p <port> -u -b 1M -t 5 -J -4`

The same selected source IP and bind device are reused when required by the WAN-selection architecture.

The Jitter probe:

- runs once;
- has no listener retry loop;
- does not consume or modify the TCP server retry budget;
- honors Stop/cancellation;
- validates the selected WAN path before the probe;
- validates the selected WAN path again before accepting the result;
- is non-fatal to the already-completed TCP test.

If UDP is unsupported, times out, returns an error, or the selected WAN changes, the TCP result remains successful and `jitter_ms` remains unset.

Only the true iPerf3 UDP `jitter_ms` value is promoted to normal result/history reporting.

UDP packet-loss counters and loss percentages are intentionally not exposed by this feature so they are not confused with TCP retransmission counts.

## 20.5 Manual and Scheduled control semantics

The Manual Test control is engine-aware:

- **iPerf3** — `Jitter`
- **Netperf** — `Latency/Jitter`

The Scheduled Test editor uses the same presentation.

The underlying `include_latency` field is preserved for configuration compatibility:

- iPerf3 `include_latency=true` requests the supplemental Jitter probe.
- Netperf `include_latency=true` retains the existing Netperf Latency/Jitter behavior.

For iPerf3, TCP RTT is collected regardless of the `include_latency` value.

No new configuration key or schema migration is required.

## 20.6 User-interface and reporting behavior

For iPerf3:

- The live result card is labeled **TCP RTT ms**.
- The optional control is labeled **Jitter**.
- Jitter remains `--` when the supplemental measurement is not requested or does not produce a valid result.
- History labels the measurement **TCP RTT** and shows average plus minimum/maximum range.
- History shows the device-side Uplink **Retransmissions** count.
- History shows Jitter when collected.

Netperf retains the existing Latency/Jitter terminology and measurement behavior.

CSV uses:

- `Latency_ms`
- `Jitter_ms`
- `TCP_Retransmissions`

The first two column names are retained for compatibility even though the iPerf3 `Latency_ms` value specifically represents loaded TCP RTT.

## 20.7 Validation

v1.1.3 iPerf3 telemetry validation included:

- Python syntax validation after telemetry integration.
- Confirmation that temporary raw-JSON instrumentation was removed before release.
- Manual iPerf3 TCP-only testing with Jitter disabled.
- Automatic TCP RTT population with Jitter disabled.
- Manual iPerf3 testing with Jitter enabled.
- Successful Jitter collection on Ethernet WAN.
- Successful Jitter collection on cellular WAN.
- History validation of TCP RTT average/minimum/maximum.
- History validation of device-side Uplink retransmissions.
- Validation that the compact `iperf3_tcp` block persisted 10-second Downlink and Uplink interval data.
- Scheduled iPerf3 Jitter configuration persistence.
- Scheduled iPerf3 Jitter execution.
- CSV validation of `Latency_ms`, `Jitter_ms`, and `TCP_Retransmissions`.
- Confirmation that successful TCP results remain successful independently of the supplemental Jitter phase.
