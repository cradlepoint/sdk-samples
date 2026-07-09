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
import subprocess
import configparser
import unittest
import datetime
import hashlib
import re
import tarfile
import gzip
import time

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
    from requests.auth import HTTPDigestAuth
except ImportError:
    requests = None
    HTTPDigestAuth = None
    
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
        # Compare timestamps (GitHub timestamp is in UTC, local is in local timezone)
        # Convert local timestamp to UTC for proper comparison
        import time
        local_utc_offset = time.timezone if (time.daylight == 0) else time.altzone
        # time.timezone is negative for timezones behind UTC, so we add the absolute value to get UTC
        local_utc_timestamp = local_timestamp + datetime.timedelta(seconds=abs(local_utc_offset))
        print(f"Local file modified: {local_utc_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
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
    Updates: make.py and apps/templates/app_template/cp.py
    """
    print("Checking for updates to core SDK files...")
    print("=" * 50)
    
    # Files to check and update
    files_to_check = [
        ("make.py", "make.py"),
        ("apps/templates/app_template/cp.py", "apps/templates/app_template/cp.py"),
    ]
    
    results = {}
    updated_count = 0
    error_count = 0
    
    for repo_path, local_path in files_to_check:
        print(f"\n--- {local_path} ---")
        result = check_and_update_file(repo_path, local_path)
        results[local_path] = result
        
        if result['status'] == 'updated':
            updated_count += 1
        elif result['status'] == 'downloaded':
            updated_count += 1
        elif result['status'] == 'error':
            error_count += 1
        
        print(f"Status: {result['status']}")
    
    # Summary
    print("\n" + "=" * 50)
    print("UPDATE SUMMARY")
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

DEFAULT_IGNORE = ['__pycache__/', 'buildignore', '.DS_Store']


def parse_ignore_file(app_root):
    """Parse .ignore file in app directory and return list of patterns to exclude.
    Combines default ignore patterns with any patterns from the .ignore file.

    Args:
        app_root (str): Path to the app directory

    Returns:
        tuple: (ignored_files, ignored_dirs) - sets of filenames and directory names to ignore
    """
    ignored_files = set()
    ignored_dirs = set()

    # Add default ignored directories
    for pattern in DEFAULT_IGNORE:
        if pattern.endswith('/'):
            ignored_dirs.add(pattern.rstrip('/'))
        else:
            ignored_files.add(pattern)

    # Parse .ignore file if it exists
    ignore_path = os.path.join(app_root, 'buildignore')
    if os.path.isfile(ignore_path):
        with open(ignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.endswith('/'):
                    ignored_dirs.add(line.rstrip('/'))
                else:
                    ignored_files.add(line)
        print('Loaded .ignore file with {} file(s) and {} dir(s) to exclude'.format(
            len(ignored_files), len(ignored_dirs)))

    return ignored_files, ignored_dirs


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
# in DEV mode. Returns False and prints a message if
# the device is unreachable or not in dev mode.
def is_NCOS_device_in_DEV_mode():
    raw = get('/status/system/sdk/mode')
    if raw is None:
        print('\nERROR: Could not connect to NCOS device at {}.'.format(g_dev_client_ip))
        print('       Verify the device is powered on, reachable, and that')
        print('       sdk_settings.ini has the correct IP/credentials.')
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        print('\nERROR: Unexpected response from NCOS device at {}.'.format(g_dev_client_ip))
        return False
    mode = data.get('data', '')
    if mode == 'devmode':
        return True
    elif mode == 'standard':
        print('\nERROR: NCOS device at {} is not in Developer Mode.'.format(g_dev_client_ip))
        print('       Enable Dev Mode in NetCloud Manager: Tools > Developer Mode Devices.')
        return False
    else:
        print('\nERROR: Unexpected SDK mode ({}) on device at {}.'.format(mode, g_dev_client_ip))
        return False


# Returns the app package name based on the global app name.
def get_app_pack(app_name=None):
    package_name = (app_name or g_app_name) + ".tar.gz"
    if app_name is not None:
        package_name = app_name + ".tar.gz"
    return package_name


# Gets data from the NCOS config store
def get(config_tree):
    if requests is None:
        print("Error: 'requests' library is not installed. Run: pip install requests")
        return None

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

    # Search under apps/ directory for package.ini files (flat structure)
    apps_dir = os.path.join(cwd, 'apps')
    if os.path.isdir(apps_dir):
        for item in os.listdir(apps_dir):
            if item in ('templates', 'archive', '__pycache__', 'METADATA', '.git', '.venv'):
                continue
            item_path = os.path.join(apps_dir, item)
            if os.path.isdir(item_path) and os.path.isfile(os.path.join(item_path, 'package.ini')):
                app_dirs.append(item_path)
    else:
        # Fallback: look in cwd for flat structure (backward compat)
        dirs_in_cwd = os.listdir(cwd)
        for item in dirs_in_cwd:
            if os.path.isdir(item):
                contents = os.listdir(item)
                if 'package.ini' in contents:
                    app_dirs.append(item)

    # Also check repo root for apps in active development (created but not yet moved)
    dirs_in_cwd = os.listdir(cwd)
    for item in dirs_in_cwd:
        item_path = os.path.join(cwd, item)
        if os.path.isdir(item_path) and item not in ['apps', 'archive', 'docs', '.git', '.github', '.kiro', '.venv', '__pycache__']:
            if os.path.isfile(os.path.join(item_path, 'package.ini')):
                if item_path not in app_dirs:
                    app_dirs.append(item_path)

    # Warn about duplicate app names
    names_seen = {}
    for app_dir in app_dirs:
        name = os.path.basename(app_dir)
        if name in names_seen:
            print("WARNING: Duplicate app name '{}' found at:\n  {}\n  {}".format(
                name, names_seen[name], app_dir))
        else:
            names_seen[name] = app_dir

    return app_dirs


# Puts an SDK action in the NCOS device config store
def put(value):
    try:
        response = requests.put("https://{}/api/control/system/sdk/action".format(g_dev_client_ip),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=get_auth(),
                                data={"data": '"{} {}"'.format(value, get_app_uuid())},
                                verify=False)

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


def hash_dir(target, hash_func=hashlib.sha256, ignored_files=None, ignored_dirs=None):
    if ignored_files is None or ignored_dirs is None:
        ignored_files, ignored_dirs = parse_ignore_file(target)
    hashed_files = {}
    for path, d, f in os.walk(target):
        # Prune ignored directories in-place so os.walk won't descend into them
        d[:] = [x for x in d if x not in ignored_dirs]
        for fl in f:
            if fl in ignored_files:
                print("Ignored file: {}".format(fl))
                continue
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


def pack_package(app_root, app_name, ignored_files=None, ignored_dirs=None):
    if ignored_files is None or ignored_dirs is None:
        ignored_files, ignored_dirs = parse_ignore_file(app_root)

    def tar_filter(tarinfo):
        basename = os.path.basename(tarinfo.name)
        if tarinfo.isdir() and basename in ignored_dirs:
            return None
        if tarinfo.isfile() and basename in ignored_files:
            return None
        return tarinfo

    tar_name = f"{app_name}.tar"
    with tarfile.open(tar_name, 'w') as tar:
        tar.add(app_root, arcname=os.path.basename(app_root), filter=tar_filter)

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
            try:
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import padding
                with open(pkey, 'rb') as kf:
                    private_key = serialization.load_pem_private_key(kf.read(), password=None)
                signature = private_key.sign(checksum, padding.PKCS1v15(), hashes.SHA256())
                sf.write(signature)
            except ImportError:
                print("WARNING: 'cryptography' library not installed. Writing unsigned checksum.")
                sf.write(checksum)
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
        # Case-insensitive match between folder name and section name
        if os.path.basename(app_root).lower() != app_name.lower():
            continue

        clean_manifest_folder(app_metadata_folder)

        clean_bytecode_files(app_root)

        pmf = {}
        pmf['version_major'] = int(1)
        pmf['version_minor'] = int(0)
        pmf['version_patch'] = int(0)

        app = {}
        app['name'] = os.path.basename(app_root)
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

        ignored_files, ignored_dirs = parse_ignore_file(app_root)
        app['files'] = hash_dir(app_root, ignored_files=ignored_files, ignored_dirs=ignored_dirs)

        with open(app_manifest_file, 'w') as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

        create_signature(app_metadata_folder, pkey)

        app_name_version = f"{os.path.basename(app_root)} v{app['version_major']}.{app['version_minor']}.{app['version_patch']}"
        pack_package(app_root, app_name_version, ignored_files=ignored_files, ignored_dirs=ignored_dirs)

        print(f'Package {app_name_version}.tar.gz created')


# Package the app files into a tar.gz archive.
def package(app=None):
    app_name = app or g_app_name
    app_path = app_name

    # If app_name is not a directory, try to find it under apps/
    if not os.path.isdir(app_path):
        # Check apps/{app_name} directly (flat structure)
        candidate = os.path.join('apps', app_name)
        if os.path.isdir(candidate):
            app_path = candidate
        else:
            print("ERROR: App directory '{}' does not exist. Skipping.".format(app_name))
            return False

    # The app_name for packaging must match the folder basename
    actual_app_name = os.path.basename(app_path)

    # Verify the app has a valid package.ini with the correct section
    app_config_file = os.path.join(app_path, CONFIG_FILE)
    if not os.path.isfile(app_config_file):
        print("ERROR: '{}' not found in '{}'. Skipping.".format(CONFIG_FILE, app_path))
        return False

    config = configparser.ConfigParser()
    config.read(app_config_file)
    # Case-insensitive section lookup: find section matching folder name
    matched_section = None
    for section in config.sections():
        if section.lower() == actual_app_name.lower():
            matched_section = section
            break
    if matched_section is None:
        print("ERROR: The '{}' section does not exist in {}. Skipping.".format(actual_app_name, app_config_file))
        return False

    print("Packaging {}".format(actual_app_name))
    scan_for_cr(app_path)
    setup_script(app_path)

    try:
        package_application(app_path, None)
        return True
    except Exception as err:
        print('Error packaging {}: {}'.format(actual_app_name, err))
        return False


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

    # Create at repo root for easy dev iteration — move to apps/ when done
    target_dir = app_name

    if os.path.exists(target_dir):
        print('App already exists.  Please choose a different name.')
        return

    # Check if an app with this name already exists under apps/
    candidate = os.path.join('apps', app_name)
    if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'package.ini')):
        print(f'App already exists at {candidate}. Please choose a different name.')
        return

    # Find app_template
    template_path = os.path.join('apps', 'templates', 'app_template')
    if not os.path.isdir(template_path):
        # Fallback to old location
        template_path = 'app_template'
    if not os.path.isdir(template_path):
        print('ERROR: app_template not found.')
        return

    try:
        shutil.copytree(template_path, target_dir)
        os.rename(f'{target_dir}/app_template.py', f'{target_dir}/{app_name}.py')

        # Replace app_template with new app name in all files
        files = [f'{app_name}.py', 'package.ini', 'readme.md', 'start.sh']
        for file in files:
            path = f'{target_dir}/{file}'
            if os.path.isfile(path):
                with open(path, 'r') as in_file:
                    filedata = in_file.read()
                filedata = filedata.replace('app_template', app_name)
                with open(path, 'w') as out_file:
                    out_file.write(filedata)
        print(f'App {app_name} created at ./{app_name}/')
    except Exception as e:
        print(f'Error creating app: {e}')

# Transfer the app tar.gz package to the NCOS device
def install():
    if is_NCOS_device_in_DEV_mode():
        # Try to read version from package.ini in the app folder
        app_archive = None
        try:
            # Check multiple possible locations for package.ini
            candidates = [
                os.path.join(g_app_name, 'package.ini'),
                os.path.join('apps', g_app_name, 'package.ini'),
            ]
            package_ini_path = None
            for candidate in candidates:
                if os.path.isfile(candidate):
                    package_ini_path = candidate
                    break

            if package_ini_path:
                config = configparser.ConfigParser()
                config.read(package_ini_path)
                # Case-insensitive section lookup
                section_name = None
                for s in config.sections():
                    if s.lower() == g_app_name.lower():
                        section_name = s
                        break
                if section_name:
                    version_major = config[section_name].get('version_major', '0')
                    version_minor = config[section_name].get('version_minor', '0')
                    version_patch = config[section_name].get('version_patch', '0')
                    app_archive = f"{g_app_name} v{version_major}.{version_minor}.{version_patch}.tar.gz"
        except Exception:
            pass

        # Fallback: find any matching tar.gz
        if not app_archive or not os.path.exists(app_archive):
            import glob
            matches = glob.glob(f"{g_app_name}*.tar.gz") + glob.glob(f"{g_app_name} v*.tar.gz")
            if matches:
                app_archive = matches[0]
            else:
                app_archive = f"{g_app_name}.tar.gz"

        if not os.path.exists(app_archive):
            print('ERROR: Package file not found: {}'.format(app_archive))
            return 1

        print('Installing {} to {}...'.format(app_archive, g_dev_client_ip))

        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(g_dev_client_ip, username=g_dev_client_username,
                        password=g_dev_client_password,
                        look_for_keys=False, allow_agent=False, timeout=10)
            transport = ssh.get_transport()

            # Legacy SCP protocol — remote path MUST be /app_upload (no trailing slash)
            channel = transport.open_session()
            channel.exec_command('scp -t /app_upload')

            # Wait for ready signal
            response = channel.recv(1)
            if response != b'\x00':
                err = channel.recv(1024).decode(errors='replace') if channel.recv_ready() else ''
                print('ERROR: SCP not ready: {}'.format(err))
                return 1

            # Send file header
            file_size = os.path.getsize(app_archive)
            filename = os.path.basename(app_archive)
            header = 'C0644 {} {}\n'.format(file_size, filename)
            channel.sendall(header.encode())

            # Wait for header ack
            response = channel.recv(1)
            if response != b'\x00':
                err = channel.recv(1024).decode(errors='replace') if channel.recv_ready() else ''
                print('ERROR: SCP rejected file: {}'.format(err))
                return 1

            # Send file content
            with open(app_archive, 'rb') as f:
                while True:
                    data = f.read(32768)
                    if not data:
                        break
                    channel.sendall(data)

            # Send completion signal
            channel.sendall(b'\x00')
            channel.close()
        except (EOFError, OSError, paramiko.ssh_exception.SSHException):
            # Router drops connection after receiving file — expected
            pass
        except Exception as e:
            print('ERROR: Upload failed: {}'.format(e))
            return 1
        finally:
            ssh.close()

        return 0
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to install the app into {}.'.format(g_dev_client_ip))
        return 1


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
        result = put('purge')
        if result:
            try:
                data = json.loads(result)
                if data.get('success'):
                    print('Purge successful on {}.'.format(g_dev_client_ip))
                    return
            except (json.JSONDecodeError, TypeError):
                pass
            print('Purge failed on {}.'.format(g_dev_client_ip))
        else:
            print('Purge failed on {}.'.format(g_dev_client_ip))
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to purge the app from {}.'.format(g_dev_client_ip))

def deploy():
    """Full deploy: purge, build, install, and show recent logs."""
    print('Purging apps from {}...'.format(g_dev_client_ip))
    purge()
    time.sleep(3)

    if not package():
        print('ERROR: Packaging failed.')
        return

    result = install()
    if result != 0:
        print('ERROR: Install failed.')
        return

    # Wait for the app to start, then show all recent logs
    time.sleep(5)
    try:
        log_url = 'https://{}/api/status/log/'.format(g_dev_client_ip)
        response = requests.get(log_url, auth=get_auth(), verify=False)
        logs = json.loads(response.text).get('data', [])
        cutoff = time.time() - 7
        recent = [e for e in logs if e[0] >= cutoff]
        if recent:
            print('Logs:')
            for entry in recent:
                ts = datetime.datetime.fromtimestamp(entry[0]).strftime('%H:%M:%S')
                facility = entry[2] if len(entry) > 2 else ''
                msg = entry[3] if len(entry) > 3 and entry[3] else ''
                print('  {} [{}] {}'.format(ts, facility, msg))
        else:
            print('  No log entries in the last 7 seconds.')
    except Exception as e:
        print('Warning: Could not fetch logs: {}'.format(e))

def setup():
    """Create .venv and install requirements.txt."""
    setup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'setup_env.py')
    subprocess.run([sys.executable, setup_script], check=True)




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
    print('deploy: Purge, build, install, and show logs in one step.\n')
    print('setup: Create .venv and install requirements.txt.\n')
    print('uuid: Create a UUID for the app and save it to the package.ini file.\n')
    print('update: Check and update core SDK files from GitHub repository.\n')
    print('\tUpdates: make.py and apps/templates/app_template/cp.py\n')
    print('unit: Run any unit tests associated with selected app.\n')
    print('system: Run any system tests associated with selected app.\n')
    print('help: Print this help information.\n')


# Get the uuid from application package.ini if not already set
def get_app_uuid():
    global g_app_uuid

    if g_app_uuid == '':
        uuid_key = 'uuid'
        app_config_file = os.path.join(g_app_name, 'package.ini')

        if not os.path.isdir(g_app_name):
            return g_app_uuid

        if not os.path.isfile(app_config_file):
            return g_app_uuid

        config = configparser.ConfigParser()
        config.read(app_config_file)
        # Case-insensitive section lookup
        section_name = None
        for s in config.sections():
            if s.lower() == g_app_name.lower():
                section_name = s
                break
        if section_name:
            if uuid_key in config[section_name]:
                g_app_uuid = config[section_name][uuid_key]

                if g_app_uuid == '':
                    # Create a UUID if it does not exist
                    _uuid = str(uuid.uuid4())
                    config.set(section_name, uuid_key, _uuid)
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
    # Also check parent directories (in case running from a subdirectory)
    if not os.path.isfile(settings_file):
        # Walk up to find sdk_settings.ini
        check_dir = os.path.dirname(os.getcwd())
        for _ in range(3):
            candidate = os.path.join(check_dir, 'sdk_settings.ini')
            if os.path.isfile(candidate):
                settings_file = candidate
                break
            check_dir = os.path.dirname(check_dir)

    config = configparser.ConfigParser()
    config.read(settings_file)

    # Initialize the globals based on the sdk_settings.ini contents.
    if sdk_key in config:
        if app is not None:
            g_app_name = os.path.basename(app.rstrip('/'))
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

    if utility_name in ['clean', 'package', 'build', 'uuid', 'status', 'start', 'stop', 'install', 'uninstall', 'purge', 'update', 'deploy']:
        # Load the settings from the sdk_settings.ini file.
        if not init(option):
            sys.exit(0)
        if utility_name not in ['install', 'purge']:
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

    elif utility_name == 'deploy':
        deploy()

    elif utility_name == 'setup':
        setup()

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
