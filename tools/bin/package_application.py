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

BYTE_CODE_FILES = re.compile(r'^.*\.(pyc|pyo|pyd)$')
BYTE_CODE_FOLDERS = re.compile('^(__pycache__)$')


def file_checksum(hash_func=hashlib.sha256, file=None):
    h = hash_func()
    buffer_size = h.block_size * 64

    with open(file, 'rb') as f:
        for buffer in iter(lambda: f.read(buffer_size), b''):
            h.update(buffer)
    return h.hexdigest()


def get_paths_to_include(app_root):
    """Return value: Maps relative-to-app_root to relative-to-cwd.
    """
    paths = {}
    for path, d, f in os.walk(app_root):
        # TODO: Why not just skip the folder completely if it has a dot? (E.g. .git)
        for fl in f:
            if not shouldinclude(path, fl):
                print("Did not include {} in the App package.".format(fl))
                continue
            fully_qualified_file = os.path.join(path, fl)
            relpath = os.path.relpath(fully_qualified_file, app_root)
            # we need this be LINUX fashion!
            if sys.platform == "win32":
                # swap the network\\tcp_echo to be network/tcp_echo
                relpath = relpath.replace('\\', '/')
            paths[relpath] = fully_qualified_file

    return paths


def hash_paths(paths, hash_func=hashlib.sha256):
    hashes = {}
    for arcpath, fpath in paths.items():
        hashes[arcpath] = file_checksum(hash_func, fpath)
    return hashes


def shouldinclude(dirpath, filename):
    # Possible bug: A parent can have a dot and not be included, but the child's files will still be included.
    return not filename.startswith('.') and not os.path.basename(dirpath).startswith('.')


def pack_package(app_root, app_name):
    print('app_root: {}'.format(app_root))
    print('app_name: {}'.format(app_name))
    tar_name = "{}.tar".format(app_name)
    print("pack TAR:%s" % tar_name)
    #TODO: Consider using 'w:gz' to skip the additional gzip step.
    with tarfile.open(tar_name, 'w') as tar:
        tar.add(app_root, arcname=app_name)

    gzip_name = "{}.tar.gz".format(app_name)
    print("gzip archive:%s" % gzip_name)
    with open(tar_name, 'rb') as f_in:
        with gzip.open(gzip_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    if os.path.isfile(tar_name):
        os.remove(tar_name)


def create_signature(meta_data_folder, pkey):
    manifest_file = os.path.join(meta_data_folder, MANIFEST_FILE)
    checksum = file_checksum(hashlib.sha256, manifest_file).encode('utf-8')
    with open(os.path.join(meta_data_folder, SIGNATURE_FILE), 'wb') as sf:
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
        for file in filter(BYTE_CODE_FILES.match, files):
            os.remove(os.path.join(path, file))
        for d in filter(BYTE_CODE_FOLDERS.match, dirs):
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

        paths = get_paths_to_include(app_root)
        app['files'] = hash_paths(paths)

        with open(app_manifest_file, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True)

        create_signature(app_metadata_folder, pkey)

        pack_package(app_root, app_name)

        print('Package {}.tar.gz created'.format(app_name))


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
