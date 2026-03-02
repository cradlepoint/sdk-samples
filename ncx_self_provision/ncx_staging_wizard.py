"""NCX Staging Group Configuration Wizard.

Web-based configuration tool for setting up NCM staging groups used with
the NCX Self-Provisioning SDK Application. Provides an interactive 6-step
wizard for configuring all parameters, API keys, and bulk configuration
files required for zero-touch device provisioning.

Wizard Steps:
    1. API Keys - NCM v2 (X-CP, X-ECM) and v3 (Bearer Token) credentials
       - Real-time connectivity testing with NCM API
       - Validates credentials before proceeding
    
    2. Required Parameters - Core provisioning settings
       - Staging Group ID and Production Group ID
       - Exchange Network ID
       - Secure Connect License (required, NCX or SASE platform)
       - DNS Configuration: LAN as DNS with local domain OR custom DNS servers
       - Mutually exclusive: LAN as DNS or Custom DNS (not both)
    
    3. Optional Parameters - Add-on features
       - SD-WAN License (optional, must match SC license prefix)
       - HMF License (optional, must match SC license prefix)
       - AI License (optional, must match SC license prefix)
       - Resource creation toggles (LAN subnet, CP host FQDN, wildcard FQDN)
       - CP host and wildcard FQDN checkboxes disabled unless LAN as DNS or
         Custom DNS Servers is enabled (required by NCX API for FQDN resources)
       - Global Force DNS setting (can be overridden per-device in CSV)
    
    4. Global Tags - Site and resource tagging
       - Site tags (comma or semicolon-separated)
       - LAN resource tags (if LAN resource creation enabled)
       - CP host resource tags (if CP host resource creation enabled)
       - Wildcard resource tags (if wildcard resource creation enabled)
       - Tag validation: min 2 chars, lowercase letters and numbers only
       - Tags merged with per-device CSV tags (automatic deduplication)
    
    5. Bulk Configuration - Device-specific configuration files
       - Enable/disable bulk configuration
       - Upload or edit router_grid.csv (device data)
       - Upload or edit config_template.json (configuration template)
       - Built-in file editor with CSV grid view and JSON syntax highlighting
       - Real-time validation: CSV columns vs JSON placeholders
       - Special column detection: id, name, primary_lan_ip, desc, custom1/2, tags, disable_force_dns
       - Template placeholder detection: any non-special column as {{column_name}}
       - Missing 'id' column warning (required for router matching)
    
    6. Review & Apply - Configuration summary and deployment
       - Comprehensive configuration summary
       - Client-side and server-side validation
       - Error display ordered by wizard steps
       - Apply configuration to staging group via NCM API
       - Sets 22 appdata parameters for self-provisioning app
       - Stores API keys as certificates in staging group

Configuration Applied to Staging Group:
    - 22 appdata parameters:
      * staging_group_id, prod_group_id, exchange_network_id
      * secure_connect_lic, sdwan_lic, hmf_lic, ai_lic
      * lan_as_dns, local_domain, primary_dns, secondary_dns
      * create_lan_resource, create_cp_host_resource, create_wildcard_resource
      * site_tags, lan_resource_tags, cp_host_tags, wildcard_tags
      * self_bulk_config, bulk_config_file, config_template_file
      * disable_force_dns (global setting)
    
    - API keys stored as certificates:
      * X-CP-API-ID, X-CP-API-KEY
      * X-ECM-API-ID, X-ECM-API-KEY
      * Bearer Token (NCM v3)

Key Features:
    - Real-time API key connectivity testing
    - License type validation with automatic NCX/SASE prefix matching
    - Tag format validation (min 2 chars, lowercase alphanumeric)
    - IP address validation (no netmask notation allowed)
    - FQDN validation for local domain
    - CSV/JSON file validation (column/placeholder matching)
    - Built-in file editor with grid view for CSV files
    - Collapsible warning messages for bulk configuration
    - Color-coded CSV column analysis (green=config, blue=NCM/NCX, red=missing)
    - Per-device Force DNS override via CSV disable_force_dns column
    - Comprehensive error reporting ordered by wizard steps
    - Configuration summary before applying
    - Success confirmation with next steps

Supported License Types:
    Secure Connect (required):
    - NCX: NCX-SC, NCX-SCL, NCX-SCM, NCX-SCIOT, NCX-SCS, NCX-SC-TEMP
    - SASE: NCS-SC, NCS-SC-TRIAL
    
    SD-WAN (optional):
    - NCX: NCX-SDWAN, NCX-SDWANL, NCX-SDWANM, NCX-SDWANMICRO, NCX-SDWANS, NCX-SDWAN-TRIAL
    - SASE: NCS-SDWAN, NCS-SDWAN-TRIAL
    
    HMF (optional):
    - NCX: NCX-HMF, NCX-HMF-L, NCX-HMF-M, NCX-HMF-MS, NCX-HMF-SS, NCX-HMF-TRIAL
    - SASE: NCS-HMF, NCS-HMF-TRIAL
    
    AI (optional):
    - NCX: NCX-AI, NCX-AI-TRIAL
    - SASE: NCS-AI, NCS-AI-TRIAL

CSV Column Types:
    Special columns (processed by app logic, not template placeholders):
    - id: Router ID for matching (required)
    - name: System name (optional, cached for site creation, fallback to device)
    - primary_lan_ip: Primary LAN IP (optional, cached for site/resource, fallback to device)
    - desc: Description (optional, injected into device config)
    - custom1, custom2: NCM custom fields (optional)
    - site_tags: Per-device site tags (optional, semicolon-separated)
    - lan_resource_tags: Per-device LAN resource tags (optional)
    - cp_host_tags: Per-device CP host resource tags (optional)
    - wildcard_resource_tags: Per-device wildcard resource tags (optional)
    - disable_force_dns: Override global Force DNS (optional, 'true' to disable)
    
    Template placeholder columns:
    - Any non-special column can be used as {{column_name}} in config_template.json

Usage:
    python ncx_staging_wizard.py
    # Open browser to http://localhost:8000
    # Complete 6-step wizard
    # Apply configuration to staging group
    # Build SDK package: python make.py build ncx_self_provision
    # Upload to NCM and assign to staging group

Security:
    - NEVER deploy this file to routers
    - NEVER include in SDK package
    - Contains sensitive API credentials during runtime
    - Web interface files (index.html, static/) also excluded from SDK
    - Only ncx_self_provision.py and dependencies deployed to devices

Files Deployed to Devices:
    - ncx_self_provision.py (main application)
    - cp.py (router library)
    - ncm.py (NCM API library)
    - config_template.json (if bulk config enabled)
    - router_grid.csv (if bulk config enabled)
    - start.sh, package.ini (SDK metadata)

Files Never Deployed (Local Use Only):
    - ncx_staging_wizard.py (this file)
    - index.html (wizard web interface)
    - static/ (wizard CSS/JS/assets)
    - README.md (documentation)

Port Configuration:
    - Default port: 8000
    - Automatically tries alternative ports if 8000 is in use
    - Web interface accessible at http://localhost:<port>
"""

