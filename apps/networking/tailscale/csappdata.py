import os
from csclient import EventingCSClient
from eccencryptor import ECCEncryptor


class AppDataCSClient(EventingCSClient):
    def __init__(self, *args, encrypt_cert_name=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.eccappdata = None
        
        if encrypt_cert_name:
            self.enable_encryption(encrypt_cert_name)
        self.change_listeners = {}

    def enable_encryption(self, encrypt_cert_name):
        encrypt_cert_uuid = self.find_cert_id_by_name(encrypt_cert_name)
        if not encrypt_cert_uuid:
            self.log(f"Encryption requested but certificate '{encrypt_cert_name}' not found.")
            return
        cert, key = self.get_cert_and_private_key(uuid=encrypt_cert_uuid)
        self.eccappdata = ECCEncryptor(cert_pem=cert, private_key_pem=key)

    def on_appdata_change(self, key, callback):
        if len(self.change_listeners) == 0:
            self.on("PUT", "/config/system/sdk/appdata", self._on_appdata_change)
            self.on("POST", "/config/system/sdk/appdata", self._on_appdata_change)
            self.on("DELETE", "/config/system/sdk/appdata", self._on_appdata_change)
        self.change_listeners[key] = callback

    def _on_appdata_change(self, path, value, args):
        key = args[0]
        if key in self.change_listeners:
            value = next((j['value'] for j in value if j['name'] == key), None)
            if self.eccappdata and self.eccappdata.is_encrypted(value):
                value = self.eccappdata.decrypt_json(value)
            self.change_listeners[key](value)

    def get_appdata(self, key):
        """Get an appdata value by key. Automatically checks environment variables too.
        though the environment variable must be in uppercase and replace '.' and '-' with '_'."""
        rval = None
        env_key = key.upper().replace('.', '_').replace('-', '_')
        env_value = os.environ.get(env_key)
        if env_value:
            rval = env_value

        appdata = self.get("/config/system/sdk/appdata")
        rval = next((j['value'] for j in appdata if j['name'] == key), None)
        if rval and self.eccappdata and self.eccappdata.is_encrypted(rval):
            rval = self.eccappdata.decrypt_json(rval)
        return rval

    def set_appdata(self, key, value, encrypt=False):
        """Set an appdata value by key."""
        if self.eccappdata and encrypt:
            value = self.eccappdata.encrypt_json(value)
        appdata = self.get("/config/system/sdk/appdata")
        for item in appdata:
            if item['name'] == key:
                item['value'] = value
                self.put("/config/system/sdk/appdata", appdata)
                return
        appdata.append({'name': key, 'value': value})
        self.put("/config/system/sdk/appdata", appdata)

    def find_cert_id_by_name(self, name):
        """Find a certificate by name."""
        certs = self.decrypt("/config/certmgmt/certs") or []
        for cert in certs:
            if cert["name"] == name:
                return cert["_id_"]

    def get_cert_data(self, uuid):
        """Get certificate data by UUID."""
        cert_data = self.get(f"/config/certmgmt/certs/{uuid}")
        key_path = f"/config/certmgmt/certs/{cert_data['_id_']}/key"
        decrypted_key = self.decrypt(key_path)
        cert_data["key"] = decrypted_key
        return cert_data

    def get_cert_and_private_key(self, uuid=None, name=None):
        """Load a certificate by UUID or name. Returns a tuple of (cert pem, private key pem)."""
        cert_data = self.get_cert_data(uuid) if uuid else self.get_cert_data(self.find_cert_id_by_name(name))
        return cert_data["x509"], cert_data["key"]