import ncm
import time

api_keys = {
    "X-CP-API-ID": "5d4b40cd",
    "X-CP-API-KEY": "4c1108d8b2da465588bb87bfe0cbbd2c",
    "X-ECM-API-ID": "1580cfa7-b720-46f1-bbf9-671857fee0e8",
    "X-ECM-API-KEY": "b952b0e117ea8c3dc69fe6152e60220291c19b65",
    "bearer_token": "TR1p9dUA3HclW5rRUAmIFKvAVcuzxyib"
}

n2 = ncm.NcmClientv2(api_keys=api_keys)

n2.set_ncm_api_keys_by_group(group_id=554956, group_name=None, x_ecm_api_id=api_keys['X-ECM-API-ID'], x_ecm_api_key=api_keys['X-ECM-API-KEY'], 
                             x_cp_api_id=api_keys['X-CP-API-ID'], x_cp_api_key=api_keys['X-CP-API-KEY'], bearer_token=api_keys['bearer_token'])

config_json = {
    "configuration": [
        {
            "system": {
                "sdk": {
                    "appdata": {
                        "00000000-8e48-3903-ad8c-538bad254b4c": {
                            "name": "prod_group_id",
                            "value": '554967',
                            "_id_": "00000000-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000001-8e48-3903-ad8c-538bad254b4c": {
                            "name": "exchange_network_id",
                            "value": '01GQFWVHYDEWNNCJGBXXJFRHMF',
                            "_id_": "00000001-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000002-8e48-3903-ad8c-538bad254b4c": {
                            "name": "lan_as_dns",
                            "value": 'True',
                            "_id_": "00000002-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000003-8e48-3903-ad8c-538bad254b4c": {
                            "name": "local_domain",
                            "value": 'ncx.net',
                            "_id_": "00000003-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000004-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_lan_resource",
                            "value": 'True',
                            "_id_": "00000004-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000005-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_cp_host_resource",
                            "value": 'True',
                            "_id_": "00000005-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000006-8e48-3903-ad8c-538bad254b4c": {
                            "name": "create_wildcard_resource",
                            "value": 'True',
                            "_id_": "00000006-8e48-3903-ad8c-538bad254b4c"
                        },
                        "00000007-8e48-3903-ad8c-538bad254b4c": {
                            "name": "secure_connect_lic",
                            "value": 'NCX-SCIOT',
                            "_id_": "00000007-8e48-3903-ad8c-538bad254b4c"
                        }
                    }
                }
            }
        },
        []
    ]
}

time.sleep(1)

n2.patch_group_configuration(group_id='554956', config_json=config_json)