import http.server
import socketserver
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
import time
import ncm

PORT = 8000

# Valid license types by category
VALID_LICENSES = {
    'Secure Connect': [
        'NCX-SC', 'NCX-SCL', 'NCX-SCM', 'NCX-SCIOT', 'NCX-SCS', 'NCX-SC-TEMP',
        'NCS-SC', 'NCS-SC-TRIAL'
    ],
    'SD-WAN': [
        'NCX-SDWAN', 'NCX-SDWANL', 'NCX-SDWANM', 'NCX-SDWANMICRO',
        'NCX-SDWANS', 'NCX-SDWAN-TRIAL', 'NCS-SDWAN', 'NCS-SDWAN-TRIAL'
    ],
    'HMF': [
        'NCX-HMF', 'NCX-HMF-L', 'NCX-HMF-M', 'NCX-HMF-MS', 'NCX-HMF-SS',
        'NCX-HMF-TRIAL', 'NCS-HMF', 'NCS-HMF-TRIAL'
    ],
    'AI': [
        'NCX-AI', 'NCX-AI-TRIAL', 'NCS-AI', 'NCS-AI-TRIAL'
    ]
}


def validate_api_keys_connectivity(api_keys: Dict[str, str]) -> tuple:
    """Validate API keys by testing connectivity."""
    try:
        # Test v2 API keys with get_accounts()
        n2 = ncm.NcmClientv2(api_keys=api_keys)
        accounts = n2.get_accounts()
        
        if not accounts or (isinstance(accounts, str) and accounts.startswith('ERROR')):
            return False, "Error validating NCM v2 API keys (X-CP and X-ECM)"
        
        # Test v3 API key (Bearer Token) with get_exchange_sites()
        n3 = ncm.NcmClientv3(api_key=api_keys['Bearer Token'])
        sites = n3.get_exchange_sites()
        
        if isinstance(sites, str) and sites.startswith('ERROR'):
            return False, "Error validating Bearer Token"
        
        return True, "All API keys validated successfully"
        
    except Exception as e:
        return False, f"API key validation error: {str(e)}"


