import ncm
import time

# Provide APIv2 keys and APIv3 Bearer Token from NCM
api_keys = {
    "X-CP-API-ID": "",
    "X-CP-API-KEY": "",
    "X-ECM-API-ID": "",
    "X-ECM-API-KEY": "",
    "Bearer Token": ""
}

# Provide staging group id from NCM
staging_group_id = '123456'

# Initialize APIv2 client
n2 = ncm.NcmClientv2(api_keys=api_keys)

# Set APIv2 keys and APIv3 Bearer Token to staging group by group id
n2.set_ncm_api_keys_by_group(group_id=staging_group_id, x_ecm_api_id=api_keys['X-ECM-API-ID'], x_ecm_api_key=api_keys['X-ECM-API-KEY'], 
                             x_cp_api_id=api_keys['X-CP-API-ID'], x_cp_api_key=api_keys['X-CP-API-KEY'], bearer_token=api_keys['Bearer Token'])


# Provide values to use as part of config_json. production group id, exchange network id, etc. examples below
prod_group_id = '654321' # Production group id as string. Site will be moved to this group after provisioning
exchange_network_id = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' # Exchange network id. Site will be added to this network
lan_as_dns = 'True' # 'True' if LAN as DNS is to be enabled for the site
local_domain = 'ncx.net' # Domain suffix for site. Will be prepended by the site name (system id)
create_lan_resource = 'True' # 'True' if an ip subnet resource is to be created for Primary LAN IP subnet
create_cp_host_resource = 'True' # 'True' if an FQDN resource is to be created for the default 'cp' hostname. Will be appended by the local domain
create_wildcard_resource = 'True' # 'True' if a wildcard FQDN resource is to be created for the site
secure_connect_lic = 'NCX-SCIOT' # Secure Connect license typeto apply to the router. Obtain from APIv3 'regrades' endpoint docs
sdwan_lic = 'None' # SD-WAN license type to apply to the router. Obtain from APIv3 'regrades' endpoint docs or 'None' if not applicable
hmf_lic = 'None' # HMF license type to apply to the router. Obtain from APIv3 'regrades' endpoint docs or 'None' if not applicable

# Build config_json to apply to staging group
config_json = {
    "configuration": [
        {
            "system": {
                "sdk": {
                    "appdata": {
                        "00000000-8e48-3903-ad8c-538bad254b4c": {
                            "name": "prod_group_id",
                            "value": f'{prod_group_id}',
                            "_id_": "00000000-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000001-8e48-3903-ad8c-538bad254b4c": {
                            "name": "exchange_network_id",
                            "value": f'{exchange_network_id}',
                            "_id_": "00000001-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000002-8e48-3903-ad8c-538bad254b4c": {
                            "name": "lan_as_dns",
                            "value": f'{lan_as_dns}',
                            "_id_": "00000002-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000003-8e48-3903-ad8c-538bad254b4c": {
                            "name": "local_domain",
                            "value": f'{local_domain}',
                            "_id_": "00000003-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000004-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_lan_resource",
                            "value": f'{create_lan_resource}',
                            "_id_": "00000004-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000005-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_cp_host_resource",
                            "value": f'{create_cp_host_resource}',
                            "_id_": "00000005-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000006-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_wildcard_resource",
                            "value": f'{create_wildcard_resource}',
                            "_id_": "00000006-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000007-8e48-3903-ad8c-538bad254b4c": {
                            "name": "secure_connect_lic",
                            "value": f'{secure_connect_lic}',
                            "_id_": "00000007-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000008-8e48-3903-ad8c-538bad254b4c": {
                            "name": "sdwan_lic",
                            "value": f'{sdwan_lic}',
                            "_id_": "00000008-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000009-8e48-3903-ad8c-538bad254b4c": {
                            "name": "hmf_lic",
                            "value": f'{hmf_lic}',
                            "_id_": "00000009-8e48-3903-ad8c-538bad254b4c"
                        }
                    }
                }
            }
        },
        []
    ]
}

# Wait for 1 second to ensure config_json is built
time.sleep(1)

# Apply config_json to staging group
n2.patch_group_configuration(group_id=staging_group_id, config_json=config_json)
