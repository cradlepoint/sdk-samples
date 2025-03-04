"""encrypt_appdata.py - Automatically encrypts appdata values that start with 'enc_', or 'secret_', or 'password_', or 'encrypt_'
requires an ecc Secp256r1 certificate named 'ecc' to be added through certificate manager on the device"""

import time

from csappdata import AppDataCSClient
cp = AppDataCSClient('encrypt_appdata', encrypt_cert_name='ecc')
cp.log('Starting...')

def auto_encrypt_data(path, value, args):
    time.sleep(1) # Wait for the data to be updated
    value = cp.get("/config/system/sdk/appdata") # Get the latest appdata
    for appdata in value:
        key = appdata['name']
        value = appdata['value']
        if any(key.startswith(prefix) for prefix in ['enc_', 'secret_', 'password_', 'encrypt_']) and not cp.eccappdata.is_encrypted(value):
            cp.log(f'Encrypting {key}...')
            cp.set_appdata(key, value, encrypt=True)

def appdata_change(key, new_value):
    cp.log(f'Appdata {key} changed to {new_value}')


def main():
    cp.on("put", "/config/system/sdk/appdata", auto_encrypt_data)
    cp.on("post", "/config/system/sdk/appdata", auto_encrypt_data)
    cp.on("delete", "/config/system/sdk/appdata", auto_encrypt_data)

    # also can detect changes on specific keys regardless of encryption
    cp.on_appdata_change("enc_mydata", appdata_change)

    cp.log("Autoencryption enabled...")
    while True:
        auto_encrypt_data(None, None, None)
        time.sleep(30)

if __name__ == "__main__":
    main()