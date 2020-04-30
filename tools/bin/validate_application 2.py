#!/usr/bin/env python3

import hashlib
import os
import json
import sys
from OpenSSL import crypto
import shutil
import re

META_DATA_FOLDER = 'METADATA'
CONFIG_FILE = 'package.ini'
SIGNATURE_FILE = 'SIGNATURE.DS'
MANIFEST_FILE = 'MANIFEST.json'

BYTE_CODE_FILES = re.compile('^.*\.(pyc|pyo|pyd)$')
BYTE_CODE_FOLDERS = re.compile('^(__pycache__)$')


class InvalidSignature(Exception):
    pass


class InvalidHash(Exception):
    pass


def file_checksum(hash_func=hashlib.sha256, file=None):
    h = hash_func()
    buffer_size = h.block_size * 64

    with open(file, 'rb') as f:
        for buffer in iter(lambda: f.read(buffer_size), b''):
            h.update(buffer)
    return h.hexdigest()


def validate_files(app_root):
    app_metadata_folder = os.path.join(app_root, META_DATA_FOLDER)
    manifest = read_manifest(app_metadata_folder)
    expected_checksum = manifest['app']['files']

    for path, dirs, files in os.walk(app_root):
        for file in files:
            fully_qualified_file = os.path.join(path, file)
            manifest_file_name = fully_qualified_file[len(app_root) + 1:]
            checksum = file_checksum(hashlib.sha256, fully_qualified_file)

            if manifest_file_name in (
                    os.path.join(META_DATA_FOLDER, SIGNATURE_FILE),
                    os.path.join(META_DATA_FOLDER, MANIFEST_FILE)):
                continue

            try:
                if expected_checksum[manifest_file_name] != checksum:
                    raise InvalidHash('File "{}" has been modified'.format(
                        manifest_file_name))
                del expected_checksum[manifest_file_name]
            except KeyError:
                raise InvalidHash(
                    'File "{}" has been added'.format(manifest_file_name))

    if len(expected_checksum) != 0:
        raise InvalidHash('Files have been removed: {}'.format(
            list(expected_checksum.keys())))


def validate_signature(app_root, cert):
    app_metadata_folder = os.path.join(app_root, META_DATA_FOLDER)
    app_manifest_file = os.path.join(app_metadata_folder, MANIFEST_FILE)
    signature_file = os.path.join(app_metadata_folder, SIGNATURE_FILE)

    with open(signature_file, 'rb') as sf:
        signature = sf.read()
        checksum = file_checksum(hashlib.sha256,
                                 file=app_manifest_file).encode('utf-8')

        if cert:
            try:
                crypto.verify(cert, signature, checksum, 'sha256')
            except Exception as e:
                raise InvalidSignature('Invalid Signature: ' + e)
        else:
            if checksum != signature:
                raise InvalidSignature('Invalid Signature')


def read_manifest(app_metadata_folder):
    with open(os.path.join(app_metadata_folder, MANIFEST_FILE), 'r') as mf:
        manifest = json.load(mf)
    return manifest


def clean_bytecode_files(app_root):
    for path, dirs, files in os.walk(app_root):
        for file in filter(lambda x: BYTE_CODE_FILES.match(x), files):
            os.remove(os.path.join(path, file))
        for d in filter(lambda x: BYTE_CODE_FOLDERS.match(x), dirs):
            shutil.rmtree(os.path.join(path, d))
    pass


def verify_application(app_root, cert):
    app_root = os.path.realpath(app_root)

    clean_bytecode_files(app_root)

    try:
        validate_signature(app_root, cert)
    except InvalidSignature as signature_error:
        print('Invalid Signature: {}'.format(signature_error))
        return False

    try:
        validate_files(app_root)
    except InvalidHash as hash_error:
        print('Invalid Hash: {}'.format(hash_error))
        return False

    return True


def argument_list(args):
    print('{} <applicationRoot> <path_to_pub_OPTIONAL>'.format(args[0]))


if __name__ == "__main__":

    if len(sys.argv) < 2:
        argument_list(sys.argv)
    else:
        cert = None
        if 3 == len(sys.argv):
            with open(sys.argv[2], 'r') as pf:
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, pf.read())
        if not verify_application(sys.argv[1], cert):
            sys.exit(1)
