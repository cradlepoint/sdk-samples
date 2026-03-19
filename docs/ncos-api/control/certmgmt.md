# Certificate Management API

Router can generate and manage X.509 certificates via `control/certmgmt`.

## Create Certificates

All cert creation uses `cp.put('control/certmgmt/ca', {...})`.

### CA Certificate

```python
cp.put('control/certmgmt/ca', {
    "name": "myca",
    "is_ca": True,
    "attr": "",
    "SAN": "",
    "days": 365,
    "type": "rsa",
    "digest": "SHA256",
    "key_size": 2048,
    "curve": "SECP224R1",
    "CN": "myca"
})
# Returns index into config/certmgmt/certs/
```

### TLS Server Certificate

```python
cp.put('control/certmgmt/ca', {
    "name": "server",
    "is_ca": False,
    "attr": "server",
    "SAN": "",
    "days": 365,
    "type": "rsa",
    "digest": "SHA256",
    "key_size": 2048,
    "curve": "SECP224R1",
    "CN": "server"
})
```

### TLS Client Certificate (signed by specific CA)

```python
cp.put('control/certmgmt/ca', {
    "name": "client",
    "is_ca": False,
    "attr": "client",
    "SAN": "",
    "days": 365,
    "type": "rsa",
    "digest": "SHA256",
    "key_size": 2048,
    "curve": "SECP224R1",
    "ca_uuid": "00000000-ece6-3612-8417-5dca1c72cdd6",
    "CN": "client"
})
```

## Field Reference

- `name` - Display name for the cert
- `is_ca` - `True` for CA certs, `False` for leaf certs
- `attr` - `""` general, `"server"` TLS server, `"client"` TLS client
- `SAN` - Subject Alternative Names (comma-separated)
- `days` - Validity period
- `type` - Key type: `"rsa"` or `"ec"`
- `digest` - Hash algorithm: `"SHA256"`, `"SHA384"`, `"SHA512"`
- `key_size` - RSA key size: 1024, 2048, 4096
- `curve` - EC curve (only for type=ec): `"SECP224R1"`, `"SECP256R1"`, etc.
- `ca_uuid` - UUID of the CA to sign with (omit to use default/self-sign)
- `CN` - Common Name

## Retrieve Certificates

```python
# List all certs
certs = cp.get('config/certmgmt/certs')
# Returns list of dicts, each with: _id_ (uuid), name, x509 (PEM), key (encrypted)

# Get cert PEM by index
cert_pem = cp.get('config/certmgmt/certs/{index}/x509')

# Get decrypted private key PEM
key_pem = cp.decrypt('config/certmgmt/certs/{index}/key')
```

## Notes

- `cp.decrypt()` retrieves encrypted values (like private keys) in plaintext
- Certs and keys are stored in `config/certmgmt/certs/` as an array
- The `_id_` field on each cert is the UUID, used as `ca_uuid` when signing child certs
- The cert PEM is in the `x509` field (not `cert`)
- Write PEM data to `tmp/` files for use with Python's `ssl` module

## Export Certificate as PKCS#12 (.p12)

The router can export any certificate as a `.p12` file via REST API (not available through the SDK `cp` module):

```
GET /api/certexport?uuid={cert_uuid}&passphrase={password}&filetype=P12
```

- Requires HTTP Basic Auth (`admin:password`)
- `uuid` - The `_id_` field from `config/certmgmt/certs`
- `passphrase` - Password to encrypt the `.p12` file
- `filetype` - `P12` for PKCS#12 format

Example with curl:
```bash
curl -u admin:password "http://192.168.1.4/api/certexport?uuid=00010000-ece6-3612-8417-5dca1c72cdd6&passphrase=foo&filetype=P12" -o client.p12
```

Note: This endpoint requires router admin credentials and is only accessible via REST, not the SDK `cp` module. For SDK apps that need to generate `.p12` files without admin credentials, use pure-Python PKCS#12 encoding with PEM data from `cp.get()` and `cp.decrypt()`.
