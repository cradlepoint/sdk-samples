# NCX Self-Provisioning SDK Application

This SDK application enables Ericsson routers to automatically self-provision themselves to an NCX or SASE network when moved into a staging group. The application handles license application, exchange site creation, resource provisioning, and group re-assignment automatically.

## Overview

The NCX Self-Provisioning application consists of two main components:

1. **`ncx_staging.py`** - Configuration script that sets up the staging group with required API keys and deployment parameters
2. **`ncx_self_provision.py`** - Main application that runs on each device to perform the self-provisioning process

## Deployment Process

### Step 1: Prepare Your Deployment Configuration

Before deploying, you need to update the `ncx_staging.py` script with your specific deployment values:

1. **API Credentials** - Update the API keys section with your NCM API credentials:
   ```python
   api_keys = {
       "X-CP-API-ID": "your_cp_api_id",
       "X-CP-API-KEY": "your_cp_api_key", 
       "X-ECM-API-ID": "your_ecm_api_id",
       "X-ECM-API-KEY": "your_ecm_api_key",
       "Bearer Token": "your_bearer_token"
   }
   ```

2. **Group Configuration** - Set your staging and production group IDs:
   ```python
   staging_group_id = 'staging_group_id'
   prod_group_id = 'prod_group_id'
   ```

3. **Exchange Network Settings** - Configure your NCX/SASE network settings:
   ```python
   exchange_network_id = 'exchange_network_id'
   ```

4. **Site Creation Settings** - Configure site settings:
   ```python
   lan_as_dns = 'True'  # or 'False'
   local_domain = 'yourdomain.com'
   ```

5. **Resource Creation Settings** - Configure which resources to create:
   ```python
   create_lan_resource = 'True'      # Create IP subnet resource for LAN
   create_cp_host_resource = 'True'  # Create FQDN resource for router hostname
   create_wildcard_resource = 'True' # Create wildcard FQDN resource
   ```

6. **License Configuration** - Set the Secure Connect license type:
   ```python
   secure_connect_lic = 'NCX-SCIOT'  # Your license type
   ```

### Step 2: Configure the Staging Group

Run the staging configuration script to apply the required configuration to your staging group:

```bash
python ncx_staging.py
```

This script will:
- Set the NCM API keys and Bearer token on the staging group
- Apply the deployment configuration parameters as application data

### Step 3: Deploy the SDK Application

1. Package the SDK application:
```bash
python make.py build
```

2. Upload the application to NCM and assign it to your staging group

3. The application will automatically install and run on all devices in the staging group

### Step 4: Self-Provisioning Process

When devices are moved into the staging group, they will automatically:

1. **Wait for System Readiness** - Wait for router uptime and WAN connection
2. **Build API Keys** - Retrieve and decrypt API credentials from device certificates
3. **Apply License** - Apply the configured Secure Connect license to the router
4. **Create Exchange Site** - Create an exchange site in the specified network
5. **Create Resources** - Create configured resources (LAN subnet, FQDN, wildcard)
6. **Move to Production group** - Move the router to the production group

## File Descriptions

*   **`ncx_self_provision.py`**: The main self-provisioning application that runs on each device
*   **`ncx_staging.py`**: Configuration script to set up the staging group with deployment parameters
*   **`cp.py`**: Helper library for router interaction and NCOS communication
*   **`ncm.py`**: NCM API client library for v2 and v3 API interactions
*   **`start.sh`**: Execution script that starts the application on the router
*   **`package.ini`**: Application configuration file
*   **`readme.md`**: This documentation file

## Configuration Parameters

The following parameters are configured via the staging script and used by the self-provisioning application:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `prod_group_id` | Production group ID where devices will be moved after provisioning | `'654321'` |
| `exchange_network_id` | NCX/SASE exchange network ID | `'ABCDEFGHIJKLMNOPQRSTUVWXYZ'` |
| `lan_as_dns` | Enable LAN as DNS for the exchange site | `'True'` or `'False'` |
| `local_domain` | Domain suffix for the site | `'ncx.net'` |
| `create_lan_resource` | Create IP subnet resource for LAN | `'True'` or `'False'` |
| `create_cp_host_resource` | Create FQDN resource for router hostname | `'True'` or `'False'` |
| `create_wildcard_resource` | Create wildcard FQDN resource | `'True'` or `'False'` |
| `secure_connect_lic` | Secure Connect license type to apply | `'NCX-SCIOT'` |

## Prerequisites

Before deploying this application, ensure you have:

1. **NCM API Access** - Valid API credentials for both v2 and v3 APIs
2. **Staging Group** - A group in NCM designated for staging devices
3. **Production Group** - A group in NCM where provisioned devices will be moved
4. **Exchange Network** - An NCX/SASE exchange network configured in NCM
5. **Secure Connect License** - Valid license type for your deployment
6. **Device Certificates** - API keys stored as certificates on the devices

## Troubleshooting

### Common Issues

1. **API Key Decryption Failures** - Ensure API keys are properly stored as certificates on the devices
2. **Network Connectivity** - Verify devices have WAN connectivity before provisioning
3. **License Application Failures** - Check that the license type is valid and available
4. **Group Assignment Failures** - Verify production group ID is correct and accessible

### Logs

The application provides detailed logging throughout the provisioning process. Check the device logs in NCM for:
- API key retrieval and decryption status
- License application results
- Exchange site creation details
- Resource creation status
- Group assignment confirmation

## Security Considerations

- API credentials are stored encrypted on the devices
- The application only runs when devices are in the staging group
- All API communications use secure HTTPS connections
- Application data is cleared after provisioning completion
