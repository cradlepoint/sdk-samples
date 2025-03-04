# Encrypt AppData

## Overview
The `encrypt_appdata` application automatically encrypts sdk app data values that start with specific prefixes (`enc_`, `secret_`, `password_`, or `encrypt_`). It utilizes ECC (Elliptic Curve Cryptography) with the Secp256r1 certificate named `ecc`, which must be added through the certificate manager on your device.

![Encrypt AppData Encryption Screenshot](screenshot.jpg)

## Encrypting and Decrypting Data manually

You can use the `eccencryptor.py` script to encrypt and decrypt JSON data using ECC. You must export the ecc certificate from the certificate manager on your device and save it in the same directory as the script named `certificate.pem` and `private_key.pem` respectively.

### Encrypting Data

To encrypt JSON data, you can pass the JSON string as an argument to the script:

```sh
$ python eccencryptor.py '{"key": "value"}'
```

Alternatively, you can pipe the JSON data to the script:

```sh
$ echo '{"key": "value"}' | python eccencryptor.py
```

### Decrypting Data

To decrypt encrypted data, you can pass the encrypted string as an argument to the script:

```sh
$ python eccencryptor.py '$0$ivtagciphertext'
```

Alternatively, you can pipe the encrypted data to the script:

```sh
$ echo '$0$ivtagciphertext' | python eccencryptor.py
```
