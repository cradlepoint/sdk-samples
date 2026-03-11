"""NCX Self-Provisioning SDK Application.

Runs on Ericsson routers to automate zero-touch provisioning to NCX/SASE
networks when devices are moved to a staging group. Executes a 9-step
provisioning workflow with state management and automatic recovery.

Provisioning Steps:
    1. System Readiness - Wait for uptime and WAN connectivity
    2. API Key Retrieval - Extract NCM credentials from device certificates
    3. Readiness Validation - Verify firmware sync and staging group assignment
    4. Bulk Configuration - Apply device-specific config from CSV (optional)
    5. License Application - Apply Secure Connect, SD-WAN, HMF, AI licenses
    6. Exchange Site Creation - Create NCX/SASE site with DNS and tags
    7. Exchange Resource Provisioning - Create LAN subnet, FQDN, wildcard resources
    8. DNS Force Redirect - Disable force DNS if configured (optional)
    9. Production Group Assignment - Move device to production group and cleanup

Key Features:
    - Persistent state tracking enables recovery after failures/reboots
    - Automatic retry with exponential backoff for transient API failures
    - Template-based bulk configuration with {{placeholder}} syntax
    - Special CSV columns: id, name, primary_lan_ip, desc, custom1/2, tags, disable_force_dns
    - Template placeholders: any non-special CSV column as {{column_name}}
    - Global and per-device tagging with automatic merge and deduplication
    - DNS options: LAN as DNS with local domain, or custom DNS servers (primary/secondary)
    - CP host and wildcard FQDN resources require DNS to be configured (LAN as DNS or custom DNS)
    - local_domain for FQDN resources: uses appdata value if set, otherwise falls back to cp.get('config/system/local_domain')
    - Global Force DNS setting with per-device CSV override
    - System name and LAN IP caching for accurate site/resource creation
    - Hostname validation for FQDN compliance
    - VPN tunnel status checking before DNS configuration
    - Sanitized logging prevents credential exposure
    - Idempotent operations safe to re-run

State Management:
    Persistent appdata markers track step completion:
    - prov_state_readiness: Firmware validation complete
    - prov_state_bulk_config: Bulk configuration applied
    - prov_state_license: Licenses applied
    - prov_state_site: Exchange site created
    - prov_state_resources: Exchange resources provisioned
    - prov_state_vpn_tunnel: VPN tunnel up
    - prov_state_dns_force: DNS force redirect configured

    Cached data for recovery and dependent steps:
    - bulk_config_system_id: System name from CSV (used for site creation)
    - bulk_config_lan_ip: Primary LAN IP from CSV (used for site/resource creation)
    - exchange_site_id: Created site ID (used for resource creation)

    Note: Per-device CSV tags and disable_force_dns are passed in-memory from
    self_bulk_config() to downstream steps — not stored in appdata — to avoid
    being overwritten by asynchronous NCM config pushes.

Configuration:
    All parameters retrieved from staging group appdata, configured via
    ncx_staging_wizard.py (web-based tool, never deployed to devices).
    
    Supports both NCX and SASE platform licenses with automatic prefix validation.
    
    Global tags (comma/semicolon-separated) merge with per-device CSV tags
    (semicolon-separated) with automatic deduplication.

Bulk Configuration:
    Optional template-based configuration using JSON templates with {{placeholder}}
    syntax. CSV columns map to placeholders for device-specific values.
    
    Required CSV column:
    - id: Router ID for matching (required)
    
    Special CSV columns (processed by app logic, not template placeholders):
    - name: System name (optional, cached for site creation, fallback to device config)
    - primary_lan_ip: Primary LAN IP (optional, cached for site/resource, fallback to device)
    - desc: Description (optional, injected into device config via API)
    - custom1, custom2: NCM custom fields (optional, set via NCM API)
    - site_tags: Per-device site tags (optional, semicolon-separated)
    - lan_resource_tags: Per-device LAN resource tags (optional)
    - cp_host_tags: Per-device CP host resource tags (optional)
    - wildcard_resource_tags: Per-device wildcard resource tags (optional)
    - disable_force_dns: Override global Force DNS (optional, 'true' to disable)
    
    Template placeholder columns:
    - Any non-special column can be used as {{column_name}} in config_template.json

Deployment Workflow:
    1. Run ncx_staging_wizard.py to configure staging group (REQUIRED FIRST)
    2. Build SDK package: python make.py build ncx_self_provision
    3. Upload package to NCM and assign to staging group
    4. Move devices to staging group (max 50 at a time recommended)
    5. Monitor device logs for "[Step X/9]" progress indicators
    6. Devices automatically move to production group when complete

Recovery:
    Application automatically resumes from last completed step after:
    - Device reboot or restart
    - Application crash or restart
    - Network interruption
    - Transient API failures
    
    State markers and cached data enable granular recovery without
    repeating completed steps or creating duplicate resources.

Security:
    - API keys stored encrypted as device certificates
    - Sensitive data automatically redacted from logs
    - All API calls use HTTPS
    - No hardcoded credentials
    - Configuration wizard (ncx_staging_wizard.py) never deployed to devices

Files Deployed to Devices:
    - ncx_self_provision.py (this file)
    - cp.py (router library)
    - ncm.py (NCM API library)
    - config_template.json (if bulk config enabled)
    - router_grid.csv (if bulk config enabled)
    - start.sh, package.ini (SDK metadata)

Files Never Deployed (Local Use Only):
    - ncx_staging_wizard.py (web-based configuration tool)
    - index.html (wizard web interface)
    - static/ (wizard CSS/JS/assets)
    - README.md (documentation)
"""

