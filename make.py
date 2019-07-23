'''
This is the NCOS SDK tool used to created applications
for Cradlepoint NCOS devices. It will work on Linux,
OS X, and Windows once the computer environment is setup.
'''

import os
import sys
import uuid
import logging
import json
import shutil
import requests
import subprocess
import configparser
import unittest
import urllib3
urllib3.disable_warnings()

from requests.auth import HTTPDigestAuth
from tools.bin import package_application


logger = logging.getLogger(__name__)

# These will be set in init() by using the sdk_settings.ini file.
# They are used by various functions in the file.
g_app_name = ''
g_app_uuid: str = ''
g_dev_client_ip = ''
g_dev_client_username = ''
g_dev_client_password = ''


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


def is_NCOS_device_in_devmode(func):
    """
    Raises an exception if NCOS device is not in devmode
    """
    def wrapper():
        sdk_status = json.loads(get('/status/system/sdk')).get('data')
        if sdk_status.get('mode') != 'devmode':
            raise RuntimeError('Router not in devmode')
        func()
    return wrapper


# Returns the app package name based on the global app name.
def get_app_pack(app_name=None, dist_path=None):
    package_name = g_app_name + ".tar.gz"
    if app_name is not None:
        package_name = app_name + ".tar.gz"
    if dist_path:
        package_name = os.path.join(dist_path, package_name)
    return package_name


# Gets data from the NCOS config store
def get(config_tree):
    ncos_api = 'https://{}/api{}'.format(g_dev_client_ip, config_tree)
    try:
        response = requests.get(ncos_api,
                                auth=get_auth(),
                                verify=False)

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with get for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None
    return json.dumps(json.loads(response.text), indent=4)


def put(value):
    """
    Puts an SDK action in the NCOS device config store
    :param value:
    :return:
    """
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


def clean(app_name=None):
    """
    Cleans the SDK directory for a given app by removing files created during packaging.
    :param app_name:
    :return:
    """
    global g_app_name
    if not app_name:
        app_name = g_app_name
    print("Cleaning app: {}".format(app_name))
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


def scan_for_cr(path):
    scanfiles = ('.py', '.sh')
    for root, _, files in os.walk(path):
        for fl in files:
            with open(os.path.join(root, fl), 'rb') as f:
                if b'\r' in f.read() and [x for x in scanfiles if fl.endswith(x)]:
                    raise Exception('Carriage return (\\r) found in file %s' % (os.path.join(root, fl)))


def package():
    """
    Package the app files into a tar.gz archive.
    """
    print("Packaging {}".format(g_app_name))
    app_path = os.path.join(g_app_name)
    new_package(app_path, None)


def new_package(build_path, dist_path):
    scan_for_cr(build_path)
    package_application.package_application(build_path, None, dist_path=dist_path)


# Get the SDK status from the NCOS device
def status():
    status_tree = '/status/system/sdk'
    print('Get {} status for NCOS device at {}'.format(status_tree, g_dev_client_ip))
    response = get(status_tree)
    print(response)


@is_NCOS_device_in_devmode
def install(dist_path=None):
    """
    Transfer the app app tar.gz package to the NCOS device
    :param dist_path: path to folder where zip file lives.
    """
    app_archive = get_app_pack(dist_path=dist_path)

    # Use sshpass for Linux or OS X
    cmd = 'sshpass -p {0} scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {1} {2}@{3}:/app_upload'.format(
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
        pass


@is_NCOS_device_in_devmode
def start():
    """
    Start the app in the NCOS device
    """
    print('Start application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
    print('Application UUID is {}.'.format(g_app_uuid))
    response = put('start')
    print(response)


@is_NCOS_device_in_devmode
def stop():
    """
    Stop the app in the NCOS device
    """
    print('Stop application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
    print('Application UUID is {}.'.format(g_app_uuid))
    response = put('stop')
    print(response)


@is_NCOS_device_in_devmode
def uninstall():
    """
    Uninstall the app from the NCOS device
    """
    print('Uninstall application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
    print('Application UUID is {}.'.format(g_app_uuid))
    response = put('uninstall')
    print(response)


@is_NCOS_device_in_devmode
def purge():
    """
    Purge the app from the NCOS device
    """
    print('Purged application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
    print('Application UUID is {}.'.format(g_app_uuid))
    response = put('purge')
    print(response)


# Prints the help information
def output_help():
    print('Command format is: python3 make.py <action>\n')
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


class AppBuilder:

    # Setup all the globals based on the OS and the sdk_settings.ini file.
    def __init__(self, ceate_new_uuid):
        global g_app_name
        global g_dev_client_ip
        global g_dev_client_username
        global g_dev_client_password

        # Keys in sdk_settings.ini
        sdk_key = 'sdk'
        app_key = 'app_name'
        ip_key = 'dev_client_ip'
        username_key = 'dev_client_username'
        password_key = 'dev_client_password'

        if sys.platform == 'Darwin':
            # This will exclude the '._' files  in the
            # tar.gz package for OS X.
            os.environ["COPYFILE_DISABLE"] = "1"

        settings_file = os.path.join(os.path.dirname(__file__), 'sdk_settings.ini')
        config = configparser.ConfigParser()
        config.read(settings_file)

        # Initialize the globals based on the sdk_settings.ini contents.
        g_app_name = config[sdk_key][app_key]
        g_dev_client_ip = config[sdk_key][ip_key]
        g_dev_client_username = config[sdk_key][username_key]
        g_dev_client_password = config[sdk_key][password_key]

        # This will also create a UUID if needed.
        get_app_uuid(ceate_new_uuid)


def unit_tests():
    # load any tests in app/test/unit
    app_test_path = os.path.join(g_app_name, 'test', 'unit')
    suite = unittest.defaultTestLoader.discover(app_test_path)
    # change to the app dir so app files can be properly imported
    os.chdir(g_app_name)
    # add the current path to sys path so we can directly import
    sys.path.append(os.getcwd())
    # run suite
    unittest.TextTestRunner().run(suite)


def system_tests():
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


UTILITY_PROCESSES = {
    'redeploy': [clean, uninstall, package, install],
    'clean': [clean],
    'package': [clean, package],
    'build': [clean, package],
    'status': [status],
    'install': [uninstall, install],
    'start': [start],
    'stop': [stop],
    'uninstall': [uninstall],
    'purge': [purge],
    'uuid': [], #handled by AppBuilder constructor
    'unit': [unit_tests],
    'system': [system_tests]

}


def main():
    logging.basicConfig(level=logging.INFO)
    # Default is no arguments given.
    if len(sys.argv) < 2:
        output_help()
        sys.exit(0)

    utility_name = str(sys.argv[1]).lower()

    AppBuilder(ceate_new_uuid=utility_name == 'uuid')

    try:
        processes = UTILITY_PROCESSES[utility_name]
    except KeyError:
        output_help()
        return

    for process in processes:
        process()


if __name__ == "__main__":
    main()
