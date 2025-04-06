import os
import json
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography import x509

# default paths for storing keys
CERTIFICATE_PATH = "certificate.pem"
PRIVATE_KEY_PATH = "private_key.pem"
PUBLIC_KEY_PATH = "public_key.pem"

DEFAULT_HEADER = "$0$"

class ECCEncryptor:
    def __init__(self, cert_pem = None, private_key_pem = None, certificate_path=CERTIFICATE_PATH, private_key_path=PRIVATE_KEY_PATH, public_key_path=PUBLIC_KEY_PATH, header=DEFAULT_HEADER):
        self.certificate_path = certificate_path
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self.header = header

        # Generate ECC keys if they don't exist
        self.generate_ecc_keypair()

        # Load the existing keys
        self.private_key = self.load_private_key(private_key_pem)
        self.public_key = self.load_public_key(cert_pem)

    def text_encode(self, data):
        return base64.b64encode(data).decode()

    def text_decode(self, data):
        return base64.b64decode(data)

    def generate_ecc_keypair(self, private_key_path=PRIVATE_KEY_PATH, public_key_path=PUBLIC_KEY_PATH):
        """Generate an ECC key pair and save it to files if they don't exist."""
        if not os.path.exists(private_key_path):
            self.private_key = ec.generate_private_key(ec.SECP256R1())
            self.public_key = self.private_key.public_key()

            # Save private key
            with open(private_key_path, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Save public key
            with open(public_key_path, "wb") as f:
                f.write(self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))

    def load_private_key(self, pem_data=None):
        """Load the ECC private key from a file."""
        if not pem_data:
            with open(self.private_key_path, "rb") as f:
                pem_data = f.read()
        else:
            pem_data = pem_data.encode()
        return serialization.load_pem_private_key(pem_data, password=None)

    def load_public_key(self, pem_data=None):
        """Load the ECC public key from an X.509 certificate."""
        if not pem_data:
            try:
                with open(self.certificate_path, "rb") as f:
                    pem_data = f.read()
            except FileNotFoundError:
                with open(self.public_key_path, "rb") as f:
                    pem_data = f.read()
        else:
            pem_data = pem_data.encode()
        cert = x509.load_pem_x509_certificate(pem_data)
        return cert.public_key()

    def derive_aes_key(self, private_key, public_key):
        """Derive a shared AES key using ECDH key exchange."""
        shared_secret = private_key.exchange(ec.ECDH(), public_key)
        aes_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256
            salt=None,
            info=b"ecc-aes-key",
        ).derive(shared_secret)
        return aes_key

    def encrypt_json(self, json_data):
        """Encrypt a JSON object using AES-GCM with an ECC-derived key."""
        aes_key = self.derive_aes_key(self.private_key, self.public_key)
        iv = os.urandom(12)  # Smaller IV (12 bytes) for AES-GCM
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
        encryptor = cipher.encryptor()

        json_bytes = json.dumps(json_data).encode()
        ciphertext = encryptor.update(json_bytes) + encryptor.finalize()

        return self.text_encode(self.header.encode() + iv + encryptor.tag + ciphertext)

    def decrypt_json(self, encrypted_base64):
        """Decrypt an AES-GCM encrypted JSON object using ECC-derived key."""
        aes_key = self.derive_aes_key(self.private_key, self.public_key)
        encrypted_data = self.text_decode(encrypted_base64)
        
        header, encrypted_data = encrypted_data[:len(self.header.encode())], encrypted_data[len(self.header.encode()):]
        if header != self.header.encode():
            raise ValueError("Invalid header")
        iv, tag, ciphertext = encrypted_data[:12], encrypted_data[12:28], encrypted_data[28:]

        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()

        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        return json.loads(decrypted.decode())

    def is_encrypted(self, base64_data):
        """Check if the data is encrypted by looking for the header"""
        try:
            # Try direct base64 header comparison
            base64_header = base64.b64encode(self.header.encode()).decode()
            if base64_data.startswith(base64_header):
                return True
            
            # Try decoding and check for raw header
            decoded_data = base64.b64decode(base64_data)
            return decoded_data.startswith(self.header.encode())
        except:
            return False
    

if __name__ == "__main__":
    encrypt_data = ECCEncryptor()

    json_data = {"this": "is", "some": "sample", "data": 123}

    # Encrypt
    encrypted_text = encrypt_data.encrypt_json(json_data)
    print("\n🔐 Encrypted (Base64):", encrypted_text)

    print("\nIs Encrypted:", encrypt_data.is_encrypted(encrypted_text))
    # Decrypt
    decrypted_json = encrypt_data.decrypt_json(encrypted_text)
    print("\n🔓 Decrypted JSON:", decrypted_json)