import ipaddress
import json
import os
import time
from typing import Any, Dict, List, Optional

import cp
import ncm


def parse_csv_line(line: str) -> List[str]:
    """Parse a single CSV line handling quoted fields.

    Args:
        line: CSV line to parse.

    Returns:
        List[str]: List of field values.

    """
    fields = []
    current_field = ''
    in_quotes = False

    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            fields.append(current_field)
            current_field = ''
        else:
            current_field += char

    fields.append(current_field)
    return fields


def read_csv(filename: str) -> List[Dict[str, str]]:
    """Read CSV file and return list of dictionaries.

    Args:
        filename: Path to CSV file.

    Returns:
        List[Dict[str, str]]: List of row dictionaries.

    """
    rows = []
    with open(filename, 'r') as f:
        content = f.read()

        # Remove UTF-8 BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]
        elif content.startswith('\xef\xbb\xbf'):
            content = content[3:]

        lines = content.strip().split('\n')
        if not lines:
            return rows

        headers = parse_csv_line(lines[0])

        for line in lines[1:]:
            if line.strip():
                values = parse_csv_line(line)
                row = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        row[header] = values[i]
                    else:
                        row[header] = ''
                rows.append(row)

    return rows


# Configuration Constants
UPTIME_WAIT_SECONDS = 120
FIRMWARE_CHECK_INTERVAL = 15
FIRMWARE_CHECK_TIMEOUT = 3600
STEP_DELAY_SECONDS = 5
COMPLETION_WAIT_SECONDS = 600
DEFAULT_CSV_FILE = 'router_grid.csv'
DEFAULT_CONFIG_TEMPLATE = 'config_template.json'
LICENSE_APPLY_DELAY = 1
MAX_RETRIES = 3
RETRY_DELAY = 5

# State tracking keys
STATE_READINESS = 'prov_state_readiness'
STATE_BULK_CONFIG = 'prov_state_bulk_config'
STATE_LICENSE = 'prov_state_license'
STATE_SITE = 'prov_state_site'
STATE_RESOURCES = 'prov_state_resources'
STATE_VPN_TUNNEL = 'prov_state_vpn_tunnel'
STATE_DNS_FORCE = 'prov_state_dns_force'

# VPN tunnel check settings
VPN_TUNNEL_CHECK_INTERVAL = 10  # Check every 10 seconds
VPN_TUNNEL_CHECK_TIMEOUT = 300  # 5 minutes total timeout
VPN_TUNNEL_MAX_ATTEMPTS = VPN_TUNNEL_CHECK_TIMEOUT // VPN_TUNNEL_CHECK_INTERVAL


def sanitize_log(message: str) -> str:
    """Sanitize log messages to remove sensitive data.

    Args:
        message: Log message to sanitize.

    Returns:
        str: Sanitized log message.

    """
    sensitive_keys = ['api_key', 'api-key', 'token', 'bearer', 'password']
    sanitized = message
    for key in sensitive_keys:
        if key.lower() in sanitized.lower():
            sanitized = sanitized.split(':')[0] + ': [REDACTED]'
            break
    return sanitized


def validate_hostname(hostname: str) -> None:
    """Validate hostname format for FQDN compliance.

    Hostname must contain only letters, numbers, and hyphens, and be max 50 chars.
    This validation ensures hostnames are compliant for use as exchange site names.

    Args:
        hostname: Hostname to validate.

    Raises:
        ValueError: If hostname is empty, exceeds 50 characters, or contains
                   invalid characters (only alphanumeric and hyphens allowed).
    
    Validation Rules:
        - Cannot be empty
        - Maximum 50 characters
        - Only alphanumeric characters and hyphens allowed
        - Used for exchange site creation (Step 6)

    """
    if not hostname:
        raise ValueError("Hostname cannot be empty")
    
    if len(hostname) > 50:
        raise ValueError(
            f"Hostname '{hostname}' exceeds 50 characters ({len(hostname)} chars). "
            f"Maximum length is 50 characters."
        )

    for char in hostname:
        if not (char.isalnum() or char == '-'):
            raise ValueError(
                f"Hostname '{hostname}' contains invalid character '{char}'. "
                f"Only letters, numbers, and hyphens allowed."
            )


def merge_tags(global_tags: str, csv_tags: str) -> str:
    """Merge global tags with CSV tags, removing duplicates.
    
    Supports both comma and semicolon separators. Global tags from staging
    group configuration are typically comma-separated, while per-device tags
    from CSV are semicolon-separated to avoid conflicts with CSV format.

    Args:
        global_tags: Comma or semicolon-separated global tags from appdata.
        csv_tags: Comma or semicolon-separated tags from CSV.

    Returns:
        str: Comma-separated unique tag string, sorted alphabetically.
        
    Example:
        >>> merge_tags('production,east', 'branch;east;retail')
        'branch,east,production,retail'

    """
    tags = set()

    # Add global tags (support both comma and semicolon)
    if global_tags:
        for sep in [',', ';']:
            if sep in global_tags:
                tags.update(global_tags.split(sep))
                break
        else:
            tags.add(global_tags)

    # Add CSV tags (support both comma and semicolon)
    if csv_tags:
        for sep in [',', ';']:
            if sep in csv_tags:
                tags.update(csv_tags.split(sep))
                break
        else:
            tags.add(csv_tags)

    # Remove empty strings, strip whitespace, and return comma-separated string
    unique_tags = sorted([tag.strip() for tag in tags if tag.strip()])
    return ','.join(unique_tags) if unique_tags else ''