def validate_api_keys(api_keys: Dict[str, str]) -> list:
    """Validate API keys and return list of errors (consolidated)."""
    required_keys = [
        'X-CP-API-ID', 'X-CP-API-KEY',
        'X-ECM-API-ID', 'X-ECM-API-KEY',
        'Bearer Token'
    ]
    
    missing_keys = [key for key in required_keys if key not in api_keys or not api_keys[key]]
    
    if missing_keys:
        return [f"Missing API keys: {', '.join(missing_keys)}"]
    return []


def validate_tags(tags: str) -> tuple:
    """Validate tag format."""
    if not tags or tags == '':
        return True, "Valid"
    
    # Split by comma or semicolon
    tag_list = [t.strip() for t in tags.replace(';', ',').split(',')]
    for tag in tag_list:
        if len(tag) < 2:
            return False, f"Tag '{tag}' must be at least 2 characters long"
        if not all(c.islower() or c.isdigit() for c in tag):
            return False, f"Tag '{tag}' must contain only lowercase letters and numbers"
    return True, "Valid"


def validate_ip_address(ip: str) -> bool:
    """Validate IP address format (no netmask allowed)."""
    if not ip or ip.strip() == '':
        return True
    
    # Check for netmask notation
    if '/' in ip:
        return False
    
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False
    
    return True


def validate_fqdn(domain: str) -> tuple:
    """Validate FQDN format."""
    if not domain:
        return True, "Valid"
    
    for char in domain:
        if not (char.isalnum() or char in '.-'):
            return False, f"Domain contains invalid character '{char}'"
    
    if '.' in domain:
        tld = domain.split('.')[-1]
        if not tld.isalpha():
            return False, f"Domain has invalid TLD '{tld}'"
    return True, "Valid"


def validate_license(license_value: str, license_type: str) -> tuple:
    """Validate license type."""
    if not license_value:
        return True, "Valid"
    
    valid_for_type = VALID_LICENSES.get(license_type, [])
    if license_value not in valid_for_type:
        return False, f"Invalid {license_type} license"
    return True, "Valid"


