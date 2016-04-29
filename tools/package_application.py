#!tools/bin/python

# changes by Lynn:
# add the package.ini to the MANIFEST hash table
# in the MANIFEST hash table, force use of linux "/" separator in json text file
# use the Python modules tarfile and gzip, do not 'shell' to Linux
# make sure the 'package'ing directory is in the build subdirectory

import configparser
import logging
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
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
            # if fl == CONFIG_FILE:
            #     continue
            # we need this be LINUX fashion!
            if sys.platform == "win32":
                # swap the network\\tcp_echo to be network/tcp_echo
                fully_qualified_file = path.replace('\\', '/') + '/' + fl
            else:  # else allow normal method
                fully_qualified_file = os.path.join(path, fl)
            hashed_files[fully_qualified_file[len(target) + 1:]] =\
                file_checksum(hash_func, fully_qualified_file)

    return hashed_files


def pack_package(app_root, app_name):
    """
    :param app_root: build\\network\\tcp_echo
    :param app_name: tcp_echo
    :return:
    """
    import tarfile
    import gzip

    base = None
    if app_root.startswith("build"):
        base = "build"
        app_root = app_root[6:]
        os.chdir("build")

    # we'll make "tcp_echo.tar.gz"
    logging.debug("pack TAR:%s.tar" % app_name)
    tar_name = "{}.tar".format(app_name)
    tar = tarfile.open(tar_name, 'w')
    # this will add the sub-directory recursively
    tar.add(app_root)
    tar.close()

    logging.debug("gzip  archive:%s.tar.gz" % app_name)
    gzip_name = "{}.tar.gz".format(app_name)
    with open(tar_name, 'rb') as f_in:
        with gzip.open(gzip_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    if base is not None:
        os.chdir("..")

    return


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
    """

    :param str app_root: root path, such as "network/tcp_echo"
    :param pkey: encryption key
    :return:
    """
    # app_root = os.path.real path(app_root)
    if app_root[-1] == '/':
        # this routine (or os.path.basename()) doesn't like trailing dir slash
        app_root = app_root[:-1]
    logging.debug("app_root:%s" % app_root)

    # expect like "network/tcp_echo/package.ini"
    app_config_file = os.path.join(app_root, CONFIG_FILE)
    logging.debug("app_config_file:%s" % app_config_file)

    # expect like "network/tcp_echo/METADATA"
    app_metadata_folder = os.path.join(app_root, META_DATA_FOLDER)
    logging.debug("app_metadata_folder:%s" % app_metadata_folder)

    # expect like "network/tcp_echo/METADATA/MANIFEST.json"
    app_manifest_file = os.path.join(app_metadata_folder, MANIFEST_FILE)
    logging.debug("app_manifest_file:%s" % app_manifest_file)

    config = configparser.ConfigParser()
    config.read(app_config_file)
    if not os.path.exists(app_metadata_folder):
            os.makedirs(app_metadata_folder)

    for section in config.sections():
        app_name = section
        assert os.path.basename(app_root) == app_name

        clean_manifest_folder(app_metadata_folder)

        clean_bytecode_files(app_root)

        pmf = dict()
        pmf['version_major'] = int(1)
        pmf['version_minor'] = int(0)

        app = dict()
        app['name'] = str(section)
        logging.debug("app['name']:{}".format(app['name']))
        try:
            app['uuid'] = config[section]['uuid']
        except KeyError:
            if not pkey:
                app['uuid'] = str(uuid.uuid4())
            else:
                raise
        app['vendor'] = config[section]['vendor']
        app['notes'] = config[section]['notes']
        app['version_major'] = int(config[section]['version_major'])
        app['version_minor'] = int(config[section]['version_minor'])
        app['firmware_major'] = int(config[section]['firmware_major'])
        app['firmware_minor'] = int(config[section]['firmware_minor'])
        app['restart'] = config[section].getboolean('restart')
        app['reboot'] = config[section].getboolean('reboot')
        # this actually makes an INVALID format, because it uses localtime, but adds no time-zine offset!
        # app['date'] = datetime.datetime.now().isoformat()
        app['date'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        data = dict()
        data['pmf'] = pmf
        data['app'] = app

        app['files'] = hash_dir(app_root)

        with open(app_manifest_file, 'w') as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

        create_signature(app_metadata_folder, pkey)

        logging.debug("app_root:{}".format(app_root))
        logging.debug("section:{}".format(section))
        pack_package(app_root, section)

        print(
            'Package {}.tar.gz created'.format(section))


def argument_list(args):
    print('{} <applicationRoot> <path_to_private_OPTIONAL>'.format(args[0]))


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        argument_list(sys.argv)
    else:

        private_key = None
        if 2 < len(sys.argv):
            with open(sys.argv[2], 'r') as pf:
                private_key = crypto.load_privatekey(
                        type=crypto.FILETYPE_PEM, buffer=pf.read(),
                        passphrase='pass'.encode('utf-8'))

        logging.debug("app:%s" % sys.argv[1])
        package_application(sys.argv[1], private_key)
