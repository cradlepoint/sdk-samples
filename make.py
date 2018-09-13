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

from requests.auth import HTTPDigestAuth

# These will be set in init() by using the sdk_settings.ini file.
# They are used by various functions in the file.
g_app_name = ''
g_app_uuid = ''
g_dev_client_ip = ''
g_dev_client_username = ''
g_dev_client_password = ''
g_python_cmd = 'python3'  # Default for Linux and OS X


# Returns the proper HTTP Auth for the global username and password.
# Digest Auth is used for NCOS 6.4 and below while Basic Auth is
# used for NCOS 6.5 and up.
def get_auth():
    from http import HTTPStatus

    use_basic = False
    device_api = 'http://{}/api/status/product_info'.format(g_dev_client_ip)

    try:
        response = requests.get(device_api, auth=requests.auth.HTTPBasicAuth(g_dev_client_username, g_dev_client_password))
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
    package_name = g_app_name + ".tar.gz"
    if app_name is not None:
        package_name = app_name + ".tar.gz"
    return package_name


# Gets data from the NCOS config store
def get(config_tree):
    ncos_api = 'http://{}/api/{}'.format(g_dev_client_ip, config_tree)

    try:
        response = requests.get(ncos_api, auth=get_auth())

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
        response = requests.put("http://{}/api/control/system/sdk/action".format(g_dev_client_ip),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=get_auth(),
                                data={"data": '"{} {}"'.format(value, get_app_uuid())})

        print('status_code: {}'.format(response.status_code))

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with put for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None

    return json.dumps(json.loads(response.text), indent=4)


# Cleans the SDK directory for a given app by removing files created during packaging.
def clean(app=None):
    app_name = g_app_name
    if app is not None:
        app_name = app
    print("Cleaning {}".format(app_name))
    app_pack_name = get_app_pack(app_name)
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
            with open(os.path.join(root, fl), 'rb') as f:
                if b'\r' in f.read() and [x for x in scanfiles if fl.endswith(x)]:
                    raise Exception('Carriage return (\\r) found in file %s' % (os.path.join(root, fl)))

# Package the app files into a tar.gz archive.
def package():
    print("Packaging {}".format(g_app_name))
    success = True
    package_dir = os.path.join('tools', 'bin')
    package_script_path = os.path.join('tools', 'bin', 'package_application.py')
    app_path = os.path.join(g_app_name)
    scan_for_cr(app_path)

    try:
        subprocess.check_output('{} {} {}'.format(g_python_cmd, package_script_path, app_path), shell=True)
    except subprocess.CalledProcessError as err:
        print('Error packaging {}: {}'.format(g_app_name, err))
        success = False
    finally:
        return success


# Package all the app files in the directory into a tar.gz archives.
def package_all():
    success = True
    cwd = os.getcwd()
    print("Scanning {} for app directories.".format(cwd))
    app_dirs = get_app_list()

    package_script_path = os.path.join('tools', 'bin', 'package_application.py')
    for app in app_dirs:
        app_path = os.path.join(app)
        scan_for_cr(app_path)
        try:
            print('Build app: {}'.format(app_path))
            subprocess.check_output('{} {} {}'.format(g_python_cmd, package_script_path, app_path), shell=True)
        except subprocess.CalledProcessError as err:
            print('Error packaging {}: {}'.format(app_path, err))
            success = False

    return success


# Get the SDK status from the NCOS device
def status():
    status_tree = '/status/system/sdk'
    print('Get {} status for NCOS device at {}'.format(status_tree, g_dev_client_ip))
    response = get(status_tree)
    print(response)


# Transfer the app app tar.gz package to the NCOS device
def install():
    if is_NCOS_device_in_DEV_mode():
        app_archive = get_app_pack()

        # Use sshpass for Linux or OS X
        cmd = 'sshpass -p {0} scp {1} {2}@{3}:/app_upload'.format(
               g_dev_client_password, app_archive,
               g_dev_client_username, g_dev_client_ip)

        # For Windows, use pscp.exe in the tools directory
        if sys.platform == 'win32':
            cmd = "./tools/bin/pscp.exe -pw {0} -v {1} {2}@{3}:/app_upload".format(
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
        print('Purged application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('purge')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to purge the app from {}.'.format(g_dev_client_ip))


# Prints the help information
def output_help():
    print('Command format is: {} make.py <action>\n'.format(g_python_cmd))
    print('Actions include:')
    print('================')
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
    print('unit: Run any unit tests associated with selected app.\n')
    print('system: Run any system tests associated with selected app.\n')
    print('help: Print this help information.\n')


# Get the uuid from application package.ini if not already set
def get_app_uuid(ceate_new_uuid=False):
    global g_app_uuid

    if g_app_uuid == '':
        uuid_key = 'uuid'
        app_config_file = os.path.join(g_app_name, 'package.ini')
        config = configparser.ConfigParser()
        config.read(app_config_file)
        if g_app_name in config:
            if uuid_key in config[g_app_name]:
                g_app_uuid = config[g_app_name][uuid_key]

                if ceate_new_uuid or g_app_uuid == '':
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
def init(ceate_new_uuid):
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
        if app_key in config[sdk_key]:
            g_app_name = config[sdk_key][app_key]
        else:
            success = False
            print('ERROR 1: The {} key does not exist in {}'.format(app_key, settings_file))

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

    # This will also create a UUID if needed.
    get_app_uuid(ceate_new_uuid)

    return success


if __name__ == "__main__":
    # Default is no arguments given.
    if len(sys.argv) < 2:
        output_help()
        sys.exit(0)

    utility_name = str(sys.argv[1]).lower()
    option = None
    if len(sys.argv) > 2:
        option = str(sys.argv[2]).lower()

    if not init(ceate_new_uuid=utility_name == 'uuid'):
        sys.exit(0)

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
