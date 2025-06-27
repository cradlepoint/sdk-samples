import cp
import ncm
from icecream import ic

def build_keys():
    certs = cp.get('config/certmgmt/certs')
    api_keys = {}
    try:
        for cert in certs:
            if cert['name'] == 'X-CP-API-ID':
                api_keys['X-CP-API-ID'] = cp.decrypt(cert['key'])
            elif cert['name'] == 'X-CP-API-KEY':
                api_keys['X-CP-API-KEY'] = cp.decrypt(cert['key'])
            elif cert['name'] == 'X-ECM-API-ID':
                api_keys['X-ECM-API-ID'] = cp.decrypt(cert['key'])
            elif cert['name'] == 'X-ECM-API-KEY':
                api_keys['X-ECM-API-KEY'] = cp.decrypt(cert['key'])
            elif cert['name'] == 'Bearer Token':
                api_keys['Bearer Token'] = cp.decrypt(cert['key'])
    except Exception as e:
        api_keys = {
            "X-CP-API-ID": "5d4b40cd",
            "X-CP-API-KEY": "4c1108d8b2da465588bb87bfe0cbbd2c",
            "X-ECM-API-ID": "1580cfa7-b720-46f1-bbf9-671857fee0e8",
            "X-ECM-API-KEY": "b952b0e117ea8c3dc69fe6152e60220291c19b65",
            "bearer_token": "TR1p9dUA3HclW5rRUAmIFKvAVcuzxyib"
        }
        
    return api_keys


api_keys = build_keys()
n2 = ncm.NcmClientv2(api_keys=api_keys)
n3 = ncm.NcmClientv3(api_key=api_keys['Bearer Token'])

def apply_license():
    secure_connect_lic = cp.get_appdata('secure_connect_lic')
    mac = cp.get('status/product_info/mac0')
    cp.log(f"Applying license {secure_connect_lic} to {mac}")
    
    n3.regrade(mac=mac, subscription_id=secure_connect_lic)


def create_exchange_site():
    site_name = cp.get('config/system/system_id')
    exchange_network_id = cp.get_appdata('exchange_network_id')
    router_id = cp.get('status/ecm/client_id')
    lan_as_dns = True if cp.get_appdata('lan_as_dns') == 'True' else False
    local_domain = cp.get_appdata('local_domain')
    cp.log(f"Creating exchange site {site_name} on exchange network {exchange_network_id} for router {router_id}")
    cp.log(f"LAN as DNS: {lan_as_dns}, local domain: {local_domain}")
    
    site_info = n3.create_exchange_site(name=site_name, exchange_network_id=exchange_network_id, router_id=router_id, lan_as_dns=lan_as_dns, local_domain=local_domain)

    return site_info


def create_exchange_site_resources(site_info):
    exchange_site_id = cp.get_appdata('exchange_site_id')
    lan_resource_id = cp.get_appdata('lan_resource_id')
    cp_host_resource_id = cp.get_appdata('cp_host_resource_id')
    wildcard_resource_id = cp.get_appdata('wildcard_resource_id')
     

    '''
       def create_exchange_resource(self, resource_name: str, resource_type: str, site_id: str = None, site_name: str = None, **kwargs) -> dict:
        
        Creates an exchange resource.

        :param resource_name: Name for the new resource.
        :type resource_name: str
        :param resource_type: Type of resource to create. Must be one of:
            'exchange_fqdn_resources', 'exchange_wildcard_fqdn_resources', or 'exchange_ipsubnet_resources'.
        :type resource_type: str
        :param site_id: NCX Site ID to add the resource to. Optional if site_name is provided.
        :type site_id: str
        :param site_name: Name of the NCX Site to add the resource to. Optional if site_id is provided.
        :type site_name: str
        :param kwargs: Optional parameters for the resource. Can include:
            - protocols: List of protocols (e.g., ['TCP'], ['UDP'], ['TCP', 'UDP'], or ['ICMP']).
            - tags: List of tags for the resource.
            - domain: Domain name for FQDN or wildcard FQDN resources. Required for these types.
              For wildcard FQDN, must start with '*.'.
            - ip: IP address for IP subnet resources. Required for this type.
            - static_prime_ip: Static prime IP for the resource.
            - port_ranges: List of port ranges. Each range can be an int, a string (e.g., '80' or '8000-8080').
              Will be converted to a list of dicts with 'lower_limit' and 'upper_limit'.
              Not allowed when protocol is ICMP or None.
        :return: The created exchange resource data if successful, error message otherwise.
        :raises TypeError: If the type of any parameter is incorrect.
        :raises ValueError: If required parameters are missing, if an invalid resource type is provided,
                            if an invalid parameter or value is provided, or if port ranges are provided
                            with ICMP protocol or no protocol.
        :raises LookupError: If no site is found when searching by site_name.
        '''

if __name__ == "__main__":
    apply_license()
    site_info = create_exchange_site()
    ic(site_info)
    exit()
    create_exchange_site_resources(site_info=site_info)
