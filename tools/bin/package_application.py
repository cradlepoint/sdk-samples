#!/usr/bin/env python3

import configparser
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import tarfile
import gzip
from OpenSSL import crypto

META_DATA_FOLDER = 'METADATA'
CONFIG_FILE = 'package.ini'
SIGNATURE_FILE = 'SIGNATURE.DS'
MANIFEST_FILE = 'MANIFEST.json'

BYTE_CODE_FILES = re.compile('^.*\.(pyc|pyo|pyd)$')
BYTE_CODE_FOLDERS = re.compile('^(__pycache__)$')


def file_checksum(hash_func=hashlib.sha256, file=None):
    h = hash_func()
    buffer_size = h.block_size * 64

    with open(file, 'rb') as f:
        for buffer in iter(lambda: f.read(buffer_size), b''):
            h.update(buffer)
    return h.hexdigest()


def hash_dir(target, hash_func=hashlib.sha256):
    hashed_files = {}
    for path, d, f in os.walk(target):
        for fl in f:
            if not fl.startswith('.') and not os.path.basename(path).startswith('.'):
                # we need this be LINUX fashion!
                if sys.platform == "win32":
                    # swap the network\\tcp_echo to be network/tcp_echo
                    fully_qualified_file = path.replace('\\', '/') + '/' + fl
                else:  # else allow normal method
                    fully_qualified_file = os.path.join(path, fl)
                hashed_files[fully_qualified_file[len(target) + 1:]] =\
                    file_checksum(hash_func, fully_qualified_file)
            else:
                print("Did not include {} in the App package.".format(fl))

    return hashed_files


def pack_package(app_root, app_name):
    print('app_root: {}'.format(app_root))
    print('app_name: {}'.format(app_name))
    tar_name = "{}.tar".format(app_name)
    print("pack TAR:%s" % tar_name)
    #TODO: Consider using 'w:gz' to skip the additional gzip step.
    with tarfile.open(tar_name, 'w') as tar:
        tar.add(app_root, arcname=os.path.basename(app_root))

    gzip_name = "{}.tar.gz".format(app_name)
    print("gzip archive:%s" % gzip_name)
    with open(tar_name, 'rb') as f_in:
        with gzip.open(gzip_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    if os.path.isfile(tar_name):
        os.remove(tar_name)


def create_signature(meta_data_folder, pkey):
    manifest_file = os.path.join(meta_data_folder, MANIFEST_FILE)
    with open(os.path.join(meta_data_folder, SIGNATURE_FILE), 'wb') as sf:
        checksum = file_checksum(hashlib.sha256, manifest_file).encode('utf-8')
        if pkey:
            sf.write(crypto.sign(pkey, checksum, 'sha256'))
        else:
            sf.write(checksum)


def clean_manifest_folder(app_metadata_folder):
    path, dirs, files = next(os.walk(app_metadata_folder))

    for file in files:
        fully_qualified_file = os.path.join(path, file)
        os.remove(fully_qualified_file)

    for d in dirs:
        shutil.rmtree(os.path.join(path, d))


def clean_bytecode_files(app_root):
    for path, dirs, files in os.walk(app_root):
        for file in filter(lambda x: BYTE_CODE_FILES.match(x), files):
            os.remove(os.path.join(path, file))
        for d in filter(lambda x: BYTE_CODE_FOLDERS.match(x), dirs):
            shutil.rmtree(os.path.join(path, d))
    pass


def package_application(app_root, pkey):
    app_root = os.path.realpath(app_root)
    app_config_file = os.path.join(app_root, CONFIG_FILE)
    app_metadata_folder = os.path.join(app_root, META_DATA_FOLDER)
    app_manifest_file = os.path.join(app_metadata_folder, MANIFEST_FILE)
    config = configparser.ConfigParser()
    config.read(app_config_file)

    os.makedirs(app_metadata_folder, exist_ok=True)

    for section in config.sections():
        app_name = section
        assert os.path.basename(app_root) == app_name

        clean_manifest_folder(app_metadata_folder)

        clean_bytecode_files(app_root)

        pmf = {
            'version_major': 1,
            'version_minor': 0,
        }

        app = {
            'name': str(section),
            'vendor': config[section]['vendor'],
            'notes': config[section]['notes'],
            'version_major': int(config[section]['version_major']),
            'version_minor': int(config[section]['version_minor']),
            'firmware_major': int(config[section]['firmware_major']),
            'firmware_minor': int(config[section]['firmware_minor']),
            'restart': config[section].getboolean('restart'),
            'reboot': config[section].getboolean('reboot'),
            'date': datetime.datetime.now().isoformat(),
        }

        try:
            app['uuid'] = config[section]['uuid']
        except KeyError:
            if not pkey:
                app['uuid'] = str(uuid.uuid4())
            else:
                raise
        if config.has_option(section, 'auto_start'):
            app['auto_start'] = config[section].getboolean('auto_start')
        if config.has_option(section, 'app_type'):
            app['app_type'] = int(config[section]['app_type'])


        data = {
            'pmf': pmf,
            'app': app,
        }

        app['files'] = hash_dir(app_root)

        with open(app_manifest_file, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True)

        create_signature(app_metadata_folder, pkey)

        pack_package(app_root, section)

        print('Package {}.tar.gz created'.format(section))


def argument_list(args):
    print('{} <applicationRoot> <path_to_private_OPTIONAL>'.format(args[0]))


if __name__ == "__main__":

    if len(sys.argv) < 2:
        argument_list(sys.argv)
    else:

        pkey = None
        if 3 == len(sys.argv):
            with open(sys.argv[2], 'r') as pf:
                pkey = crypto.load_privatekey(
                        type=crypto.FILETYPE_PEM, buffer=pf.read(),
                        passphrase='pass'.encode('utf-8'))

        package_application(sys.argv[1], pkey)
