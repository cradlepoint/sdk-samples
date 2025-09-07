'''
This is the NCOS SDK tool used to created applications
for Cradlepoint NCOS devices. It will work on Linux,
OS X, and Windows once the computer environment is setup.

'''

import os
import sys
import uuid
import json
import shutil
import requests
import subprocess
import configparser
import unittest
import urllib3
import datetime
import hashlib
import re
import tarfile
import gzip
urllib3.disable_warnings()

from requests.auth import HTTPDigestAuth
from OpenSSL import crypto

# Upgrade functionality for checking and updating files from GitHub
def get_github_commit_timestamp(file_path):
    """
    Get the timestamp of the last commit for a specific file in cradlepoint/sdk-samples.
    
    Args:
        file_path (str): Path to the file (e.g., 'app_template/cp.py')
    
    Returns:
        datetime: Timestamp of the last commit, or None if error
    """
    url = "https://api.github.com/repos/cradlepoint/sdk-samples/commits"
    params = {'path': file_path, 'per_page': 1}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        commit_data = response.json()[0]
        timestamp_str = commit_data['commit']['committer']['date']
        
        # Convert to datetime object (compatible with all Python versions)
        # GitHub returns ISO format like: 2024-01-15T10:30:45Z
        # Remove 'Z' and parse manually
        timestamp_str = timestamp_str.replace('Z', '')
        return datetime.datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
        
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        print(f"Error getting GitHub commit timestamp: {e}")
        return None

