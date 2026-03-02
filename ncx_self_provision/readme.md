# NCX Self-Provisioning SDK Application

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Staging Group Setup](#staging-group-setup)
  - [Configuration Parameters](#configuration-parameters)
  - [Bulk Configuration Template](#bulk-configuration-template)
- [Deployment](#deployment)
- [Self-Provisioning Process](#self-provisioning-process)
- [State Management](#state-management)
- [Error Handling and Recovery](#error-handling-and-recovery)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)
- [File Reference](#file-reference)
- [API Reference](#api-reference)
- [Best Practices](#best-practices)
- [FAQ](#faq)

## Overview (v2.5)

The NCX Self-Provisioning SDK Application enables Ericsson routers to automatically provision themselves to an NCX or SASE network when moved into a staging group. The application executes a 9-step zero-touch provisioning workflow with state management and automatic recovery:

- System readiness validation and firmware sync
- Bulk device configuration from CSV with template-based config
- License application (Secure Connect, SD-WAN, HMF, AI)
- Exchange site creation with DNS configuration and tagging
- Resource provisioning (LAN subnets, FQDN, wildcard domains)
- DNS force redirect configuration (optional)
- Automatic group re-assignment with state cleanup

Configuration is managed via the NCX Staging Wizard, a web-based tool that provides an interactive 6-step interface for setting up all required parameters, API keys, and bulk configuration files before deployment.

## Quick Start

For experienced users, here's the condensed setup process:

1. **Configure staging group** (MUST be done first):
   ```bash
   # Launch the web-based configuration wizard
   python ncx_staging_wizard.py
   # Open browser to http://localhost:8000
   # Complete the 6-step wizard and apply configuration
   ```

2. **Prepare files** (if using bulk config):
   - Create `router_grid.csv` with device data
   - Customize `config_template.json` with `{{column_name}}` placeholders
   - Or use the built-in file editor in the wizard

3. **Build and deploy**:
   ```bash
   python make.py build ncx_self_provision
   # Upload to NCM and assign to staging group
   ```

4. **Provision devices**:
   - Move devices to staging group (limit to batches of 50 devices at a time)
   - Monitor logs for "[Step X/9]" progress
   - Devices auto-move to production when complete

For detailed instructions, see [Installation](#installation) section below.

## Features

### Core Capabilities
- **Automatic Provisioning**: Zero-touch provisioning when devices enter staging group
- **State Management**: Resume capability after failures using persistent state tracking
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Progress Tracking**: Step-by-step progress indicators in logs
- **Validation**: Comprehensive input validation and pre-flight checks
- **Security**: Sanitized logging to prevent credential exposure

### Advanced Features
- **Bulk Configuration**: Apply device-specific configurations from CSV files with {{placeholder}} syntax
- **Template-Based Config**: JSON-based configuration templates with special and placeholder columns
- **Web-Based Wizard**: Interactive 6-step configuration tool with real-time validation
- **File Editor**: Built-in CSV grid view and JSON editor with syntax highlighting
- **VPN Tunnel Monitoring**: Automatic VPN tunnel status checking before DNS configuration
- **Timeout Protection**: Configurable timeouts prevent infinite loops
- **Idempotency**: Safe to re-run; skips completed steps
- **Granular Recovery**: Independent state tracking for each provisioning step

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    NCX Self-Provision App                    │
├─────────────────────────────────────────────────────────────┤
│  1. System Readiness Check                                  │
│  2. API Key Retrieval                                       │
│  3. Firmware Validation                                     │
│  4. Bulk Configuration (Optional)                           │
│  5. License Application                                     │
│  6. Exchange Site Creation                                  │
│  7. Exchange Resource Provisioning                          │
│  8. DNS Force Redirect Configuration (Optional)             │
│  9. Production Group Assignment                             │
└─────────────────────────────────────────────────────────────┘
```

### State Tracking

The application uses persistent state markers to enable recovery:
- `prov_state_readiness`: Firmware validation complete
- `prov_state_bulk_config`: Bulk configuration applied
- `prov_state_license`: Licenses applied
- `prov_state_site`: Exchange site created
- `prov_state_resources`: Exchange resources provisioned
- `prov_state_vpn_tunnel`: VPN tunnel up
- `prov_state_dns_force`: DNS force redirect configured

Additional cached data for recovery:
- `bulk_config_system_id`: System name from CSV (used for site creation)
- `bulk_config_lan_ip`: Primary LAN IP from CSV (used for site/resource creation)
- `exchange_site_id`: Created site ID (used for resource creation)
> **Note:** Per-device CSV tags and `disable_force_dns` are passed in-memory from the bulk config step to downstream steps and are not stored in appdata. This prevents them from being overwritten by asynchronous NCM config pushes.

## Prerequisites

### NCM Requirements
1. **API Access**: Valid NCM API credentials (v2 and v3)
2. **Groups**: 
   - Staging group for initial device placement
   - Production group for provisioned devices
3. **Exchange Network**: Pre-configured NCX/SASE exchange network
4. **Licenses**: Valid Secure Connect license (SD-WAN, HMF, and AI optional)
   - See [Supported License Types](#supported-license-types) for valid license values

### Device Requirements
1. **Firmware**: Compatible firmware version in both staging and production groups
2. **Certificates**: API keys stored as certificates on devices
3. **Connectivity**: WAN connection for API communication
4. **Storage**: Sufficient space for SDK application and configuration files

### File Requirements
- `router_grid.csv`: Device configuration data (if using bulk config)
- `config_template.json`: Configuration template (if using bulk config)

### Supported License Types

The application supports both NCX and SASE platform licenses:

**Secure Connect Licenses:**
- NCX: `NCX-SC`, `NCX-SCL`, `NCX-SCM`, `NCX-SCIOT`, `NCX-SCS`, `NCX-SC-TEMP`
- SASE: `NCS-SC`, `NCS-SC-TRIAL`

**SD-WAN Licenses (Optional):**
- NCX: `NCX-SDWAN`, `NCX-SDWANL`, `NCX-SDWANM`, `NCX-SDWANMICRO`, `NCX-SDWANS`, `NCX-SDWAN-TRIAL`
- SASE: `NCS-SDWAN`, `NCS-SDWAN-TRIAL`

**HMF Licenses (Optional):**
- NCX: `NCX-HMF`, `NCX-HMF-L`, `NCX-HMF-M`, `NCX-HMF-MS`, `NCX-HMF-SS`, `NCX-HMF-TRIAL`
- SASE: `NCS-HMF`, `NCS-HMF-TRIAL`

**AI Licenses (Optional):**
- NCX: `NCX-AI`, `NCX-AI-TRIAL`
- SASE: `NCS-AI`, `NCS-AI-TRIAL`

License types are validated during staging group configuration to ensure correct license assignment.

## Installation

### Overview

The installation process consists of three main steps:
1. **Configure the staging group** using the NCX Staging Wizard (web-based interface)
2. **Build the SDK package** with all required files
3. **Deploy to NCM** and assign to the staging group

**IMPORTANT**: You must run the NCX Staging Wizard BEFORE building and deploying the SDK package. This wizard configures the staging group with all required parameters that the self-provisioning application needs to function.

### Step 1: Configure Staging Group (REQUIRED FIRST)

The NCX Staging Wizard is a web-based configuration tool that must be run before deployment to configure the staging group with all required application data and API keys.

1. **Launch the NCX Staging Wizard**:

```bash
python ncx_staging_wizard.py
```

You should see output similar to:

```
Starting NCX Staging Wizard on http://localhost:8000
Press Ctrl+C to stop the server
```

2. **Open your web browser** and navigate to:

```
http://localhost:8000
```

3. **Complete the 6-step wizard**:

   **Step 1: API Keys**
   - Enter your NCM API v2 credentials (X-CP-API-ID, X-CP-API-KEY, X-ECM-API-ID, X-ECM-API-KEY)
   - Enter your NCM API v3 Bearer Token
   - Click "Validate API Keys" to test connectivity

   **Step 2: Required Parameters**
   - Enter Staging Group ID and Production Group ID
   - Enter Exchange Network ID
   - Select Secure Connect License type
   - Configure DNS options:
     - Enable "LAN as DNS" if needed and enter Local Domain, OR
     - Enable "Custom DNS Servers" and provide Primary DNS (required) and Secondary DNS (optional)
     - Note: LAN as DNS and Custom DNS Servers are mutually exclusive

   **Step 3: Optional Parameters**
   - Select optional licenses (SD-WAN, HMF, AI)
   - Enable resource creation options:
     - Create Primary LAN Resource
     - Create CP Host FQDN Resource *(requires LAN as DNS or Custom DNS Servers to be enabled)*
     - Create Wildcard FQDN Resource *(requires LAN as DNS or Custom DNS Servers to be enabled)*
   - Note: CP host and wildcard FQDN checkboxes are disabled in the wizard unless a DNS option is configured in Step 2
   - Configure global Force DNS setting (can be overridden per-device in CSV)

   **Step 4: Global Tags**
   - Enter global tags for sites (comma or semicolon-separated)
   - Enter global tags for resources (if resource creation enabled)
   - Tags must be at least 2 characters, lowercase letters and numbers only

   **Step 5: Bulk Configuration**
   - Enable bulk configuration if needed
   - Upload or edit `router_grid.csv` and `config_template.json` files
   - Use the built-in file editor with grid view for CSV editing
   - Validate files to check column/placeholder matching

   **Step 6: Review & Apply**
   - Review your complete configuration summary
   - Click "Validate Configuration" to check all settings
   - Click "Apply Configuration" to push settings to staging group

4. **Verify configuration was applied**:

You should see a success message:

```
Configuration Applied Successfully!
The staging group has been configured with all parameters and API keys.

Next Steps:
1. Build the SDK package: python make.py build ncx_self_provision
2. Upload to NCM and assign to your staging group
3. Move devices to staging group (maximum 50 at a time)
4. Monitor device logs for provisioning progress
```

**What the wizard does:**
- Validates all required configuration parameters
- Validates API key connectivity with real-time testing
- Validates tag format (min 2 chars, lowercase alphanumeric) and FQDN compliance
- Validates IP addresses (no netmask notation allowed)
- Validates bulk configuration files (CSV/JSON matching)
- Validates license types with automatic NCX/SASE prefix matching
- Sets API keys as certificates in the staging group
- Configures 22 application data parameters needed by the self-provisioning app
- Provides interactive file editing with CSV grid view and JSON syntax highlighting
- Color-coded CSV column analysis (green=config, blue=NCM/NCX, red=missing)
- Displays comprehensive configuration summary before applying
- Collapsible warning messages for bulk configuration issues

**Troubleshooting:**
- If you see validation errors, check that all required fields are filled correctly
- If API key validation fails, verify your credentials are correct
- Ensure you have permissions to modify the staging group in NCM
- Check that your browser allows connections to localhost:8000
- If port 8000 is in use, the wizard will try alternative ports

### Step 2: Prepare Configuration Files (Optional)

If using bulk configuration, you can prepare files before running the wizard or use the built-in file editor:

**Option A: Prepare files manually**

1. **Create router_grid.csv** with your device data:

```csv
id,name,asset_id,desc,primary_lan_ip,2ghz_ssid,5ghz_ssid,custom1,custom2,disable_force_dns
12345,Router-Site-A,ASSET-001,Branch Office A,192.168.1.1,WiFi-2G,WiFi-5G,Location-A,Region-West,false
12346,Router-Site-B,ASSET-002,Branch Office B,192.168.2.1,WiFi-2G,WiFi-5G,Location-B,Region-East,true
```

2. **Customize config_template.json** with `{{column_name}}` placeholders

**Option B: Use the wizard's built-in file editor**

- The wizard includes a file editor in Step 5 (Bulk Configuration)
- Edit CSV files in grid view or text view
- Edit JSON templates with syntax highlighting
- Validate files to check column/placeholder matching
- Save files directly from the browser

### Step 3: Build and Deploy

1. **Build the SDK package**:

```bash
python make.py build ncx_self_provision
```

This creates a package containing:
- ncx_self_provision.py (main application)
- cp.py (router library)
- ncm.py (NCM API library)
- config_template.json (if using bulk config)
- router_grid.csv (if using bulk config)
- Other required files

2. **Upload to NCM**:
- Log into NCM
- Navigate to Tools → SDK
- Upload the built package
- Assign the app to your staging group

3. **Verify deployment**:
- Check that the app appears in the staging group's SDK Apps

### Step 4: Begin Provisioning

1. **Move devices to staging group**:
- Devices can be moved manually via NCM UI
- Or use NCM API for bulk operations

2. **Monitor provisioning**:
- Check device logs in NCM for progress
- Look for "[Step X/9]" progress indicators
- Successful completion shows: "NCX Self Provisioning Complete - All steps successful"

3. **Verify results**:
- Devices should automatically move to production group
- Check that licenses were applied
- Verify exchange sites were created
- Confirm resources were provisioned

## Configuration

### Staging Group Setup

The staging group must have the following application data configured:

#### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `staging_group_id` | ID of staging group | `'123456'` |
| `prod_group_id` | ID of production group | `'654321'` |
| `exchange_network_id` | NCX/SASE network ID | `'ABCD1234'` |
| `secure_connect_lic` | Secure Connect license type | `'NCX-SCIOT'` |
| `lan_as_dns` | Enable LAN as DNS | `True` or `False` |

#### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `local_domain` | Domain suffix for sites | `'ncx.net'` (required if `lan_as_dns` is `True`; for FQDN resources falls back to `cp.get('config/system/local_domain')` if not set) |
| `primary_dns` | Primary DNS server IP | `''` (empty, or IP address if custom DNS enabled) |
| `secondary_dns` | Secondary DNS server IP | `''` (empty, or IP address if custom DNS enabled) |
| `sdwan_lic` | SD-WAN license type | `None` |
| `hmf_lic` | HMF license type | `None` |
| `ai_lic` | AI license type | `None` |
| `create_lan_resource` | Create LAN subnet resource | `'True'` |
| `create_cp_host_resource` | Create FQDN resource | `'True'` |
| `create_wildcard_resource` | Create wildcard resource | `'True'` |
| `self_bulk_config` | Enable bulk configuration | `'False'` |
| `bulk_config_file` | CSV filename | `'router_grid.csv'` |
| `config_template_file` | Template filename | `'config_template.json'` |
| `site_tags` | Global tags for all sites | `''` (empty string, comma or semicolon-separated) |
| `lan_resource_tags` | Global tags for LAN resources | `''` (empty string, comma or semicolon-separated) |
| `cp_host_tags` | Global tags for CP host resources | `''` (empty string, comma or semicolon-separated) |
| `wildcard_tags` | Global tags for wildcard resources | `''` (empty string, comma or semicolon-separated) |
| `disable_force_dns` | Disable DNS force redirect globally | `'False'` (can be overridden per-device in CSV) |

### Configuration Parameters

#### Timeout and Retry Settings

Modify constants in `ncx_self_provision.py`:

```python
UPTIME_WAIT_SECONDS = 120          # Wait for router uptime
FIRMWARE_CHECK_INTERVAL = 15       # Firmware sync check interval
FIRMWARE_CHECK_TIMEOUT = 3600      # Max wait for firmware sync
STEP_DELAY_SECONDS = 5             # Delay between major steps
COMPLETION_WAIT_SECONDS = 600      # Wait after completion
LICENSE_APPLY_DELAY = 1            # Delay between license applications
MAX_RETRIES = 3                    # API call retry attempts
RETRY_DELAY = 5                    # Initial retry delay (exponential backoff)
```

### Bulk Configuration Template

The `config_template.json` file defines the device configuration structure using placeholder syntax. Values are dynamically populated from CSV columns using `{{column_name}}` placeholders.

#### Placeholder Syntax

The template uses `{{column_name}}` placeholders that are automatically replaced with values from the CSV file:

- `{{name}}` - Replaced with value from 'name' column (e.g., 'site-3')
- `{{asset_id}}` - Replaced with value from 'asset_id' column (e.g., '12345')
- `{{primary_lan_ip}}` - Replaced with value from 'primary_lan_ip' column (e.g., '192.168.103.1')
- Any non-special CSV column can be referenced using this syntax

**Important**: Special columns (`id`, `name`, `primary_lan_ip`, `desc`, `custom1`, `custom2`, tag columns, `disable_force_dns`) are handled by application logic and should NOT be used as `{{placeholders}}` in the template. See [CSV Column Mapping](#csv-column-mapping) for the complete list of special columns.

#### Template Structure Example

```json
[
  {
    "lan": {
      "00000000-0d93-319d-8220-4a1fb0372b51": {
        "ip_address": "{{primary_lan_ip}}",
        "dhcpd": { ... }
      }
    },
    "system": {
      "system_id": "{{name}}",
      "asset_id": "{{asset_id}}"
    }
  },
  []
]
```

#### Creating Custom Templates

1. **Export Configuration from NCM**:
   - Go to device Edit Config screen
   - Make your desired changes
   - View the pending config JSON
   - Copy the JSON structure

2. **Add Placeholders**:
   - Replace static values with `{{column_name}}` placeholders
   - Use CSV column names that match your router_grid.csv
   - Leave non-variable values as-is

3. **Example Custom Template**:
```json
[
  {
    "system": {
      "system_id": "{{name}}",
      "asset_id": "{{asset_id}}"
    },
    "lan": {
      "00000000-0d93-319d-8220-4a1fb0372b51": {
        "ip_address": "{{primary_lan_ip}}"
      }
    }
  },
  []
]
```

4. **Corresponding CSV**:
```csv
id,name,asset_id,primary_lan_ip,custom1,custom2
5088306,site-3,12345,192.168.103.1,value 1,value 2
```

#### CSV Column Mapping

**Special Columns** (handled by application logic, not template placeholders):

| CSV Column | Required | Usage | Description |
|------------|----------|-------|-------------|
| `id` | **YES** | Router matching | Router ID - MUST match device's NCM router ID to find the correct row. Without this column, bulk configuration will fail. |
| `name` | No | Site creation | System name - cached during bulk config (Step 4) and used for exchange site creation (Step 6). If missing or router not in CSV, falls back to device's current system_id from running config. |
| `primary_lan_ip` | No | Site/resource creation | Primary LAN IP - cached during bulk config (Step 4) and used for site DNS configuration (Step 6) and LAN resource creation (Step 7). If missing or router not in CSV, falls back to device's current LAN IP from running config. |
| `desc` | No | Device configuration | Description - injected into device configuration via NCM API during bulk config (Step 4). Not used in template. |
| `custom1` | No | NCM custom field | Custom field 1 - set via NCM API during bulk config (Step 4), not in template. Visible in NCM device list. |
| `custom2` | No | NCM custom field | Custom field 2 - set via NCM API during bulk config (Step 4), not in template. Visible in NCM device list. |
| `site_tags` | No | Site tagging | Semicolon-separated tags for exchange site (e.g., `branch;west;retail`). Merged with global site tags from wizard, duplicates removed. Applied during site creation (Step 6). |
| `lan_resource_tags` | No | Resource tagging | Semicolon-separated tags for LAN subnet resource. Merged with global LAN resource tags from wizard. Applied during resource creation (Step 7). |
| `cp_host_tags` | No | Resource tagging | Semicolon-separated tags for CP host FQDN resource. Merged with global CP host tags from wizard. Applied during resource creation (Step 7). |
| `wildcard_resource_tags` | No | Resource tagging | Semicolon-separated tags for wildcard FQDN resource. Merged with global wildcard tags from wizard. Applied during resource creation (Step 7). |
| `disable_force_dns` | No | DNS configuration | Set to 'true' (case-insensitive) to disable DNS force redirect for this specific device. Overrides global Force DNS setting from wizard. Applied during DNS configuration (Step 8). |

**Template Placeholder Columns** (any other column):

| CSV Column | Usage | Description |
|------------|-------|-------------|
| Any other column | Template placeholder | Use as `{{column_name}}` in config_template.json. Values are replaced during bulk config (Step 4). |

**Important Notes:**
- **`id` is the ONLY required column** - without it, the application cannot match routers to CSV rows
- Special columns are processed by application logic and should NOT be used as `{{placeholders}}` in templates
- The `name` and `primary_lan_ip` columns are cached during bulk config (Step 4) and reused for site creation (Step 6) and resource creation (Step 7)
- If `name` or `primary_lan_ip` are missing, or if the router is not found in CSV, the application falls back to reading values from the device's running configuration
- All other columns can be referenced as `{{column_name}}` placeholders in your template
- Tag columns use semicolon delimiters to avoid conflicts with CSV comma separators
- Tags are automatically merged with global tags from wizard and deduplicated

#### Common Template Patterns

**Pattern 1: Simple Value Replacement**
```json
"ip_address": "{{primary_lan_ip}}"
```

**Pattern 2: System Configuration**
```json
"system": {
  "system_id": "{{name}}",
  "asset_id": "{{asset_id}}"
}
```

**Pattern 3: Nested Structures**
```json
"lan": {
  "00000000-0d93-319d-8220-4a1fb0372b51": {
    "ip_address": "{{primary_lan_ip}}",
    "dhcpd": { ... }
  }
}
```

#### Example CSV

```csv
id,name,desc,asset_id,custom1,custom2,primary_lan_ip,site_tags,lan_resource_tags,cp_host_tags,wildcard_resource_tags
5088306,site-3,NYC,12345,value 1,value 2,192.168.103.1,branch;retail,lan;network,,
```

**Column Breakdown:**
- **Special columns** (processed by app logic): `id`, `name`, `desc`, `asset_id`, `custom1`, `custom2`, `primary_lan_ip`, `site_tags`, `lan_resource_tags`, `cp_host_tags`, `wildcard_resource_tags`
- **Template placeholder columns** (used in config_template.json): None in this example (all columns are special)
- **Note**: The `disable_force_dns` column is not shown but can be added as needed

**Tag Columns (Optional)**:
- `site_tags`: Semicolon-separated tags for the exchange site (e.g., `branch;west;retail`)
- `lan_resource_tags`: Semicolon-separated tags for LAN subnet resource
- `cp_host_tags`: Semicolon-separated tags for CP host FQDN resource
- `wildcard_resource_tags`: Semicolon-separated tags for wildcard FQDN resource

**DNS Configuration (Optional)**:
- `disable_force_dns`: Set to 'true' (case-insensitive) to override global Force DNS setting for this specific device

**Force DNS Priority**:
1. Per-device CSV setting (if present) - overrides global
2. Global wizard setting (if no CSV setting)
3. No change (if neither setting is true)

**Tag Merging**:
- Global tags from wizard are merged with per-device tags from CSV
- Duplicates are automatically removed
- Example: Global `production,east` + CSV `branch;east` = Final `['branch', 'east', 'production']`

## Deployment

### Standard Deployment

1. Devices are placed in staging group
2. Application auto-installs and starts
3. Provisioning runs automatically
4. Devices move to production group when complete

### Deployment Workflow

```
┌──────────────┐
│ Device Added │
│  to Staging  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ App Installs │
│  and Starts  │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌─────────────┐
│  Validation  │────▶│   Failure   │
│   & Checks   │     │  (Retry)    │
└──────┬───────┘     └─────────────┘
       │
       ▼
┌──────────────┐
│    Bulk      │
│    Config    │
│  (Optional)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   License    │
│ Application  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Site &    │
│   Resource   │
│   Creation   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Disable DNS  │
│Force Redirect│
│  (Optional)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Move to     │
│  Production  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Complete   │
└──────────────┘
```

## Self-Provisioning Process

### Detailed Step Breakdown

#### Step 1: System Readiness (120s)
- Wait for minimum uptime
- Verify WAN connectivity
- Ensure system stability

#### Step 2: API Key Retrieval
- Extract API keys from device certificates
- Decrypt credentials
- Initialize NCM clients

#### Step 3: Readiness Validation
- Verify device in staging group
- Wait for firmware sync (actual == target)
- Confirm firmware compatibility with both groups
- Timeout: 3600s (configurable)

#### Step 4: Bulk Configuration (Optional)
- Load configuration template from JSON
- Search CSV for router ID
- Apply device-specific values
- Set custom fields
- Cache system_id for site creation
- Skip if disabled or router not found

#### Step 5: License Application
- Apply Secure Connect license (required)
- Apply SD-WAN license (if configured)
- Apply HMF license (if configured)
- Apply AI license (if configured)
- 1s delay between license applications

#### Step 6: Exchange Site Creation
- Create site with router hostname (from bulk config if available)
- Apply site tags as list (if configured)
- Configure LAN as DNS (if enabled) OR custom DNS servers (if provided)
- Set local domain (if LAN as DNS)
- Configure primary and secondary DNS (if custom DNS enabled)
- Cache site_id for resource creation

#### Step 7: Exchange Resource Provisioning
- Create LAN subnet resource (if enabled)
- Create FQDN resource for router (if enabled)
- Create wildcard FQDN resource (if enabled)
- Apply resource tags as list to all resources (if configured)
- Uses cached site_id and system_id

#### Step 8: DNS Force Redirect Configuration (Optional)
- Check global `disable_force_dns` setting from wizard
- Check per-device `disable_force_dns` from CSV (takes precedence)
- Wait for VPN tunnel to come up before applying configuration
- If either is 'true', disable DNS force redirect: `cp.put('config/dns', {"force_redir": False})`
- Per-device CSV setting overrides global wizard setting
- Skip if neither setting is true
- Clean up CSV appdata entry after processing

#### Step 9: Production Group Assignment
- Clean up all provisioning state and cached data
- Move router to production group
- Provisioning complete

### Execution Time

Typical execution time: **5-15 minutes**

Factors affecting duration:
- Firmware sync time (0-30 minutes if update needed)
- Network latency
- API response times
- Number of resources created

### Important Notes

**System Name Handling:**
- If bulk configuration is enabled and the router is found in CSV, the `name` column value is cached and used for site creation
- This ensures the exchange site is created with the updated system name, not the original device name
- The cached system_id is also used for resource naming

**Tag Format:**
- Global tags (wizard): Comma or semicolon-separated strings (e.g., 'tag1,tag2,tag3' or 'tag1;tag2;tag3')
- CSV tags: Semicolon-separated strings (e.g., 'tag1;tag2;tag3')
- Tags are automatically merged and deduplicated
- Tags must be at least 2 characters long and contain only lowercase letters and numbers
- Empty tag strings are handled gracefully (no tags applied)

**DNS Force Redirect:**
- Global setting configured in wizard (Optional Parameters step)
- Per-device control via `disable_force_dns` column in CSV
- Per-device CSV setting overrides global wizard setting
- Set to 'true' (case-insensitive) to disable force DNS
- Applied after resource creation, before moving to production group

## State Management

### How State Tracking Works

The application uses `cp.post_appdata()` to store state markers:

```python
# Set state when step completes
set_state(STATE_LICENSE, 'complete')

# Check state before executing
if get_state(STATE_LICENSE) == 'complete':
    cp.log("License application already complete, skipping")
    return
```

### State Values

- `complete`: Step successfully finished
- `skipped`: Step intentionally skipped
- `not_found`: Resource not found (e.g., router not in CSV)
- `None`: Step not yet attempted

### Recovery Scenarios

#### Scenario 1: Application Restart
If the application restarts (device reboot, app update), it will:
1. Check each state marker
2. Skip completed steps
3. Resume from last incomplete step

#### Scenario 2: Failure Mid-Process
If a step fails:
1. Error is logged
2. State is preserved
3. Cached data (system_id, site_id) is preserved
4. Application can be restarted to retry
5. Completed steps are skipped
6. Cached data is reused for dependent steps

#### Scenario 3: Manual Intervention
To reset provisioning:
```python
# Clear all state markers
cleanup_state()
```

Or manually delete appdata entries in NCM:
- `prov_state_*` entries (state markers)
- `bulk_config_system_id` (cached system name)
- `exchange_site_id` (cached site ID)

## Error Handling and Recovery

### Retry Logic

All API calls use automatic retry with exponential backoff:

```python
Attempt 1: Immediate
Attempt 2: Wait 5s
Attempt 3: Wait 10s
Failure: Raise exception
```

### Timeout Protection

Long-running operations have configurable timeouts:
- Firmware sync: 3600s (1 hour)
- WAN connection: 300s (5 minutes)
- API calls: Per NCM client configuration

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Required appdata 'X' is missing` | Configuration not set | Run NCX Staging Wizard |
| `Firmware sync timeout` | Firmware update taking too long | Increase FIRMWARE_CHECK_TIMEOUT |
| `CSV file not found` | Missing bulk config file | Upload CSV or disable bulk config |
| `Router not found in CSV` | Router ID not in CSV | Add router to CSV or provision without bulk config |
| `API key retrieval failed` | Certificates not configured | Store API keys as certificates |
| `Readiness validation failed` | Router not in staging group | Move router to staging group |

### Recovery Procedures

#### Full Reset
```bash
# On device, delete state markers via NCM or SDK
cp.delete_appdata('prov_state_readiness')
cp.delete_appdata('prov_state_bulk_config')
cp.delete_appdata('prov_state_license')
cp.delete_appdata('prov_state_site')
cp.delete_appdata('prov_state_resources')
cp.delete_appdata('prov_state_group_move')
```

#### Partial Reset (Resume from Specific Step)
Delete only the state markers for steps you want to re-run.

## Security

### Credential Protection

1. **API Keys**: Stored encrypted as device certificates
2. **Log Sanitization**: Sensitive data redacted from logs
3. **Secure Transport**: All API calls use HTTPS
4. **No Hardcoded Secrets**: Credentials retrieved at runtime
5. **Staging Script Security**: ncx_staging.py contains API credentials and must NEVER be included in SDK package or deployed to devices

### Sanitized Logging

The application automatically sanitizes logs:

```python
# Input: "API Key: abc123xyz"
# Output: "API Key: [REDACTED]"
```

Sensitive keywords: `api_key`, `api-key`, `token`, `bearer`, `password`

### Best Practices

1. **Rotate API Keys**: Regularly update API credentials
2. **Limit Permissions**: Use least-privilege API keys
3. **Monitor Logs**: Review logs for security events
4. **Secure CSV Files**: Protect bulk configuration files
5. **Network Isolation**: Use secure networks for provisioning

## Troubleshooting

### Enable Debug Logging

Modify log statements to include more detail:

```python
cp.log(f"DEBUG: Variable value = {value}")
```

### Check State Markers

View current provisioning state in NCM:
- Navigate to device → Configuration → SDK → App Data
- Look for `prov_state_*` entries

### Common Issues

#### Issue: Application Not Starting
**Symptoms**: No logs, no activity
**Checks**:
- Verify app assigned to staging group
- Check device is in staging group
- Confirm app installed successfully
- Review device system logs

#### Issue: Stuck on Firmware Validation
**Symptoms**: Repeating "Waiting for firmware sync" messages
**Checks**:
- Verify target firmware is available
- Check firmware download progress
- Confirm firmware compatibility
- Consider increasing timeout

#### Issue: Bulk Config Not Applied
**Symptoms**: "Router not found in CSV"
**Checks**:
- Verify CSV file uploaded with app
- Confirm router ID in CSV matches device
- Check CSV format (UTF-8, proper columns)
- Validate config_template.json exists

#### Issue: License Application Fails
**Symptoms**: "ERROR applying licenses"
**Checks**:
- Verify license type is valid
- Confirm license available in account
- Check device MAC address is correct
- Review NCM license inventory

#### Issue: Site Creation Fails
**Symptoms**: "ERROR creating exchange site"
**Checks**:
- Verify exchange network ID is correct
- Confirm network exists and is accessible
- Check for duplicate site names
- Review NCM exchange network settings

### Log Analysis

#### Successful Provisioning Log Pattern
```
[Step 1/9] Waiting for system readiness
[Step 2/9] Building API keys
API keys retrieved successfully
[Step 3/9] Validating readiness
Router actual firmware matches target firmware
Device firmware ID matches both staging and production group firmware IDs
[Step 4/9] Applying bulk configuration
Found router 12345 in router_grid.csv
Successfully patched config to router: 12345
Stored system_id for site creation: Router-Site-A
[Step 5/9] Applying licenses
Applying Secure Connect license NCX-SCIOT to XX:XX:XX:XX:XX:XX
[Step 6/9] Creating exchange site
Creating exchange site Router-Site-A on exchange network...
Site tags: ['tag1', 'tag2']
Exchange site created successfully: 01ABCDEF123456789
[Step 7/9] Creating exchange resources
Resource tags: ['tag1', 'tag2']
Creating LAN resource for 192.168.1.0/24
[Step 8/9] Configuring DNS force redirect
Disabling DNS force redirect as specified in CSV
DNS force redirect disabled successfully
[Step 9/9] Moving to production group
Cleaning up provisioning state and cached data
Moving to production group 654321
NCX Self Provisioning Complete - All steps successful
```

#### Failed Provisioning Log Pattern
```
[Step 1/9] Waiting for system readiness
[Step 2/9] Building API keys
API keys retrieved successfully
[Step 3/9] Validating readiness
ERROR: Router group ID (999999) does not match staging group ID (123456)
ERROR: Readiness validation failed
FATAL ERROR in main: Readiness validation failed
Provisioning state preserved for recovery
```

## Advanced Features

### Custom Configuration Templates

Create custom templates for different device types:

1. Create `config_template_branch.json` for branch routers
2. Create `config_template_datacenter.json` for datacenter routers
3. Set `config_template_file` appdata per device or group

### Conditional Provisioning

Modify the script to add conditional logic:

```python
# Example: Skip license for certain device types
product_name = cp.get('status/product_info/product_name')
if 'IBR200' not in product_name:
    apply_license(n3)
```

### Integration with External Systems

Add webhooks or API calls to notify external systems:

```python
# Example: Notify ticketing system
def notify_completion(router_id):
    # Send HTTP request to external system
    pass

# Call after provisioning
notify_completion(router_id)
```

### Batch Provisioning

For large deployments:
1. Prepare CSV with all devices
2. Move devices to staging group in batches of **50 or fewer**
3. Monitor progress via NCM logs
4. Devices auto-move to production when complete
5. Wait for batch to complete before moving next batch

**Important**: Limit batch size to 50 devices at a time to avoid performance issues. Moving too many devices simultaneously may impact NCM performance and provisioning reliability.

## File Reference

### Core Files

| File | Purpose | Required |
|------|---------|----------|
| `ncx_self_provision.py` | Main application | Yes |
| `ncx_staging_wizard.py` | Web-based staging configuration tool | No (local use only) |
| `index.html` | Wizard web interface | No (local use only) |
| `static/` | Wizard CSS/JS/assets | No (local use only) |
| `cp.py` | Router interaction library | Yes |
| `ncm.py` | NCM API client library | Yes |
| `start.sh` | Application startup script | Yes |
| `package.ini` | Application metadata | Yes |

### Configuration Files

| File | Purpose | Required |
|------|---------|----------|
| `config_template.json` | Device config template | If bulk config enabled |
| `router_grid.csv` | Device-specific data | If bulk config enabled |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | This documentation |

## API Reference

### cp Library Functions Used

```python
cp.get_name() -> str
cp.get_firmware_version() -> str
cp.get(path: str) -> Any
cp.log(message: str) -> None
cp.wait_for_uptime(seconds: int) -> None
cp.wait_for_wan_connection(timeout: int) -> bool
cp.get_appdata(name: str) -> Optional[str]
cp.put_appdata(name: str, value: str) -> None
cp.post_appdata(name: str, value: str) -> None
cp.delete_appdata(name: str) -> None
cp.get_ncm_api_keys() -> Dict[str, str]
```

### ncm Library Functions Used

```python
# NCM v2 Client
n2.get_group_by_id(group_id: str) -> Dict
n2.get_router_by_name(router_name: str) -> Dict
n2.get_firmware_for_product_id_by_version(product_id: str, firmware_name: str) -> Dict
n2.patch_configuration_managers(router_id: int, config_man_json: Dict) -> None
n2.set_custom1(router_id: int, text: str) -> None
n2.set_custom2(router_id: int, text: str) -> None
n2.assign_router_to_group(router_id: str, group_id: str) -> None

# NCM v3 Client
n3.regrade(mac: str, subscription_id: str) -> None
n3.create_exchange_site(...) -> Dict
n3.create_exchange_resource(...) -> None
```

## Best Practices

### Development
1. **Test in Lab**: Always test in non-production environment first
2. **Version Control**: Track changes to scripts and templates
3. **Backup Configs**: Keep backups of working configurations
4. **Document Changes**: Maintain changelog for modifications

### Deployment
1. **Staged Rollout**: Deploy to small batch first (max 50 devices)
2. **Monitor Closely**: Watch logs during initial deployments
3. **Have Rollback Plan**: Know how to revert changes
4. **Validate Results**: Confirm devices provisioned correctly
5. **Batch Processing**: For large deployments, process in batches of 50 devices

### Operations
1. **Regular Reviews**: Periodically review logs and success rates
2. **Update Templates**: Keep configuration templates current
3. **Maintain CSV**: Keep router_grid.csv up to date
4. **Monitor Performance**: Track provisioning times and failures

### Security
1. **Rotate Credentials**: Update API keys regularly
2. **Audit Access**: Review who has access to staging group
3. **Secure Files**: Protect CSV files with sensitive data
4. **Review Logs**: Check for security-related errors

## FAQ

### Q: Can I provision devices without bulk configuration?
**A:** Yes, disable bulk configuration in the wizard (Step 5) or set the checkbox to unchecked.

### Q: What happens if a device reboots during provisioning?
**A:** The application will resume from the last completed step using state markers.

### Q: Can I customize the configuration template?
**A:** Yes, edit `config_template.json` to match your requirements. Use `{{column_name}}` placeholders that correspond to your CSV columns.

### Q: How do placeholders work in the template?
**A:** Any value in the template can use `{{column_name}}` syntax. The application will automatically replace these with values from the corresponding CSV column. For example, `{{primary_lan_ip}}` will be replaced with the value from the 'primary_lan_ip' column in your CSV file.

### Q: Can I use any CSV column name as a placeholder?
**A:** No, special columns are handled by application logic and should NOT be used as `{{placeholders}}` in your template. Special columns include: `id`, `name`, `primary_lan_ip`, `desc`, `custom1`, `custom2`, all tag columns (`site_tags`, `lan_resource_tags`, `cp_host_tags`, `wildcard_resource_tags`), and `disable_force_dns`. All other columns can be referenced as `{{column_name}}` in your template. See the [CSV Column Mapping](#csv-column-mapping) section for details.

### Q: What are special columns and how are they used?
**A:** Special columns are CSV columns that are processed by the application's logic rather than being used as template placeholders:
- `id` - Required for router matching
- `name` - Cached and used for exchange site creation
- `primary_lan_ip` - Cached and used for site and LAN resource creation
- `desc` - Injected into device configuration via API
- `custom1`, `custom2` - Set as NCM custom fields via API
- Tag columns - Merged with global tags for sites and resources
- `disable_force_dns` - Overrides global Force DNS setting per device

These columns should NOT be used as `{{placeholders}}` in config_template.json.

### Q: How do I provision devices with different configurations?
**A:** Create different rows in your CSV file with device-specific values, or create multiple template files and specify different `config_template_file` values per group.

### Q: How do I add tags to sites and resources?
**A:** There are two ways to add tags:
1. **Global tags** (wizard Step 4): Enter comma or semicolon-separated values (e.g., `production,east` or `production;east`)
2. **Per-device tags** (CSV): Add columns `site_tags`, `lan_resource_tags`, `cp_host_tags`, `wildcard_resource_tags` with semicolon-separated values (e.g., `branch;west`)

Tags from both sources are automatically merged and deduplicated. Tags must be at least 2 characters long and contain only lowercase letters and numbers.

### Q: Why is my exchange site created with the old system name?
**A:** If bulk configuration is enabled, ensure the router ID exists in your CSV file and the `name` column contains the desired system name. The application caches this value and uses it for site creation. If the router is not found in the CSV or bulk config is disabled, it falls back to reading the system_id from the device's running configuration.

### Q: What happens if site creation succeeds but resource creation fails?
**A:** The application tracks these as separate steps with independent state markers. On restart, it will skip site creation (already complete), retrieve the cached site_id, and retry resource creation. This prevents duplicate sites and enables granular recovery.

### Q: What if firmware sync takes longer than the timeout?
**A:** Increase `FIRMWARE_CHECK_TIMEOUT` constant in the script.

### Q: Can I run this on devices already in production?
**A:** No, devices must be in the staging group for the application to run.

### Q: How do I know if provisioning completed successfully?
**A:** Check device logs for "NCX Self Provisioning Complete" message and verify device moved to production group.

### Q: Can I provision multiple devices simultaneously?
**A:** Yes, each device runs independently. Add multiple devices to staging group. For best performance, limit batches to 50 devices at a time.

### Q: What if I need to re-provision a device?
**A:** Move device back to staging group and clear state markers, or use cleanup_state() function.

### Q: How do I update the application?
**A:** Build new version, upload to NCM, and reassign to staging group. Devices will auto-update.

### Q: How do I disable DNS force redirect for devices?
**A:** There are two ways:
1. **Global setting** (wizard Step 3): Check "Disable Force DNS Redirect" to apply to all devices
2. **Per-device setting** (CSV): Add `disable_force_dns` column and set to 'true' for specific devices

Per-device CSV settings override the global wizard setting. Set to 'true' (case-insensitive) to disable force DNS redirect.

## Support

For issues or questions:
1. Review this documentation
2. Check device logs
3. Verify configuration using the NCX Staging Wizard
4. Contact your NCM administrator

## Version History

### Version 2.5
- Fixed CP host and wildcard FQDN resource creation failing silently when no DNS option configured
- Fixed `local_domain` for FQDN resources to fall back to `cp.get('config/system/local_domain')` when appdata value is empty
- Fixed per-device CSV tags not merging with global tags due to asynchronous NCM config push overwriting locally-written appdata
- Removed `csv_*` appdata keys — CSV tags now passed in-memory from bulk config step to site/resource/DNS steps
- Added error response logging for all `create_exchange_resource` API calls
- Added 2-second delay between each resource creation call
- Wizard: CP host and wildcard FQDN resource checkboxes now disabled unless LAN as DNS or Custom DNS Servers is enabled
- Wizard: Added descriptive note under both FQDN resource checkboxes explaining the DNS requirement

### Version 2.3
- Replaced ncx_staging.py with ncx_staging_wizard.py web-based configuration tool
- Added interactive 6-step wizard with real-time validation and browser-based interface
- Added built-in file editor with CSV grid view and JSON syntax highlighting
- Added custom DNS server configuration (primary and secondary, mutually exclusive with LAN as DNS)
- Added global Force DNS configuration with per-device CSV override capability
- Added VPN tunnel status monitoring before DNS configuration
- Added color-coded CSV column analysis (green=config, blue=NCM/NCX, red=missing)
- Added collapsible warning messages for bulk configuration validation
- Enhanced tagging to support both comma and semicolon separators
- Enhanced state tracking with VPN tunnel and DNS force redirect markers
- Enhanced cached data with LAN IP and per-device tag storage
- Updated provisioning to 9 steps (added DNS configuration step with VPN check)
- Updated to 22 appdata parameters (added primary_dns, secondary_dns, disable_force_dns)
- Improved configuration workflow with comprehensive validation and error reporting
- Improved recovery with granular state tracking and cached data for all resources

### Version 2.2
- Enhanced tagging system with global and per-site/resource tags
- Added support for unique tags per resource type (LAN, CP host, wildcard)
- CSV tags use semicolon delimiter to avoid conflicts with comma-separated values
- Automatic tag merging and deduplication
- Added LAN IP caching for accurate site and resource creation
- Added FQDN validation for LOCAL_DOMAIN and hostname

### Version 2.1
- Separated site creation and resource creation into distinct steps (8 total steps)
- Added system_id caching from bulk config for accurate site naming
- Added site_id caching for resource creation recovery
- Fixed tag format conversion (comma-separated string to list)
- Enhanced recovery with granular state tracking per step
- Improved resource creation to use cached data

### Version 2.0
- Added state management for recovery
- Implemented retry logic with exponential backoff
- Added progress indicators
- Implemented timeout protection
- Added input validation
- Moved configuration to JSON template
- Added log sanitization
- Improved error handling
- Added dependency injection
- Added tag support for sites and resources

### Version 1.0
- Initial release
- Basic provisioning workflow
- License application
- Site and resource creation