def log_progress(step: int, total: int, message: str) -> None:
    """Log progress with step counter.

    Args:
        step: Current step number.
        total: Total number of steps.
        message: Progress message.

    """
    progress_msg = f"[Step {step}/{total}] {message}"
    cp.log(sanitize_log(progress_msg))


def get_state(key: str) -> Optional[str]:
    """Get provisioning state value.

    Args:
        key: State key name.

    Returns:
        Optional[str]: State value or None.

    """
    return cp.get_appdata(key)


def set_state(key: str, value: str) -> None:
    """Set provisioning state value.

    Args:
        key: State key name.
        value: State value.

    """
    cp.put_appdata(name=key, value=value)


def clear_state(key: str) -> None:
    """Clear provisioning state value.

    Args:
        key: State key name.

    """
    cp.delete_appdata(name=key)


def validate_appdata(key: str, required: bool = True) -> Optional[str]:
    """Validate appdata value exists and is not empty.

    Args:
        key: Appdata key name.
        required: Whether the value is required.

    Returns:
        Optional[str]: Appdata value or None.

    Raises:
        ValueError: If required value is missing or empty.

    """
    value = cp.get_appdata(key)
    if required and (value is None or value == ''):
        raise ValueError(f"Required appdata '{key}' is missing or empty")
    return value


def validate_boolean_appdata(key: str, default: bool = False) -> bool:
    """Validate and convert boolean appdata value.

    Args:
        key: Appdata key name.
        default: Default value if not found.

    Returns:
        bool: Boolean value.

    Raises:
        ValueError: If value is not 'True' or 'False'.

    """
    value = cp.get_appdata(key)
    if value is None or value == '':
        return default
    if value not in ('True', 'False'):
        raise ValueError(f"Appdata '{key}' must be 'True' or 'False', got '{value}'")
    return value == 'True'


def validate_group_ids(staging_id: str, prod_id: str) -> None:
    """Validate group IDs are numeric and different.

    Args:
        staging_id: Staging group ID.
        prod_id: Production group ID.

    Raises:
        ValueError: If validation fails.

    """
    if not staging_id.isdigit():
        raise ValueError(f"Staging group ID must be numeric, got '{staging_id}'")
    if not prod_id.isdigit():
        raise ValueError(f"Production group ID must be numeric, got '{prod_id}'")
    if staging_id == prod_id:
        raise ValueError("Staging and production group IDs must be different")