def get_local_file_timestamp(file_path):
    """
    Get the modification timestamp of a local file.
    
    Args:
        file_path (str): Path to the local file
    
    Returns:
        datetime: Timestamp of the file modification, or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
    
    timestamp = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(timestamp)

def download_file_from_github(file_path, output_path=None):
    """
    Download a file from cradlepoint/sdk-samples repository.
    
    Args:
        file_path (str): Path to the file in the repo (e.g., 'app_template/cp.py')
        output_path (str, optional): Local path to save the file
    
    Returns:
        bool: True if successful, False otherwise
    """
    # GitHub raw URL format
    raw_url = f"https://raw.githubusercontent.com/cradlepoint/sdk-samples/master/{file_path}"
    
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        
        # If no output path specified, use the original file path
        if output_path is None:
            output_path = file_path
        
        # Create directory if it doesn't exist (only if there's a directory path)
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Write the file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Update file timestamp to current time to prevent repeated downloads
        import time
        current_time = time.time()
        os.utime(output_path, (current_time, current_time))
        
        print(f"File downloaded successfully to: {output_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        return False

def check_and_update_file(file_path, local_path=None):
    """
    Check if the GitHub version of a file is newer than the local version,
    and download if it is.
    
    Args:
        file_path (str): Path to the file in the repo (e.g., 'app_template/cp.py')
        local_path (str, optional): Local path to the file. If None, uses file_path
    
    Returns:
        dict: Status information about the check and update
    """
    if local_path is None:
        local_path = file_path
    
    print(f"Checking file: {file_path}")
    
    # Get GitHub commit timestamp
    github_timestamp = get_github_commit_timestamp(file_path)
    if github_timestamp is None:
        return {'status': 'error', 'message': 'Could not get GitHub timestamp'}
    
    # Get local file timestamp
    local_timestamp = get_local_file_timestamp(local_path)
    
    print(f"GitHub last commit: {github_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    if local_timestamp is None:
        print("Local file does not exist. Downloading...")
        success = download_file_from_github(file_path, local_path)
        return {
            'status': 'downloaded' if success else 'error',
            'message': 'File downloaded' if success else 'Download failed',
            'github_timestamp': github_timestamp,
            'local_timestamp': None
        }
    else:
        print(f"Local file modified: {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Compare timestamps (GitHub timestamp is in UTC, local is in local timezone)
        # Convert local timestamp to UTC for proper comparison
        import time
        local_utc_offset = time.timezone if (time.daylight == 0) else time.altzone
        # time.timezone is negative, so we add it to convert local to UTC
        local_utc_timestamp = local_timestamp + datetime.timedelta(seconds=abs(local_utc_offset))
        
        if github_timestamp > local_utc_timestamp:
            print("GitHub version is newer. Downloading...")
            success = download_file_from_github(file_path, local_path)
            return {
                'status': 'updated' if success else 'error',
                'message': 'File updated' if success else 'Update failed',
                'github_timestamp': github_timestamp,
                'local_timestamp': local_timestamp
            }
        else:
            print("Local file is up to date.")
            return {
                'status': 'up_to_date',
                'message': 'Local file is current',
                'github_timestamp': github_timestamp,
                'local_timestamp': local_timestamp
            }

def update():
    """
    Check and update core files from the GitHub repository.
    Updates: cp.py, cp_methods_reference.md, make.py, and app_template/cp.py
    """
    print("Checking for updates to core SDK files...")
    print("=" * 50)
    
    # Files to check and update
    files_to_check = [
        "cp.py",
        "cp_methods_reference.md", 
        "make.py",
        "app_template/cp.py"
    ]
    
    results = {}
    updated_count = 0
    error_count = 0
    
    for file_path in files_to_check:
        print(f"\n--- {file_path} ---")
        result = check_and_update_file(file_path)
        results[file_path] = result
        
        if result['status'] == 'updated':
            updated_count += 1
        elif result['status'] == 'downloaded':
            updated_count += 1
        elif result['status'] == 'error':
            error_count += 1
        
        print(f"Status: {result['status']}")
    
    # Summary
    print("\n" + "=" * 50)
    print("UPGRADE SUMMARY")
    print("=" * 50)
    
    for file_path, result in results.items():
        status_icon = "✓" if result['status'] in ['updated', 'downloaded', 'up_to_date'] else "✗"
        print(f"{status_icon} {file_path}: {result['status']}")
    
    print(f"\nFiles updated: {updated_count}")
    print(f"Errors: {error_count}")
    print(f"Files up to date: {len(files_to_check) - updated_count - error_count}")
    
    if updated_count > 0:
        print(f"\n{updated_count} file(s) have been updated.")
    
    if error_count > 0:
        print(f"\n{error_count} file(s) had errors during the update process.")

# These will be set in init() by using the sdk_settings.ini file.
# They are used by various functions in the file.
g_app_name = ''
g_app_uuid = ''
g_dev_client_ip = ''
g_dev_client_username = ''
g_dev_client_password = ''
g_python_cmd = 'python3'  # Default for Linux and OS X

# Constants for packaging
META_DATA_FOLDER = 'METADATA'
CONFIG_FILE = 'package.ini'
SIGNATURE_FILE = 'SIGNATURE.DS'
MANIFEST_FILE = 'MANIFEST.json'

BYTE_CODE_FILES = re.compile(r'^.*/.(pyc|pyo|pyd)$')
BYTE_CODE_FOLDERS = re.compile('^(__pycache__)$')


# Returns the proper HTTP Auth for the global username and password.
# Digest Auth is used for NCOS 6.4 and below while Basic Auth is
# used for NCOS 6.5 and up.
def get_auth():
    from http import HTTPStatus

    use_basic = False
    device_api = 'https://{}/api/status/product_info'.format(g_dev_client_ip)

    try:
        response = requests.get(device_api, auth=requests.auth.HTTPBasicAuth(g_dev_client_username, g_dev_client_password), verify=False)
        if response.status_code == HTTPStatus.OK:
            use_basic = True

    except:
        use_basic = False

    if use_basic:
        return requests.auth.HTTPBasicAuth(g_dev_client_username, g_dev_client_password)
    else:
        return requests.auth.HTTPDigestAuth(g_dev_client_username, g_dev_client_password)


# Returns boolean to indicate if the NCOS device is
# in DEV mode
def is_NCOS_device_in_DEV_mode():
    sdk_status = json.loads(get('/status/system/sdk')).get('data')
    if sdk_status.get('mode') in ['devmode', 'standard']:
        return True if sdk_status.get('mode') == 'devmode' else False
    raise('Unknown SDK mode (%s)' % sdk_status.get('mode'))


# Returns the app package name based on the global app name.
def get_app_pack(app_name=None):
    package_name = (app_name or g_app_name) + ".tar.gz"
    if app_name is not None:
        package_name = app_name + ".tar.gz"
    return package_name


# Gets data from the NCOS config store
def get(config_tree):
    ncos_api = 'https://{}/api{}'.format(g_dev_client_ip, config_tree)

    try:
        response = requests.get(ncos_api, auth=get_auth(), verify=False)

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with get for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None

    return json.dumps(json.loads(response.text), indent=4)


# Get a list of all the apps in the directory
def get_app_list():
    app_dirs = []
    cwd = os.getcwd()
    print("Scanning {} for app directories.".format(cwd))
    dirs_in_cwd = os.listdir(cwd)

    # Assume dir is an app_dir if it contains 'package.ini'
    for item in dirs_in_cwd:
        if os.path.isdir(item):
            contents = os.listdir(item)
            if 'package.ini' in contents:
                app_dirs.append(item)

    return app_dirs


# Puts an SDK action in the NCOS device config store
def put(value):
    try:
        response = requests.put("https://{}/api/control/system/sdk/action".format(g_dev_client_ip),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=get_auth(),
                                data={"data": '"{} {}"'.format(value, get_app_uuid())},
                                verify=False)

        print('status_code: {}'.format(response.status_code))

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with put for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None

    return json.dumps(json.loads(response.text), indent=4)


# Cleans the SDK directory for a given app by removing files created during packaging.
def clean(app=None):
    app_name = app or g_app_name
    print("Cleaning {}".format(app_name))
    app_pack_name = app_name + ".tar.gz"
    try:
        files_to_clean = [app_name + ".tar.gz", app_name + ".tar"]
        for file_name in files_to_clean:
            if os.path.isfile(file_name):
                os.remove(file_name)
                print('Deleted file: {}'.format(file_name))
    except OSError as e:
        print('Clean Error 1 for file {}: {}'.format(app_pack_name, e))

    meta_dir = '{}/{}/METADATA'.format(os.getcwd(), app_name)
    try:
        if os.path.isdir(meta_dir):
            shutil.rmtree(meta_dir)
    except OSError as e:
        print('Clean Error 2 for directory {}: {}'.format(meta_dir, e))

    build_file = os.path.join(os.getcwd(), '.build')
    try:
        if os.path.isfile(build_file):
            os.remove(build_file)
    except OSError as e:
        print('Clean Error 3 for file {}: {}'.format(build_file, e))


# Cleans the SDK directory for all apps by removing files created during packaging.
def clean_all():
    cwd = os.getcwd()
    print("Scanning {} for app directories.".format(cwd))
    app_dirs = get_app_list()

    for app in app_dirs:
        clean(app)


def scan_for_cr(path):
    scanfiles = ('.py', '.sh')
    for root, _, files in os.walk(path):
        for fl in files:
            # Only process files with the specified extensions
            if any(fl.endswith(ext) for ext in scanfiles):
                file_path = os.path.join(root, fl)
                with open(file_path, 'rb') as f:
                    content = f.read()
                if b'\r' in content:
                    # Remove carriage returns and write back to the file
                    new_content = content.replace(b'\r', b'')
                    with open(file_path, 'wb') as f:
                        f.write(new_content)
                    print(f'Removed carriage return (\\r) from file {file_path}')


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
    tar_name = f"{app_name}.tar"
    with tarfile.open(tar_name, 'w') as tar:
        tar.add(app_root, arcname=os.path.basename(app_root))

    gzip_name = "{}.tar.gz".format(app_name)
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
    if not os.path.exists(app_metadata_folder):
        os.makedirs(app_metadata_folder)

    for section in config.sections():
        app_name = section
        assert os.path.basename(app_root) == app_name

        clean_manifest_folder(app_metadata_folder)

        clean_bytecode_files(app_root)

        pmf = {}
        pmf['version_major'] = int(1)
        pmf['version_minor'] = int(0)
        pmf['version_patch'] = int(0)

        app = {}
        app['name'] = str(section)
        try:
            app['uuid'] = config[section]['uuid']
        except KeyError:
            if not pkey:
                app['uuid'] = str(uuid.uuid4())
            else:
                raise
        app['vendor'] = config[section]['vendor']
        app['notes'] = config[section]['notes']
        app['version_major'] = int(config[section].get('version_major', '0'))
        app['version_minor'] = int(config[section].get('version_minor', '0'))
        app['version_patch'] = int(config[section].get('version_patch', '0'))
        app['firmware_major'] = int(config[section].get('firmware_major', '0'))
        app['firmware_minor'] = int(config[section].get('firmware_minor', '0'))
        app['restart'] = config[section].getboolean('restart')
        app['reboot'] = config[section].getboolean('reboot')
        app['date'] = datetime.datetime.now().isoformat()
        if config.has_option(section, 'auto_start'):
            app['auto_start'] = config[section].getboolean('auto_start')
        if config.has_option(section, 'app_type'):
            app['app_type'] = int(config[section]['app_type'])

        data = {}
        data['pmf'] = pmf
        data['app'] = app

        app['files'] = hash_dir(app_root)

        with open(app_manifest_file, 'w') as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

        create_signature(app_metadata_folder, pkey)

        app_name_version = f"{section} v{app['version_major']}.{app['version_minor']}.{app['version_patch']}"
        pack_package(app_root, app_name_version)

        print(f'Package {app_name_version}.tar.gz created')


# Package the app files into a tar.gz archive.
def package(app=None):
    app_name = app or g_app_name
    print("Packaging {}".format(app_name))
    success = True
    app_path = os.path.join(app_name)
    scan_for_cr(app_path)
    setup_script(app_path)

    try:
        # Call package_application directly instead of via subprocess
        package_application(app_path, None)  # pkey=None for no signing
    except Exception as err:
        print('Error packaging {}: {}'.format(app_name, err))
        success = False
    finally:
        return success


# Package all the app files in the directory into a tar.gz archives.
def package_all():
    success = True
    cwd = os.getcwd()
    print("Scanning {} for app directories.".format(cwd))
    app_dirs = get_app_list()

    for app in app_dirs:
        package(app)

    return success


def setup_script(app_path):
    # check app_path for setup.py and execute it
    setup_path = os.path.join(app_path, 'setup.py')
    if os.path.isfile(setup_path):
        cwd = os.getcwd()
        os.chdir(app_path)
        print('Running setup.py for {}'.format(app_path))
        try:
            out = subprocess.check_output('{} {}'.format(g_python_cmd, 'setup.py'), stderr=subprocess.STDOUT, shell=True).decode()
        except subprocess.CalledProcessError as e:
            print ('[ERROR]: Exit code != 0')
            out = e.output.decode()
        print(out)
        os.chdir(cwd)


# Get the SDK status from the NCOS device
def status():
    status_tree = '/status/system/sdk'
    print('Get {} status for NCOS device at {}'.format(status_tree, g_dev_client_ip))
    response = get(status_tree)
    print(response)

# Create new app from app_template using supplied app name
def create(app_name=None):
    if not app_name:
        print('ERROR: No app name provided. Please provide a name. If you are using Cursor AI, it will generate a name for you based on your requested functionality.')
        return
    if os.path.exists(app_name):
        print('App already exists.  Please choose a different name.')
        return

    try:
        # Copy app_template folder and rename to new app name
        shutil.copytree('app_template', app_name)
        os.rename(f'{app_name}/app_template.py', f'{app_name}/{app_name}.py')

        # Replace app_template with new app name in all files
        files = [f'{app_name}.py', 'package.ini', 'readme.md', 'start.sh']
        for file in files:
            path = f'{app_name}/{file}'
            with open(path, 'r') as in_file:
                filedata = in_file.read()
            filedata = filedata.replace('app_template', app_name)
            with open(path, 'w') as out_file:
                out_file.write(filedata)
        print(f'App {app_name} created successfully.')
    except Exception as e:
        print(f'Error creating app: {e}')

# Transfer the app tar.gz package to the NCOS device
def install():
    if is_NCOS_device_in_DEV_mode():
        # Try to read version from package.ini in the app folder
        try:
            package_ini_path = os.path.join(g_app_name, 'package.ini')
            config = configparser.ConfigParser()
            config.read(package_ini_path)
            
            version_major = config[g_app_name].get('version_major', '0')
            version_minor = config[g_app_name].get('version_minor', '0') 
            version_patch = config[g_app_name].get('version_patch', '0')
            
            app_archive = f"{g_app_name} v{version_major}.{version_minor}.{version_patch}.tar.gz"
            if not os.path.exists(app_archive):
                app_archive = f"{g_app_name}.tar.gz"
        except Exception as e:
            app_archive = f"{g_app_name}.tar.gz"

        # Use sshpass for Linux or OS X
        cmd = 'sshpass -p {0} scp -O -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "{1}" {2}@{3}:/app_upload'.format(
               g_dev_client_password, app_archive,
               g_dev_client_username, g_dev_client_ip)

        # For Windows, use pscp.exe in the tools directory
        if sys.platform == 'win32':
            cmd = './tools/bin/pscp.exe -pw {0} -v "{1}" {2}@{3}:/app_upload'.format(
                   g_dev_client_password, app_archive,
                   g_dev_client_username, g_dev_client_ip)

        print('Installing {} in NCOS device {}.'.format(app_archive, g_dev_client_ip))
        try:
            if sys.platform == 'win32':
                subprocess.check_output(cmd)
            else:
                subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError as err:
            # There is always an error because the NCOS device will drop the connection.
            # print('Error installing: {}'.format(err))
            return 0
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to install the app into {}.'.format(g_dev_client_ip))


# Start the app in the NCOS device
def start():
    if is_NCOS_device_in_DEV_mode():
        print('Start application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('start')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to start the app from {}.'.format(g_dev_client_ip))


# Stop the app in the NCOS device
def stop():
    if is_NCOS_device_in_DEV_mode():
        print('Stop application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('stop')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to stop the app from {}.'.format(g_dev_client_ip))


# Uninstall the app from the NCOS device
def uninstall():
    if is_NCOS_device_in_DEV_mode():
        print('Uninstall application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('uninstall')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to uninstall the app from {}.'.format(g_dev_client_ip))


# Purge the app from the NCOS device
def purge():
    if is_NCOS_device_in_DEV_mode():
        print('Purging applications for NCOS device at {}'.format(g_dev_client_ip))
        response = put('purge')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to purge the app from {}.'.format(g_dev_client_ip))


# Prints the help information
def output_help():
    print('Command format is: {} make.py <action>\n'.format(g_python_cmd))
    print('Actions include:')
    print('================')
    print('create: Create a new app from the app_template folder.')
    print(f'\tYou must provide a new app name. Example: {g_python_cmd} make.py create my_new_app')
    print(f'\tIf you do not provide a name, Cursor AI will generate one for you based on your requested functionality.\n')
    print('clean: Clean all project artifacts.')
    print('\tTo clean all the apps, add the option "all" (i.e. clean all).\n')
    print('build or package: Create the app archive tar.gz file.')
    print('\tTo build all the apps, add the option "all" (i.e. build all).')
    print('\tAny directory containing a package.ini file is considered an app.\n')
    print('status: Fetch and print current app status from the locally connected NCOS device.\n')
    print('install: Secure copy the app archive to a locally connected NCOS device.')
    print('\tThe NCOS device must already be in SDK DEV mode via registration ')
    print('\tand licensing using NCM.\n')
    print('start: Start the app on the locally connected NCOS device.\n')
    print('stop: Stop the app on the locally connected NCOS device.\n')
    print('uninstall: Uninstall the app from the locally connected NCOS device.\n')
    print('purge: Purge all apps from the locally connected NCOS device.\n')
    print('uuid: Create a UUID for the app and save it to the package.ini file.\n')
    print('update: Check and update core SDK files from GitHub repository.\n')
    print('\tUpdates: cp.py, cp_methods_reference.md, make.py, and app_template/cp.py\n')
    print('unit: Run any unit tests associated with selected app.\n')
    print('system: Run any system tests associated with selected app.\n')
    print('help: Print this help information.\n')


# Get the uuid from application package.ini if not already set
def get_app_uuid():
    global g_app_uuid

    if g_app_uuid == '':
        uuid_key = 'uuid'
        app_config_file = os.path.join(g_app_name, 'package.ini')
        config = configparser.ConfigParser()
        config.read(app_config_file)
        if g_app_name in config:
            if uuid_key in config[g_app_name]:
                g_app_uuid = config[g_app_name][uuid_key]

                if g_app_uuid == '':
                    # Create a UUID if it does not exist
                    _uuid = str(uuid.uuid4())
                    config.set(g_app_name, uuid_key, _uuid)
                    with open(app_config_file, 'w') as configfile:
                        config.write(configfile)
                    print('INFO: Created and saved uuid {} in {}'.format(_uuid, app_config_file))
            else:
                print('ERROR: The uuid key does not exist in {}'.format(app_config_file))
        else:
            print('ERROR: The APP_NAME section does not exist in {}'.format(app_config_file))

    return g_app_uuid


# Setup all the globals based on the OS and the sdk_settings.ini file.
def init(app=None):
    global g_python_cmd
    global g_app_name
    global g_dev_client_ip
    global g_dev_client_username
    global g_dev_client_password

    success = True

    # Keys in sdk_settings.ini
    sdk_key = 'sdk'
    app_key = 'app_name'
    ip_key = 'dev_client_ip'
    username_key = 'dev_client_username'
    password_key = 'dev_client_password'

    if sys.platform == 'win32':
        g_python_cmd = 'python'

    elif sys.platform == 'Darwin':
        # This will exclude the '._' files  in the
        # tar.gz package for OS X.
        os.environ["COPYFILE_DISABLE"] = "1"

    settings_file = os.path.join(os.getcwd(), 'sdk_settings.ini')
    config = configparser.ConfigParser()
    config.read(settings_file)

    # Initialize the globals based on the sdk_settings.ini contents.
    if sdk_key in config:
        if app is not None:
            g_app_name = app
        elif app_key in config[sdk_key]:
            g_app_name = config[sdk_key][app_key]
        else:
            success = False
            print('ERROR 1: The {} key does not exist in {}'.format(app_key, settings_file))

        if g_app_name == '':
            print('The app_name key is empty in {}'.format(settings_file))

        if ip_key in config[sdk_key]:
            g_dev_client_ip = config[sdk_key][ip_key]
        else:
            success = False
            print('ERROR 2: The {} key does not exist in {}'.format(ip_key, settings_file))

        if username_key in config[sdk_key]:
            g_dev_client_username = config[sdk_key][username_key]
        else:
            success = False
            print('ERROR 3: The {} key does not exist in {}'.format(username_key, settings_file))

        if password_key in config[sdk_key]:
            g_dev_client_password = config[sdk_key][password_key]
        else:
            success = False
            print('ERROR 4: The {} key does not exist in {}'.format(password_key, settings_file))
    else:
        success = False
        print('ERROR 5: The {} section does not exist in {}'.format(sdk_key, settings_file))

    return success


if __name__ == "__main__":
    # Default is no arguments given.
    if len(sys.argv) < 2:
        output_help()
        sys.exit(0)

    utility_name = str(sys.argv[1]).lower()
    option = None
    if len(sys.argv) > 2:
        option = str(sys.argv[2])

    if utility_name in ['clean', 'package', 'build', 'uuid', 'status', 'start', 'stop', 'install', 'uninstall', 'purge', 'update']:
        # Load the settings from the sdk_settings.ini file.
        if not init(option):
            sys.exit(0)
        if utility_name != 'install':
            get_app_uuid()

    if utility_name == 'clean':
        if option == 'all':
            clean_all()
        else:
            clean()

    elif utility_name in ['package', 'build']:
        if option == 'all':
            package_all()
        else:
            package()

    elif utility_name == 'create':
        create(option)

    elif utility_name == 'status':
        status()

    elif utility_name == 'install':
        install()

    elif utility_name == 'start':
        start()

    elif utility_name == 'stop':
        stop()

    elif utility_name == 'uninstall':
        uninstall()

    elif utility_name == 'purge':
        purge()

    elif utility_name == 'uuid':
        # This is handled in init()
        pass

    elif utility_name == 'update':
        update()

    elif utility_name == 'unit':
        # load any tests in app/test/unit
        app_test_path = os.path.join(g_app_name, 'test', 'unit')
        suite = unittest.defaultTestLoader.discover(app_test_path)
        # change to the app dir so app files can be properly imported
        os.chdir(g_app_name)
        # add the current path to sys path so we can directly import
        sys.path.append(os.getcwd())
        # run suite
        unittest.TextTestRunner().run(suite)

    elif utility_name == 'system':
        # load any tests in app/test/unit
        app_test_path = os.path.join(g_app_name, 'test', 'system')
        suite = unittest.defaultTestLoader.discover(app_test_path)

        # try to add IP and auth info to system test classes
        def iterate_tests(test_suite_or_case):
            try:
                suite = iter(test_suite_or_case)
            except TypeError:
                yield test_suite_or_case
            else:
                for test in suite:
                    for subtest in iterate_tests(test):
                        yield subtest

        for test in iterate_tests(suite):
            try:
                test.DEV_CLIENT_IP = g_dev_client_ip
                test.DEV_CLIENT_USER = g_dev_client_username
                test.DEV_CLIENT_PASS = g_dev_client_password
            except Exception as e:
                # if classes don't accept it ignore
                pass

        # change to the app dir so app files can be properly imported
        os.chdir(g_app_name)
        # add the current path to sys path so we can directly import
        sys.path.append(os.getcwd())
        # run suite
        unittest.TextTestRunner().run(suite)

    else:
        output_help()

    sys.exit(0)
