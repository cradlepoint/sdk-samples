# certificate_sample - A function to extract certificates to PEM files for use in other applications.
# This function extracts a certificate by name and saves the x509 along with any CA certificates to fullchain.pem
# It also extracts the private key for the given certificate name and saves it to privatekey.pem

from csclient import EventingCSClient

cp = EventingCSClient('certificate_sample')

def extract_and_save_cert(cert_name):
    """Extract and save the certificate and key to the local filesystem."""
    cert_x509 = None
    cert_key = None
    ca_uuid = None

    # Get the list of certificates
    certs = cp.get('config/certmgmt/certs')

    # Extract the x509 and key for the matching certificate and its CA
    for cert in certs:
        if cert['name'] == cert_name:
            cert_x509 = cert.get('x509')
            cert_key = cp.decrypt(f'config/certmgmt/certs/{cert["_id_"]}/key')
            ca_uuid = cert.get('ca_uuid')
            cp.log(f'Found certificate "{cert_name}" with CA UUID: {ca_uuid}')
            break
    else:
        cp.log(f'No certificate "{cert_name}" found')
        return

    # Extract the CA certificate(s) if it exists
    while ca_uuid not in ["", "None", None]:
        for cert in certs:
            if cert.get('_id_') == ca_uuid:
                cert_x509 += "\n" + cert.get('x509')
                ca_uuid = cert.get('ca_uuid')
                msg = f'Found CA certificate "{cert.get("name")}"'
                if ca_uuid not in ["", "None", None]:
                    msg += f' with CA UUID: {ca_uuid}'
                cp.log(msg)

    # Write the fullchain.pem and privatekey.pem files
    if cert_x509 and cert_key:
        with open("fullchain.pem", "w") as fullchain_file:
            fullchain_file.write(cert_x509)
        with open("privatekey.pem", "w") as privatekey_file:
            privatekey_file.write(cert_key)
        cp.log(f'Certificate "{cert_name}" extracted and saved')
    else:
        cp.log(f'Missing certificate or key for "{cert_name}"')

extract_and_save_cert('CP Zscaler')