def retry_on_failure(func, *args, max_retries: int = MAX_RETRIES,
                     delay: int = RETRY_DELAY, **kwargs) -> Any:
    """Retry function on failure with exponential backoff.

    Args:
        func: Function to retry.
        *args: Positional arguments for function.
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        **kwargs: Keyword arguments for function.

    Returns:
        Any: Function return value.

    Raises:
        Exception: If all retries fail.

    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = delay * (2 ** attempt)
            cp.log(f"Attempt {attempt + 1} failed: {e}. "
                   f"Retrying in {wait_time}s...")
            time.sleep(wait_time)


def validate_readiness(n2_client: ncm.NcmClientv2) -> bool:
    """Validate router firmware and group assignment.
    
    Validates that:
    1. Router is in the staging group
    2. Staging and production groups have matching target firmware
    3. Router's actual firmware matches its target firmware (waits if needed)

    Args:
        n2_client: NCM v2 API client.

    Returns:
        bool: True if validation successful, False otherwise.

    """
    if get_state(STATE_READINESS) == 'complete':
        cp.log("Readiness validation already complete, skipping")
        return True

    try:
        device_name = cp.get_name()
        staging_group_id = validate_appdata('staging_group_id')
        prod_group_id = validate_appdata('prod_group_id')

        staging_group = n2_client.get_group_by_id(group_id=staging_group_id)
        staging_group_firmware_id = staging_group['target_firmware'].split('/')[6]
        prod_group = n2_client.get_group_by_id(group_id=prod_group_id)
        prod_group_firmware_id = prod_group['target_firmware'].split('/')[6]

        # Validate that staging and production groups have the same target firmware
        if staging_group_firmware_id != prod_group_firmware_id:
            msg = (
                f"ERROR: Staging group firmware ({staging_group_firmware_id}) "
                f"does not match production group firmware ({prod_group_firmware_id})"
            )
            cp.log(msg)
            return False
        
        cp.log(f"Staging and production groups have matching target firmware: {staging_group_firmware_id}")

        def get_router_data() -> Dict[str, str]:
            """Get current router data."""
            router_info = n2_client.get_router_by_name(router_name=device_name)
            return {
                'actual_firmware': router_info['actual_firmware'].split('/')[6],
                'target_firmware': router_info['target_firmware'].split('/')[6],
                'group_id': router_info['group'].split('/')[6]
            }

        router_data = get_router_data()

        if router_data['group_id'] != staging_group_id:
            msg = (
                f"ERROR: Router group ID ({router_data['group_id']}) "
                f"does not match staging group ID ({staging_group_id})"
            )
            cp.log(msg)
            return False

        start_time = time.time()
        while router_data['actual_firmware'] != router_data['target_firmware']:
            if time.time() - start_time > FIRMWARE_CHECK_TIMEOUT:
                cp.log("ERROR: Firmware sync timeout exceeded")
                return False
            msg = (
                f"Router actual firmware ({router_data['actual_firmware']}) "
                f"does not match target firmware "
                f"({router_data['target_firmware']}). "
                f"Waiting {FIRMWARE_CHECK_INTERVAL}s..."
            )
            cp.log(msg)
            time.sleep(FIRMWARE_CHECK_INTERVAL)
            router_data = get_router_data()

        msg = (
            f"Router actual firmware ({router_data['actual_firmware']}) "
            f"matches target firmware ({router_data['target_firmware']})"
        )
        cp.log(msg)

        set_state(STATE_READINESS, 'complete')
        return True

    except Exception as e:
        cp.log(f"ERROR in validate_readiness: {e}")
        return False


def build_keys() -> Dict[str, str]:
    """Build APIv2 keys and APIv3 Bearer Token from device config.

    Returns:
        Dict[str, str]: API keys dictionary.

    Raises:
        Exception: If API key retrieval fails.

    """
    try:
        api_keys = cp.get_ncm_api_keys()
        cp.log("API keys retrieved successfully")
        return api_keys
    except Exception as e:
        cp.log(f"ERROR building API keys: {e}")
        raise


def load_config_template(template_file: str) -> List[Any]:
    """Load configuration template from JSON file.

    Args:
        template_file: Path to JSON template file.

    Returns:
        List[Any]: Configuration template.

    Raises:
        FileNotFoundError: If template file not found.
        json.JSONDecodeError: If template file is invalid JSON.

    """
    if not os.path.exists(template_file):
        raise FileNotFoundError(f"Config template {template_file} not found")

    with open(template_file, 'r', encoding='utf-8') as f:
        template = json.load(f)

    return template


def replace_placeholders(obj: Any, row_data: Dict[str, str]) -> Any:
    """Recursively replace placeholder strings with CSV values.

    Placeholders in the template use {{column_name}} syntax.
    Example: {{primary_lan_ip}} will be replaced with the value from
    the 'primary_lan_ip' column in the CSV.

    Args:
        obj: Object to process (dict, list, str, or other).
        row_data: CSV row data with column names as keys.

    Returns:
        Any: Object with placeholders replaced.

    """
    import re

    if isinstance(obj, dict):
        return {k: replace_placeholders(v, row_data) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_placeholders(item, row_data) for item in obj]
    elif isinstance(obj, str):
        # Replace {{column_name}} with value from CSV
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, obj)
        result = obj
        for match in matches:
            placeholder = f'{{{{{match}}}}}'
            value = row_data.get(match, '')
            result = result.replace(placeholder, str(value))
        return result
    else:
        return obj


def apply_csv_values(template: List[Any], row_data: Dict[str, str]) -> List[Any]:
    """Apply CSV values to configuration template.

    Replaces all {{column_name}} placeholders in the template with
    corresponding values from the CSV row.

    Args:
        template: Configuration template with placeholders.
        row_data: CSV row data.

    Returns:
        List[Any]: Configuration with applied values.

    """
    return replace_placeholders(template, row_data)


def self_bulk_config(n2_client: ncm.NcmClientv2) -> Optional[Dict[str, str]]:
    """Apply bulk configuration from CSV file if enabled.

    Args:
        n2_client: NCM v2 API client.

    Returns:
        Optional[Dict[str, str]]: Matched CSV row if found, None otherwise.

    """
    bulk_config_already_complete = get_state(STATE_BULK_CONFIG) == 'complete'
    if bulk_config_already_complete:
        cp.log("Bulk configuration already complete, skipping config patch")

    try:
        self_bulk_config_enabled = cp.get_appdata('self_bulk_config')
        if self_bulk_config_enabled != 'True':
            if not bulk_config_already_complete:
                cp.log("Self bulk configuration disabled")
                set_state(STATE_BULK_CONFIG, 'skipped')
            return None

        bulk_config_file = (
            cp.get_appdata('bulk_config_file') or DEFAULT_CSV_FILE
        )
        config_template_file = (
            cp.get_appdata('config_template_file') or DEFAULT_CONFIG_TEMPLATE
        )
        router_id = int(cp.get('status/ecm/client_id'))
        cp.log("Self bulk configuration enabled")
        cp.log(f'Searching {bulk_config_file} for router ID: {router_id}')

        if not os.path.exists(bulk_config_file):
            raise FileNotFoundError(f"CSV file {bulk_config_file} not found")

        template = load_config_template(config_template_file)

        rows = read_csv(bulk_config_file)

        # Check for required 'id' column
        if rows and 'id' not in rows[0]:
            raise ValueError("CSV file missing required 'id' column")

        for row in rows:
            try:
                if int(row['id']) == router_id:
                    cp.log(f'Found router {router_id} in {bulk_config_file}')

                    if not bulk_config_already_complete:
                        config_data = apply_csv_values(template, row)
                        config = {'configuration': config_data}

                        desc_value = row.get('desc')
                        if desc_value and desc_value != '':
                            config['configuration'][0]['system']['desc'] = desc_value

                        retry_on_failure(
                            n2_client.patch_configuration_managers,
                            router_id=router_id,
                            config_man_json=config
                        )
                        cp.log(f'Successfully patched config to router: {router_id}')

                        custom1_value = row.get('custom1')
                        if custom1_value and custom1_value != '':
                            retry_on_failure(
                                n2_client.set_custom1,
                                router_id=router_id,
                                text=custom1_value
                            )
                            cp.log(f'Set custom1 to: {custom1_value}')

                        custom2_value = row.get('custom2')
                        if custom2_value and custom2_value != '':
                            retry_on_failure(
                                n2_client.set_custom2,
                                router_id=router_id,
                                text=custom2_value
                            )
                            cp.log(f'Set custom2 to: {custom2_value}')

                        set_state(STATE_BULK_CONFIG, 'complete')

                    # Cache system_id and LAN IP in appdata for recovery across restarts
                    system_id = row.get('name')
                    if system_id:
                        cp.put_appdata('bulk_config_system_id', system_id)
                        cp.log(f'Stored system_id for site creation: {system_id}')

                    lan_ip = row.get('primary_lan_ip')
                    if lan_ip:
                        cp.put_appdata('bulk_config_lan_ip', lan_ip)
                        cp.log(f'Stored LAN IP for site creation: {lan_ip}')

                    return row
            except (ValueError, KeyError) as e:
                cp.log(f'Error processing row: {e}')
                continue

        cp.log(f'Router {router_id} not found in {bulk_config_file}')
        if not bulk_config_already_complete:
            set_state(STATE_BULK_CONFIG, 'not_found')
        return None

    except FileNotFoundError as e:
        cp.log(f'ERROR: {e}')
        raise
    except Exception as e:
        cp.log(f'ERROR in self_bulk_config: {e}')
        raise
    return None


def apply_license(n3_client: ncm.NcmClientv3) -> None:
    """Apply Secure Connect, SD-WAN, and HMF licenses to router.

    Args:
        n3_client: NCM v3 API client.

    Raises:
        Exception: If license application fails.

    """
    if get_state(STATE_LICENSE) == 'complete':
        cp.log("License application already complete, skipping")
        return

    try:
        secure_connect_lic = validate_appdata('secure_connect_lic')
        mac = cp.get('status/product_info/mac0')
        msg = f"Applying Secure Connect license {secure_connect_lic} to {mac}"
        cp.log(msg)
        retry_on_failure(n3_client.regrade, mac=mac, subscription_id=secure_connect_lic)

        time.sleep(LICENSE_APPLY_DELAY)
        sdwan_lic = cp.get_appdata('sdwan_lic')
        if sdwan_lic:
            cp.log(f"Applying SD-WAN license {sdwan_lic} to {mac}")
            retry_on_failure(n3_client.regrade, mac=mac, subscription_id=sdwan_lic)

        time.sleep(LICENSE_APPLY_DELAY)
        hmf_lic = cp.get_appdata('hmf_lic')
        if hmf_lic:
            cp.log(f"Applying HMF license {hmf_lic} to {mac}")
            retry_on_failure(n3_client.regrade, mac=mac, subscription_id=hmf_lic)

        time.sleep(LICENSE_APPLY_DELAY)
        ai_lic = cp.get_appdata('ai_lic')
        if ai_lic:
            cp.log(f"Applying AI license {ai_lic} to {mac}")
            retry_on_failure(n3_client.regrade, mac=mac, subscription_id=ai_lic)

        set_state(STATE_LICENSE, 'complete')
    except Exception as e:
        cp.log(f"ERROR applying licenses: {e}")
        raise


def create_exchange_site(n3_client: ncm.NcmClientv3,
                         csv_row: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Create exchange site.
    
    Validates hostname compliance before creating the site. Site name is sourced
    from bulk config CSV (if available) or device's current system_id.

    Args:
        n3_client: NCM v3 API client.
        csv_row: Matched CSV row from bulk config (optional).

    Returns:
        Dict[str, Any]: Site information including site ID.

    Raises:
        ValueError: If hostname validation fails (max 50 chars, alphanumeric + hyphens only).
        Exception: If site creation fails.

    """
    if get_state(STATE_SITE) == 'complete':
        cp.log("Exchange site already created, skipping")
        # Retrieve cached site_id if available
        site_id = cp.get_appdata('exchange_site_id')
        if site_id:
            return {'id': site_id}
        return {}

    try:
        # Use system_id from bulk config if available, otherwise from device config
        site_name = cp.get_appdata('bulk_config_system_id') or cp.get('config/system/system_id')

        # Validate hostname is FQDN compliant
        validate_hostname(site_name)

        exchange_network_id = validate_appdata('exchange_network_id')
        router_id = str(cp.get('status/ecm/client_id'))
        lan_as_dns = cp.get_appdata('lan_as_dns') == 'True'
        # Use cached LAN IP from bulk config if available, otherwise from device config
        lan_ip = cp.get_appdata('bulk_config_lan_ip') or cp.get('config/lan/0/ip_address')

        # Merge global and CSV tags for site
        global_site_tags = cp.get_appdata('site_tags') or ''
        csv_site_tags = csv_row.get('site_tags', '') if csv_row else ''
        site_tags_str = merge_tags(global_site_tags, csv_site_tags)
        site_tags = site_tags_str.split(',') if site_tags_str else []

        # Get custom DNS servers if provided
        primary_dns_custom = cp.get_appdata('primary_dns') or ''
        secondary_dns_custom = cp.get_appdata('secondary_dns') or ''

        # Only set local_domain if lan_as_dns is True
        if lan_as_dns:
            local_domain = f'{site_name}.{validate_appdata("local_domain")}'
            msg = (
                f"Creating exchange site {site_name} on exchange network "
                f"{exchange_network_id} for router {router_id}"
            )
            cp.log(msg)
            msg = (
                f"LAN as DNS: {lan_as_dns}, local domain: {local_domain}, "
                f"primary DNS: {lan_ip}"
            )
            cp.log(msg)
            if site_tags:
                cp.log(f"Site tags: {site_tags}")
                site_info = retry_on_failure(
                    n3_client.create_exchange_site,
                    name=site_name,
                    exchange_network_id=exchange_network_id,
                    router_id=router_id,
                    lan_as_dns=lan_as_dns,
                    local_domain=local_domain,
                    primary_dns=lan_ip,
                    tags=site_tags
                )
            else:
                site_info = retry_on_failure(
                    n3_client.create_exchange_site,
                    name=site_name,
                    exchange_network_id=exchange_network_id,
                    router_id=router_id,
                    lan_as_dns=lan_as_dns,
                    local_domain=local_domain,
                    primary_dns=lan_ip
                )
        else:
            msg = (
                f"Creating exchange site {site_name} on exchange network "
                f"{exchange_network_id} for router {router_id}"
            )
            cp.log(msg)
            cp.log(f"LAN as DNS: {lan_as_dns}")
            
            # Build kwargs for site creation
            site_kwargs = {
                'name': site_name,
                'exchange_network_id': exchange_network_id,
                'router_id': router_id,
                'lan_as_dns': lan_as_dns
            }
            
            # Add custom DNS if provided
            if primary_dns_custom:
                site_kwargs['primary_dns'] = primary_dns_custom
                cp.log(f"Using custom primary DNS: {primary_dns_custom}")
            if secondary_dns_custom:
                site_kwargs['secondary_dns'] = secondary_dns_custom
                cp.log(f"Using custom secondary DNS: {secondary_dns_custom}")
            
            # Add tags if provided
            if site_tags:
                site_kwargs['tags'] = site_tags
                cp.log(f"Site tags: {site_tags}")
            
            site_info = retry_on_failure(
                n3_client.create_exchange_site,
                **site_kwargs
            )

        cp.log(f"Exchange site created successfully: {site_info['id']}")
        # Cache site_id for resource creation
        cp.put_appdata('exchange_site_id', site_info['id'])
        set_state(STATE_SITE, 'complete')
        return site_info
    except Exception as e:
        cp.log(f"ERROR creating exchange site: {e}")
        raise