def validate_configuration(data: Dict[str, Any]) -> tuple:
    """Validate entire configuration."""
    errors = []
    
    # API keys (first)
    api_keys = data.get('api_keys', {})
    api_key_errors = validate_api_keys(api_keys)
    errors.extend(api_key_errors)
    
    # Required fields
    if not data.get('staging_group_id'):
        errors.append("Staging Group ID is required")
    elif not str(data['staging_group_id']).isdigit():
        errors.append("Staging Group ID must be numeric")
    
    if not data.get('prod_group_id'):
        errors.append("Production Group ID is required")
    elif not str(data['prod_group_id']).isdigit():
        errors.append("Production Group ID must be numeric")
    
    if data.get('staging_group_id') == data.get('prod_group_id'):
        errors.append("Staging and Production Group IDs must be different")
    
    if not data.get('exchange_network_id'):
        errors.append("Exchange Network ID is required")
    
    if not data.get('secure_connect_lic'):
        errors.append("Secure Connect License is required")
    
    if data.get('lan_as_dns') and not data.get('local_domain'):
        errors.append("Local Domain is required when LAN as DNS is enabled")
    
    if data.get('custom_dns_enabled') and not data.get('primary_dns'):
        errors.append("Primary DNS Server is required when Custom DNS is enabled")
    
    # Validate IP addresses for custom DNS
    if data.get('primary_dns'):
        if not validate_ip_address(data['primary_dns']):
            errors.append("Primary DNS Server must be a valid IP address")
    
    if data.get('secondary_dns'):
        if not validate_ip_address(data['secondary_dns']):
            errors.append("Secondary DNS Server must be a valid IP address")
    
    # FQDN
    if data.get('local_domain'):
        valid, msg = validate_fqdn(data['local_domain'])
        if not valid:
            errors.append(msg)
    
    # Licenses
    valid, msg = validate_license(data.get('secure_connect_lic'), 'Secure Connect')
    if not valid:
        errors.append(msg)
    
    # Validate license prefix consistency
    sc_lic = data.get('secure_connect_lic', '')
    if sc_lic:
        prefix = 'NCX' if sc_lic.startswith('NCX') else 'NCS'
        
        if data.get('sdwan_lic'):
            if not data['sdwan_lic'].startswith(prefix):
                errors.append(f"SD-WAN license must use {prefix} prefix to match Secure Connect license")
            valid, msg = validate_license(data['sdwan_lic'], 'SD-WAN')
            if not valid:
                errors.append(msg)
        
        if data.get('hmf_lic'):
            if not data['hmf_lic'].startswith(prefix):
                errors.append(f"HMF license must use {prefix} prefix to match Secure Connect license")
            valid, msg = validate_license(data['hmf_lic'], 'HMF')
            if not valid:
                errors.append(msg)
        
        if data.get('ai_lic'):
            if not data['ai_lic'].startswith(prefix):
                errors.append(f"AI license must use {prefix} prefix to match Secure Connect license")
            valid, msg = validate_license(data['ai_lic'], 'AI')
            if not valid:
                errors.append(msg)
    
    # Tags
    for tag_field in ['site_tags', 'lan_resource_tags',
                      'cp_host_tags', 'wildcard_tags']:
        if data.get(tag_field):
            valid, msg = validate_tags(data[tag_field])
            if not valid:
                errors.append(f"{tag_field}: {msg}")
    
    # Validate bulk config files if enabled
    if data.get('self_bulk_config'):
        bulk_file = data.get('bulk_config_file', 'router_grid.csv')
        template_file = data.get('config_template_file', 'config_template.json')
        
        if not bulk_file:
            errors.append("Bulk Config File is required when bulk configuration is enabled")
        if not template_file:
            errors.append("Config Template File is required when bulk configuration is enabled")
    
    if errors:
        return False, errors
    return True, []


