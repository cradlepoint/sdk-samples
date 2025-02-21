# app_template.py
# Template for Ericsson Cradlepoint SDK applications
# Includes examples of using the CPSDK for various operations

# Initialize the CPSDK
from cpsdk import CPSDK
cp = CPSDK('app_template')

# Write a log message
cp.log('Hello, world!')

# Add your code here


"""
# Examples of using the CPSDK:


# GET Example: Get the WAN connection state and log it
wan_state = cp.get('status/wan/connection_state')
cp.log(f'WAN State: {wan_state}')


# POST Example: Create user and get index from response
req = cp.post('config/system/users', {'username': 'newuser', 'password': 'secret1234', 'group': 'admin'})
if req.get('status') == 'ok':
    index = req.get('data')
    cp.log(f'User created with index: {index}')
else:
    cp.log(f'Error creating user: {req.get("data")}')

    
# PUT Example: Update user
req = cp.put(f'config/system/users/{index}', {'password': 'newsecret1234'})
if req.get('status') == 'ok':
    cp.log(f'User updated with index: {index}')
else:
    cp.log(f'Error updating user: {req.get("data")}')

    
# DELETE Example: Delete user
req = cp.delete(f'config/system/users/{index}')
if req.get('status') == 'ok':
    cp.log(f'User deleted with index: {index}')
else:
    cp.log(f'Error deleting user: {req.get("data")}')

    
# Example: Get appdata value
appdata_value = cp.get_appdata('server')
cp.log(f'Appdata "server" value: {appdata_value}')


# Example:If appdata does not exist, create it
if not appdata_value:
    cp.post_appdata('server', '192.168.0.1')
    cp.log('Appdata "server" created')

    
# Example: Update appdata
cp.put_appdata('server', '192.168.0.2')
cp.log('Appdata "server" updated')


# Exampe: Get updated appdata value
appdata_value = cp.get_appdata('server')
cp.log(f'Appdata "server" value: {appdata_value}')


# Example: Delete appdata
cp.delete_appdata('server')
cp.log('Appdata "server" deleted')


# Example: Get list of clients and put in description (Max 1024 characters)
clients = cp.get_ipv4_lan_clients()
cp.log(f'CLIENTS: {clients}')
cp.put('config/system/desc', json.dumps(clients))


# Example: Extract and save certificate
cert_file, pkey_file = cp.extract_cert_and_key('CP Zscaler')
cp.log(f'Certificate File: {cert_file}')
cp.log(f'Private Key File: {pkey_file}')


"""