def create_exchange_site_resources(n3_client: ncm.NcmClientv3,
                                   site_info: Dict[str, Any],
                                   csv_row: Optional[Dict[str, str]] = None) -> None:
    """Create exchange site resources.

    Args:
        n3_client: NCM v3 API client.
        site_info: Site information dictionary.
        csv_row: Matched CSV row from bulk config (optional).

    Raises:
        Exception: If resource creation fails.

    """
    if get_state(STATE_RESOURCES) == 'complete':
        cp.log("Exchange site resources already created, skipping")
        return

    try:
        site_id = site_info.get('id') or cp.get_appdata('exchange_site_id')
        if not site_id:
            raise ValueError("Site ID not available for resource creation")

        site_name = cp.get_appdata('bulk_config_system_id') or cp.get('config/system/system_id')
        create_lan_resource = (
            cp.get_appdata('create_lan_resource') == 'True'
        )
        create_cp_host_resource = (
            cp.get_appdata('create_cp_host_resource') == 'True'
        )
        create_wildcard_resource = (
            cp.get_appdata('create_wildcard_resource') == 'True'
        )
        # Use cached LAN IP from bulk config if available, otherwise from device config
        lan_ip = cp.get_appdata('bulk_config_lan_ip') or cp.get('config/lan/0/ip_address')
        lan_netmask = cp.get('config/lan/0/netmask')
        lan_cidr = str(
            ipaddress.ip_network(f'{lan_ip}/{lan_netmask}', strict=False)
        )
        local_domain_suffix = cp.get_appdata('local_domain') or cp.get('config/system/local_domain') or ''
        local_domain = f'{site_name}.{local_domain_suffix}' if local_domain_suffix else site_name

        # Merge global and CSV tags for each resource type
        global_lan_tags = cp.get_appdata('lan_resource_tags') or ''
        csv_lan_tags = csv_row.get('lan_resource_tags', '') if csv_row else ''
        cp.log(f"LAN resource tags - global: '{global_lan_tags}', csv: '{csv_lan_tags}'")
        lan_resource_tags_str = merge_tags(global_lan_tags, csv_lan_tags)
        lan_resource_tags = lan_resource_tags_str.split(',') if lan_resource_tags_str else []

        global_cp_tags = cp.get_appdata('cp_host_tags') or ''
        csv_cp_tags = csv_row.get('cp_host_tags', '') if csv_row else ''
        cp.log(f"CP host resource tags - global: '{global_cp_tags}', csv: '{csv_cp_tags}'")
        cp_host_tags_str = merge_tags(global_cp_tags, csv_cp_tags)
        cp_host_tags = cp_host_tags_str.split(',') if cp_host_tags_str else []

        global_wildcard_tags = cp.get_appdata('wildcard_tags') or ''
        csv_wildcard_tags = csv_row.get('wildcard_resource_tags', '') if csv_row else ''
        cp.log(f"Wildcard resource tags - global: '{global_wildcard_tags}', csv: '{csv_wildcard_tags}'")
        wildcard_tags_str = merge_tags(global_wildcard_tags, csv_wildcard_tags)
        wildcard_tags = wildcard_tags_str.split(',') if wildcard_tags_str else []

        if create_lan_resource:
            cp.log(f"Creating LAN resource for {lan_cidr}")
            if lan_resource_tags:
                cp.log(f"LAN resource tags: {lan_resource_tags}")
            result = retry_on_failure(
                n3_client.create_exchange_resource,
                resource_name=f'{site_name}-lan',
                resource_type='exchange_ipsubnet_resources',
                site_id=site_id,
                ip=lan_cidr,
                **(({'tags': lan_resource_tags}) if lan_resource_tags else {})
            )
            if isinstance(result, str) and result.startswith('ERROR'):
                cp.log(f"ERROR creating LAN resource: {result}")
            time.sleep(2)

        if create_cp_host_resource:
            cp.log(f"Creating FQDN resource for router hostname: cp.{local_domain}")
            if cp_host_tags:
                cp.log(f"CP host resource tags: {cp_host_tags}")
            result = retry_on_failure(
                n3_client.create_exchange_resource,
                resource_name=f'{site_name}-cp',
                resource_type='exchange_fqdn_resources',
                site_id=site_id,
                domain=f'cp.{local_domain}',
                **(({'tags': cp_host_tags}) if cp_host_tags else {})
            )
            if isinstance(result, str) and result.startswith('ERROR'):
                cp.log(f"ERROR creating CP host resource: {result}")
            time.sleep(2)

        if create_wildcard_resource:
            cp.log(f"Creating wildcard FQDN resource: *.{local_domain}")
            if wildcard_tags:
                cp.log(f"Wildcard resource tags: {wildcard_tags}")
            result = retry_on_failure(
                n3_client.create_exchange_resource,
                resource_name=f'{site_name}-wildcard',
                resource_type='exchange_wildcard_fqdn_resources',
                site_id=site_id,
                domain=f'*.{local_domain}',
                **(({'tags': wildcard_tags}) if wildcard_tags else {})
            )
            if isinstance(result, str) and result.startswith('ERROR'):
                cp.log(f"ERROR creating wildcard resource: {result}")

        set_state(STATE_RESOURCES, 'complete')
    except Exception as e:
        cp.log(f"ERROR creating exchange site resources: {e}")
        raise


