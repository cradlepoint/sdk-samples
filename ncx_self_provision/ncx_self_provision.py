import cp
import ncm
import ipaddress
import time

# Build APIv2 keys and APIv3 Bearer Token from device config
def build_keys():
    api_keys = cp.get_ncm_api_keys()
    cp.log(f"APIv2 keys: {api_keys}")
    return api_keys


# Apply Secure Connect license to router
def apply_license():
    secure_connect_lic = cp.get_appdata('secure_connect_lic')
    mac = cp.get('status/product_info/mac0')
    cp.log(f"Applying Secure Conenct license {secure_connect_lic} to {mac}")
    n3.regrade(mac=mac, subscription_id=secure_connect_lic)

    time.sleep(1)
    sdwan_lic = cp.get_appdata('sdwan_lic')
    if sdwan_lic != 'None':
        cp.log(f"Applying SD-WAN license {sdwan_lic} to {mac}")
        n3.regrade(mac=mac, subscription_id=sdwan_lic)

    time.sleep(1)
    hmf_lic = cp.get_appdata('hmf_lic')
    if hmf_lic != 'None':
        cp.log(f"Applying HMF license {hmf_lic} to {mac}")
        n3.regrade(mac=mac, subscription_id=hmf_lic)


# Create exchange site
def create_exchange_site():
    site_name = cp.get('config/system/system_id')
    exchange_network_id = cp.get_appdata('exchange_network_id')
    router_id = str(cp.get('status/ecm/client_id'))
    lan_as_dns = True if cp.get_appdata('lan_as_dns') == 'True' else False
    local_domain = f'{site_name}.{cp.get_appdata("local_domain")}'
    lan_ip = cp.get('config/lan/0/ip_address')
    cp.log(f"Creating exchange site {site_name} on exchange network {exchange_network_id} for router {router_id}")
    cp.log(f"LAN as DNS: {lan_as_dns}, local domain: {local_domain}, primary DNS: {lan_ip}")
    site_info = n3.create_exchange_site(name=site_name, exchange_network_id=exchange_network_id, router_id=router_id, lan_as_dns=lan_as_dns, local_domain=local_domain, primary_dns=lan_ip)

    return site_info


# Create exchange site resources
def create_exchange_site_resources(site_info):
    site_id = site_info['id']
    site_name = site_info['attributes']['name']
    create_lan_resource = True if cp.get_appdata('create_lan_resource') == 'True' else False
    create_cp_host_resource = True if cp.get_appdata('create_cp_host_resource') == 'True' else False
    create_wildcard_resource = True if cp.get_appdata('create_wildcard_resource') == 'True' else False
    lan_ip = cp.get('config/lan/0/ip_address')
    lan_netmask = cp.get('config/lan/0/netmask')
    lan_cidr = str(ipaddress.ip_network(f'{lan_ip}/{lan_netmask}', strict=False))
    local_domain = f'{site_name}.{cp.get_appdata("local_domain")}'
    
    if create_lan_resource:
        cp.log(f"Creating LAN resource for {lan_cidr}")
        n3.create_exchange_resource(resource_name=f'{site_name}-lan', resource_type='exchange_ipsubnet_resources', site_id=site_id, ip=lan_cidr)

    if create_cp_host_resource:
        cp.log(f"Creating FQDN resource for router hostname")
        n3.create_exchange_resource(resource_name=f'{site_name}-cp', resource_type='exchange_fqdn_resources', site_id=site_id, domain=f'cp.{local_domain}')

    if create_wildcard_resource:
        cp.log(f"Creating wildcard FQDN resource for {site_name}")
        n3.create_exchange_resource(resource_name=f'{site_name}-wildcard', resource_type='exchange_wildcard_fqdn_resources', site_id=site_id, domain=f'*.{local_domain}')


# Move router to production group
def move_router_to_prod_group():
    prod_group_id = cp.get_appdata('prod_group_id')
    router_id = str(cp.get('status/ecm/client_id'))
    cp.log(f"Moving to production group {prod_group_id}")
    n2.assign_router_to_group(router_id=router_id, group_id=prod_group_id)


if __name__ == "__main__":
    cp.wait_for_uptime(120)
    cp.wait_for_wan_connection()
    api_keys = build_keys()
    n2 = ncm.NcmClientv2(api_keys=api_keys)
    n3 = ncm.NcmClientv3(api_key=api_keys['Bearer Token'])
    apply_license()
    site_info = create_exchange_site()
    time.sleep(5)
    create_exchange_site_resources(site_info=site_info)
    time.sleep(5)
    move_router_to_prod_group()
    cp.log('NCX Self Provisioning Complete')
    time.sleep(600)