def build_appdata_config(config: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Build appdata configuration with 22 parameters."""
    appdata_items = [
        {"name": "staging_group_id", "value": str(config['staging_group_id'])},
        {"name": "prod_group_id", "value": str(config['prod_group_id'])},
        {"name": "exchange_network_id", "value": config['exchange_network_id']},
        {"name": "secure_connect_lic", "value": config['secure_connect_lic']},
        {"name": "local_domain", "value": config.get('local_domain', '')},
        {"name": "lan_as_dns", "value": str(config.get('lan_as_dns', False))},
        {"name": "primary_dns", "value": config.get('primary_dns', '')},
        {"name": "secondary_dns", "value": config.get('secondary_dns', '')},
        {"name": "create_lan_resource", "value": str(config.get('create_lan_resource', False))},
        {"name": "create_cp_host_resource", "value": str(config.get('create_cp_host_resource', False))},
        {"name": "create_wildcard_resource", "value": str(config.get('create_wildcard_resource', False))},
        {"name": "sdwan_lic", "value": config.get('sdwan_lic', '')},
        {"name": "hmf_lic", "value": config.get('hmf_lic', '')},
        {"name": "ai_lic", "value": config.get('ai_lic', '')},
        {"name": "self_bulk_config", "value": str(config.get('self_bulk_config', False))},
        {"name": "bulk_config_file", "value": config.get('bulk_config_file', 'router_grid.csv')},
        {"name": "config_template_file", "value": config.get('config_template_file', 'config_template.json')},
        {"name": "site_tags", "value": config.get('site_tags', '')},
        {"name": "lan_resource_tags", "value": config.get('lan_resource_tags', '')},
        {"name": "cp_host_tags", "value": config.get('cp_host_tags', '')},
        {"name": "wildcard_tags", "value": config.get('wildcard_tags', '')},
        {"name": "disable_force_dns", "value": str(config.get('disable_force_dns', False))},
    ]
    
    appdata_dict = {}
    for idx, item in enumerate(appdata_items):
        item_id = f"{idx:08x}-8e48-3903-ad8c-538bad254b4c"
        appdata_dict[item_id] = {
            "name": item["name"],
            "value": item["value"],
            "_id_": item_id
        }
    
    return appdata_dict


def apply_configuration(data: Dict[str, Any]) -> tuple:
    """Apply configuration to staging group."""
    try:
        # Validate
        valid, errors = validate_configuration(data)
        if not valid:
            return False, {'errors': errors}
        
        # Initialize NCM client
        api_keys = data['api_keys']
        n2 = ncm.NcmClientv2(api_keys=api_keys)
        
        # Build configuration
        appdata = build_appdata_config(data)
        config_json = {
            "configuration": [
                {
                    "system": {
                        "sdk": {
                            "appdata": appdata
                        }
                    }
                },
                []
            ]
        }
        
        # Set API keys
        n2.set_ncm_api_keys_by_group(
            group_id=data['staging_group_id'],
            x_ecm_api_id=api_keys['X-ECM-API-ID'],
            x_ecm_api_key=api_keys['X-ECM-API-KEY'],
            x_cp_api_id=api_keys['X-CP-API-ID'],
            x_cp_api_key=api_keys['X-CP-API-KEY'],
            bearer_token=api_keys['Bearer Token']
        )
        
        time.sleep(1)
        
        # Apply configuration
        n2.patch_group_configuration(
            group_id=data['staging_group_id'],
            config_json=config_json
        )
        
        return True, {'message': 'Configuration applied successfully'}
        
    except Exception as e:
        return False, {'error': str(e)}


class ConfigurationHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with API endpoints."""
    
    def end_headers(self):
        """Add CORS and cache headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/api/licenses':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(VALID_LICENSES).encode())
        elif self.path == '/api/check-default-files':
            script_dir = Path(__file__).parent.absolute()
            csv_path = script_dir / 'router_grid.csv'
            json_path = script_dir / 'config_template.json'
            
            result = {
                'csv_exists': csv_path.exists(),
                'json_exists': json_path.exists()
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        elif self.path == '/api/validate-default-files':
            script_dir = Path(__file__).parent.absolute()
            csv_path = script_dir / 'router_grid.csv'
            json_path = script_dir / 'config_template.json'
            
            try:
                import csv
                import re
                
                errors = []
                csv_columns = []
                placeholders = set()
                
                # Validate CSV
                if not csv_path.exists():
                    errors.append('router_grid.csv not found in working directory')
                else:
                    try:
                        with open(csv_path, 'r', encoding='utf-8-sig') as f:
                            csv_content = f.read()
                            lines = csv_content.strip().splitlines()
                            
                            if lines:
                                csv_reader = csv.DictReader(lines)
                                csv_columns = list(csv_reader.fieldnames or [])
                                
                                if 'id' not in csv_columns:
                                    errors.append(f'CSV must contain "id" column. Found: {", ".join(csv_columns)}')
                                if len(csv_columns) < 2:
                                    errors.append('CSV must contain at least 2 columns (id + 1 other)')
                            else:
                                errors.append('CSV file is empty')
                    except Exception as e:
                        errors.append(f'Invalid CSV format: {str(e)}')
                
                # Validate JSON
                if not json_path.exists():
                    errors.append('config_template.json not found in working directory')
                else:
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            template = json.load(f)
                            
                            if not isinstance(template, list) or len(template) != 2:
                                errors.append('JSON must be array with 2 elements: [config_object, []]')
                            elif not isinstance(template[0], dict):
                                errors.append('First element must be a configuration object')
                            elif not isinstance(template[1], list):
                                errors.append('Second element must be an empty array')
                            else:
                                # Find placeholders
                                json_str = json.dumps(template[0])
                                placeholders = set(re.findall(r'\{\{(\w+)\}\}', json_str))
                                
                                if not placeholders:
                                    errors.append('JSON template must contain at least one {{placeholder}}')
                                elif csv_columns:
                                    # Check if placeholders match CSV columns
                                    missing = placeholders - set(csv_columns)
                                    if missing:
                                        errors.append(f'Template placeholders not in CSV: {", ".join(missing)}')
                    except json.JSONDecodeError:
                        errors.append('Invalid JSON format')
                    except Exception as e:
                        errors.append(f'JSON validation error: {str(e)}')
                
                if errors:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'errors': errors}).encode())
                else:
                    # Check if disable_force_dns column has any true values
                    has_disable_force_dns_true = False
                    if 'disable_force_dns' in csv_columns and csv_path.exists():
                        with open(csv_path, 'r', encoding='utf-8-sig') as f:
                            csv_reader = csv.reader(f)
                            next(csv_reader)  # Skip header
                            disable_col_idx = csv_columns.index('disable_force_dns')
                            for row in csv_reader:
                                if len(row) > disable_col_idx:
                                    value = row[disable_col_idx].strip().lower()
                                    if value == 'true':
                                        has_disable_force_dns_true = True
                                        break
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': True,
                        'csv_columns': csv_columns,
                        'csv_count': len(csv_columns),
                        'json_placeholders': sorted(list(placeholders)),
                        'json_count': len(placeholders),
                        'special_columns': {
                            'desc': 'desc' in csv_columns,
                            'custom1': 'custom1' in csv_columns,
                            'custom2': 'custom2' in csv_columns,
                            'site_tags': 'site_tags' in csv_columns,
                            'lan_resource_tags': 'lan_resource_tags' in csv_columns,
                            'cp_host_tags': 'cp_host_tags' in csv_columns,
                            'wildcard_resource_tags': 'wildcard_resource_tags' in csv_columns,
                            'disable_force_dns': 'disable_force_dns' in csv_columns
                        },
                        'has_disable_force_dns_true': has_disable_force_dns_true
                    }).encode())
            
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'errors': [f'Server error: {str(e)}']}).encode())
        
        elif self.path == '/api/get-files':
            script_dir = Path(__file__).parent.absolute()
            csv_path = script_dir / 'router_grid.csv'
            json_path = script_dir / 'config_template.json'
            
            try:
                csv_content = ''
                json_content = ''
                
                if csv_path.exists():
                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        csv_content = f.read()
                
                if json_path.exists():
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_content = f.read()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'csv_content': csv_content,
                    'json_content': json_content
                }).encode())
            
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Error loading files: {str(e)}'}).encode())
        
        else:
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/validate-api-keys':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            api_keys = data.get('api_keys', {})
            valid, message = validate_api_keys_connectivity(api_keys)
            
            if valid:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'valid': True, 'message': message}
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'valid': False, 'error': message}
                self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/validate':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            valid, result = validate_configuration(data)
            
            if valid:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'valid': True, 'message': 'Validation passed'}
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'valid': False, 'errors': result}
                self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/configure':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            success, result = apply_configuration(data)
            
            if success:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': True, 'message': result['message']}
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': result.get('error', 'Unknown error')}
                if 'errors' in result:
                    response['errors'] = result['errors']
                self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/upload':
            content_type = self.headers['Content-Type']
            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.end_headers()
                return
            
            # Check file size (1MB limit)
            content_length = int(self.headers.get('Content-Length', 0))
            max_size = 1024 * 1024  # 1MB
            if content_length > max_size:
                self.send_response(413)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'File size exceeds 1MB limit'}).encode())
                return
            
            import cgi
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            if 'file' not in form:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'No file uploaded'}).encode())
                return
            
            file_item = form['file']
            if not file_item.filename:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'No file selected'}).encode())
                return
            
            # Save to working directory
            script_dir = Path(__file__).parent.absolute()
            file_path = script_dir / file_item.filename
            
            # Check if file exists
            if file_path.exists():
                # Get overwrite parameter
                overwrite = form.getvalue('overwrite', 'false')
                if overwrite != 'true':
                    self.send_response(409)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'exists': True, 'filename': file_item.filename}
                    self.wfile.write(json.dumps(response).encode())
                    return
            
            with open(file_path, 'wb') as f:
                f.write(file_item.file.read())
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': True, 'filename': file_item.filename}
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/api/validate-files':
            content_type = self.headers['Content-Type']
            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.end_headers()
                return
            
            try:
                import csv
                import re
                
                # Parse multipart data
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                
                # Get boundary
                boundary = content_type.split('boundary=')[1]
                if boundary.startswith('"'):
                    boundary = boundary.strip('"')
                boundary = boundary.encode()
                
                parts = body.split(b'--' + boundary)
                
                files = {}
                for part in parts:
                    if b'Content-Disposition' in part and b'filename=' in part:
                        # Find the double CRLF that separates headers from content
                        header_end = part.find(b'\r\n\r\n')
                        if header_end == -1:
                            continue
                        
                        headers = part[:header_end].decode('utf-8', errors='ignore')
                        content = part[header_end+4:]
                        
                        # Remove trailing CRLF
                        if content.endswith(b'\r\n'):
                            content = content[:-2]
                        
                        # Extract field name and filename
                        name_match = re.search(r'name="([^"]+)"', headers)
                        filename_match = re.search(r'filename="([^"]+)"', headers)
                        
                        if name_match and filename_match:
                            field_name = name_match.group(1)
                            filename = filename_match.group(1)
                            files[field_name] = {'filename': filename, 'content': content}
                
                errors = []
                csv_columns = []
                placeholders = set()
                
                # Validate CSV
                if 'csv_file' not in files:
                    errors.append('CSV file is required')
                else:
                    csv_file = files['csv_file']
                    if not csv_file['filename'].endswith('.csv'):
                        errors.append('CSV file must have .csv extension')
                    else:
                        try:
                            csv_content = csv_file['content'].decode('utf-8-sig')  # utf-8-sig removes BOM
                            lines = csv_content.strip().splitlines()
                            
                            if lines:
                                csv_reader = csv.DictReader(lines)
                                csv_columns = list(csv_reader.fieldnames or [])
                                
                                if 'id' not in csv_columns:
                                    errors.append(f'CSV must contain "id" column. Found: {", ".join(csv_columns)}')
                                if len(csv_columns) < 2:
                                    errors.append('CSV must contain at least 2 columns (id + 1 other)')
                            else:
                                errors.append('CSV file is empty')
                        except Exception as e:
                            errors.append(f'Invalid CSV format: {str(e)}')
                
                # Validate JSON
                if 'json_file' not in files:
                    errors.append('JSON file is required')
                else:
                    json_file = files['json_file']
                    if not json_file['filename'].endswith('.json'):
                        errors.append('JSON file must have .json extension')
                    else:
                        try:
                            json_content = json_file['content'].decode('utf-8')
                            template = json.loads(json_content)
                            
                            if not isinstance(template, list) or len(template) != 2:
                                errors.append('JSON must be array with 2 elements: [config_object, []]')
                            elif not isinstance(template[0], dict):
                                errors.append('First element must be a configuration object')
                            elif not isinstance(template[1], list):
                                errors.append('Second element must be an empty array')
                            else:
                                # Find placeholders
                                json_str = json.dumps(template[0])
                                placeholders = set(re.findall(r'\{\{(\w+)\}\}', json_str))
                                
                                if not placeholders:
                                    errors.append('JSON template must contain at least one {{placeholder}}')
                                elif csv_columns:
                                    # Check if placeholders match CSV columns
                                    missing = placeholders - set(csv_columns)
                                    if missing:
                                        errors.append(f'Template placeholders not in CSV: {", ".join(missing)}')
                        except json.JSONDecodeError:
                            errors.append('Invalid JSON format')
                        except Exception as e:
                            errors.append(f'JSON validation error: {str(e)}')
                
                if errors:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'errors': errors}).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': True,
                        'csv_columns': csv_columns,
                        'csv_count': len(csv_columns),
                        'json_placeholders': sorted(list(placeholders)),
                        'json_count': len(placeholders),
                        'special_columns': {
                            'desc': 'desc' in csv_columns,
                            'custom1': 'custom1' in csv_columns,
                            'custom2': 'custom2' in csv_columns,
                            'site_tags': 'site_tags' in csv_columns,
                            'lan_resource_tags': 'lan_resource_tags' in csv_columns,
                            'cp_host_tags': 'cp_host_tags' in csv_columns,
                            'wildcard_resource_tags': 'wildcard_resource_tags' in csv_columns,
                            'disable_force_dns': 'disable_force_dns' in csv_columns
                        }
                    }).encode())
            
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'errors': [f'Server error: {str(e)}']}).encode())
        
        elif self.path == '/api/save-files':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            script_dir = Path(__file__).parent.absolute()
            csv_path = script_dir / 'router_grid.csv'
            json_path = script_dir / 'config_template.json'
            
            try:
                # Save CSV file
                with open(csv_path, 'w', encoding='utf-8') as f:
                    f.write(data.get('csv_content', ''))
                
                # Save JSON file
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(data.get('json_content', ''))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'message': 'Files saved successfully'}).encode())
            
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Error saving files: {str(e)}'}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()


def main():
    """Start the HTTP server."""
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    if not (script_dir / 'index.html').exists():
        print(f"Warning: index.html not found in {script_dir}")
        print("The configuration interface may not be available.")
    
    handler = ConfigurationHandler
    
    try:
        with socketserver.TCPServer(("", PORT), handler) as httpd:
            print("=" * 60)
            print("NCX Staging Configuration Web Server")
            print("=" * 60)
            print(f"Server running at: http://0.0.0.0:{PORT}")
            print(f"Configuration UI: http://0.0.0.0:{PORT}")
            print(f"Serving directory: {script_dir}")
            print(f"\nPress Ctrl+C to stop the server")
            print("=" * 60)
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:
            print(f"\nError: Port {PORT} is already in use.")
            print(f"Please stop the process using port {PORT} or change the PORT variable.")
        else:
            print(f"\nError starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