def check_vpn_tunnel_status() -> bool:
    """Check if VPN tunnel is up.
    
    Returns:
        bool: True if at least one VPN tunnel is in 'up' state, False otherwise.
    """
    try:
        tunnels = cp.get('status/vpn/tunnels')
        if not tunnels:
            return False
        
        for tunnel in tunnels:
            if tunnel.get('state') == 'up':
                cp.log(f"VPN tunnel '{tunnel.get('name')}' is up")
                return True
        
        return False
    except Exception as e:
        cp.log(f"ERROR checking VPN tunnel status: {e}")
        return False


def wait_for_vpn_tunnel() -> None:
    """Wait for VPN tunnel to come up with retry logic.
    
    Checks VPN tunnel status at regular intervals up to a maximum timeout.
    Uses state tracking to enable recovery after failures.
    
    Raises:
        RuntimeError: If VPN tunnel does not come up within timeout period.
    """
    if get_state(STATE_VPN_TUNNEL) == 'complete':
        cp.log("VPN tunnel check already complete, skipping")
        return
    
    try:
        cp.log(f"Waiting for VPN tunnel to come up (timeout: {VPN_TUNNEL_CHECK_TIMEOUT}s)")
        
        for attempt in range(1, VPN_TUNNEL_MAX_ATTEMPTS + 1):
            cp.log(f"VPN tunnel check attempt {attempt}/{VPN_TUNNEL_MAX_ATTEMPTS}")
            
            if check_vpn_tunnel_status():
                cp.log("VPN tunnel is up")
                set_state(STATE_VPN_TUNNEL, 'complete')
                return
            
            if attempt < VPN_TUNNEL_MAX_ATTEMPTS:
                cp.log(f"VPN tunnel not up yet, waiting {VPN_TUNNEL_CHECK_INTERVAL}s before retry")
                time.sleep(VPN_TUNNEL_CHECK_INTERVAL)
        
        # Timeout reached
        error_msg = f"VPN tunnel did not come up within {VPN_TUNNEL_CHECK_TIMEOUT}s timeout"
        cp.log(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)
        
    except Exception as e:
        cp.log(f"ERROR waiting for VPN tunnel: {e}")
        raise


def configure_dns_force_redirect(csv_row: Optional[Dict[str, str]] = None) -> None:
    """Configure DNS force redirect based on global and per-device settings.

    Args:
        csv_row: Matched CSV row from bulk config (optional).

    Raises:
        Exception: If DNS configuration fails.
    """
    if get_state(STATE_DNS_FORCE) == 'complete':
        cp.log("DNS force redirect configuration already complete, skipping")
        return
    
    try:
        # Check global setting from wizard
        global_disable = cp.get_appdata('disable_force_dns')
        global_disable_bool = global_disable and global_disable.lower() == 'true'
        
        # Check per-device setting from CSV (takes precedence)
        csv_disable = csv_row.get('disable_force_dns', '') if csv_row else ''
        csv_disable_bool = csv_disable and csv_disable.lower() == 'true'
        
        # Determine final setting (CSV overrides global)
        should_disable = False
        if csv_disable:
            # CSV value exists, use it (overrides global)
            should_disable = csv_disable_bool
            if should_disable:
                cp.log("Disabling DNS force redirect (per-device CSV setting)")
            else:
                cp.log("DNS force redirect enabled (per-device CSV setting overrides global)")
        elif global_disable_bool:
            # No CSV value, use global setting
            should_disable = True
            cp.log("Disabling DNS force redirect (global setting)")
        else:
            cp.log("DNS force redirect not modified (no global or per-device setting)")
        
        if should_disable:
            # Wait for VPN tunnel before applying force_redir
            wait_for_vpn_tunnel()

            cp.put('config/dns/force_redir', False)
            cp.log("DNS force redirect disabled successfully")

        set_state(STATE_DNS_FORCE, 'complete')
    except Exception as e:
        cp.log(f"ERROR configuring DNS force redirect: {e}")
        raise


def move_router_to_prod_group(n2_client: ncm.NcmClientv2) -> None:
    """Move router to production group.

    Args:
        n2_client: NCM v2 API client.

    Raises:
        Exception: If group assignment fails.

    """
    try:
        prod_group_id = validate_appdata('prod_group_id')
        router_id = str(cp.get('status/ecm/client_id'))
        
        # Clean up all appdata before moving
        cp.log("Cleaning up provisioning state and cached data")
        cleanup_state()
        
        cp.log(f"Moving to production group {prod_group_id}")
        retry_on_failure(
            n2_client.assign_router_to_group,
            router_id=router_id,
            group_id=prod_group_id
        )
        cp.log(f"Successfully moved to production group {prod_group_id}")
    except Exception as e:
        cp.log(f"ERROR moving router to production group: {e}")
        raise


def cleanup_state() -> None:
    """Clean up all provisioning state markers and cached data."""
    state_keys = [
        STATE_READINESS,
        STATE_BULK_CONFIG,
        STATE_LICENSE,
        STATE_SITE,
        STATE_RESOURCES,
        STATE_VPN_TUNNEL,
        STATE_DNS_FORCE,
        'bulk_config_system_id',
        'bulk_config_lan_ip',
        'exchange_site_id',
    ]
    for key in state_keys:
        try:
            clear_state(key)
        except Exception as e:
            cp.log(f"Warning: Failed to clear state key '{key}': {e}")
    
    # Brief sleep to allow appdata deletions to propagate
    time.sleep(2)


if __name__ == "__main__":
    total_steps = 9
    current_step = 0

    try:
        current_step += 1
        log_progress(current_step, total_steps, "Waiting for system readiness")
        cp.wait_for_uptime(UPTIME_WAIT_SECONDS)
        cp.wait_for_wan_connection()

        current_step += 1
        log_progress(current_step, total_steps, "Building API keys")
        api_keys = build_keys()
        n2 = ncm.NcmClientv2(api_keys=api_keys)
        n3 = ncm.NcmClientv3(api_key=api_keys['Bearer Token'])

        # Validate critical appdata parameters early
        cp.log("Validating configuration parameters")
        staging_group_id = validate_appdata('staging_group_id')
        prod_group_id = validate_appdata('prod_group_id')
        validate_group_ids(staging_group_id, prod_group_id)
        validate_appdata('exchange_network_id')
        validate_appdata('secure_connect_lic')
        lan_as_dns = validate_boolean_appdata('lan_as_dns', default=False)
        if lan_as_dns:
            validate_appdata('local_domain')
        cp.log("Configuration validation passed")

        current_step += 1
        log_progress(current_step, total_steps, "Validating readiness")
        if not validate_readiness(n2):
            cp.log('ERROR: Readiness validation failed')
            raise RuntimeError('Readiness validation failed')

        time.sleep(STEP_DELAY_SECONDS)

        current_step += 1
        log_progress(current_step, total_steps, "Applying bulk configuration")
        csv_row = self_bulk_config(n2)
        time.sleep(STEP_DELAY_SECONDS)

        current_step += 1
        log_progress(current_step, total_steps, "Applying licenses")
        apply_license(n3)

        current_step += 1
        log_progress(current_step, total_steps, "Creating exchange site")
        site_info = create_exchange_site(n3, csv_row=csv_row)
        time.sleep(STEP_DELAY_SECONDS)

        current_step += 1
        log_progress(current_step, total_steps, "Creating exchange resources")
        create_exchange_site_resources(n3, site_info=site_info, csv_row=csv_row)
        time.sleep(STEP_DELAY_SECONDS)

        # Configure DNS force redirect if needed
        configure_dns_force_redirect(csv_row=csv_row)

        current_step += 1
        log_progress(current_step, total_steps, "Moving to production group")
        cp.log('NCX Self Provisioning Complete - All steps successful')
        move_router_to_prod_group(n2)

        time.sleep(COMPLETION_WAIT_SECONDS)

    except Exception as e:
        cp.log(f'FATAL ERROR in main: {sanitize_log(str(e))}')
        cp.log('Provisioning state preserved for recovery')
        raise
