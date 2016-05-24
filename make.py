
import logging
import os
import os.path
import shutil
import subprocess
import sys
import time

# these must be added, pulled in by pip
# import requests
# import requests.exceptions
# from requests.auth import HTTPDigestAuth

from tools.copy_file_nl import copy_file_nl
import cp_lib.app_name_parse as app_name_parse
from cp_lib.app_base import CradlepointAppBase
from cp_lib.cs_ping import cs_ping

SDIR_CONFIG = "config"
SDIR_BUILD = "build"

# used for make options which don't need name (that assume 'any app' on
# router or in ./build
DEF_DUMMY_NAME = "make"

FILE_NAME_INSTALL = "install.sh"
FILE_NAME_START = "start.sh"
FILE_NAME_MAIN = "main.py"
FILE_NAME_UUID = "_last_uuid.txt"

SCP_USER_DEFAULT = "admin"
WIN_SCP_NAME = "./tools/pscp.exe"

# def is for Linux
DEF_SCP_NAME = "scp"

# set False means SCP will ask for apssword always; True means SSHPASS is used
# to feed password from ./config/settings.ini
USE_SSH_PASS = True

# codes returned by Router API access which fails
EXIT_CODE_NO_DATA = -20099
EXIT_CODE_NO_RESPONSE = -20098
EXIT_CODE_BAD_FORM = -20097
EXIT_CODE_NO_APPS = -20096
EXIT_CODE_MISSING_DEP = -20095
EXIT_CODE_BAD_ACTION = -20094

# allow a quicker timeout since we are talking LOCALLY only, so default is
# unnecessarily long
API_REQUESTS_TIMEOUT = 2.0

# any file in app directory starting with this is skipped, set to None to
# NOT skip any
SKIP_PREFACE_CHARACTER = '.'


class TheMaker(CradlepointAppBase):

    SDIR_SAVE_EXT = ".save"

    ACTION_DEFAULT = "package"
    ACTION_NAMES = ("build", "package", "status", "install", "start",
                    "stop", "uninstall",
                    "purge", "uuid", "reboot", "clean", "ping")
    ACTION_HELP = {
        "build": "Alias for 'package'.",
        "package": "Create the application archive tar.gz file.",
        "status": "Print current SDK app status from locally connected router",
        "install": "Secure copy the application archive to a locally connect" +
                   "ed router. The router must already be in SDK DEV mode " +
                   "via registration and licensing in ECM.",
        "start": "Start the application on the locally connected router.",
        "stop": "Stop the application on the locally connected router.",
        "uninstall": "Uninstall the application from locally connected router",
        "purge": "Purge all applications from the locally connected router.",
        "uuid": "Issue status to router, display any UUID installed",
        "reboot": "Reboot your router",
        "clean": "delete temp build files",
        "ping": "ask router to ping a local IP"
    }

    ACTION_CALL_TO_ROUTER = ("status", "install", "start", "stop",
                             "uninstall", "purge", "uuid", "reboot", "ping")
    ACTION_NEED_UUID = ("start", "stop", "uninstall")

    SETS_DEFAULT_USER_NAME = "admin"

    # could also set to be os.sep, if you like. But Windows accepts Linux style
    DEF_SEP = '/'

    def __init__(self):
        """Basic Init"""
        from cp_lib.load_settings_ini import copy_config_ini_to_json

        # make sure we have at least a basic ./config/settings.json
        # ALWAYS copy existing ./config/settings.ini over, which makes
        # CradlepointAppBase.__init__() happy
        copy_config_ini_to_json()

        # we don't contact router for model/fw - will do in sanity_check, IF
        # the command means contact router
        CradlepointAppBase.__init__(self, call_router=False, log_name="make")

        # 'attrib' are our internal pre-processed settings for MAKE use
        self.attrib = {}

        self.command = "make"
        self.action = self.ACTION_DEFAULT

        # these are in CradlepointAppBase
        # self.run_name = None  # like "network/tcp_echo/__init__.py"
        # self.app_path = None  # like "network/tcp_echo/", used to find files
        # self.app_name = None  # like "tcp_echo"
        # self.mod_name = None  # like "network.tcp_echo", used for importlib
        # self.settings = load_settings_json(self.app_path)
        # self.logger = get_recommended_logger(self.settings)
        # self.cs_client = init_cs_client_on_my_platform(self.logger,
        #                                                self.settings)

        # should MAKE edit/change the [app][version] in setting.ini?
        self.increment_version = False

        # are we building for running on PC? Then don't include PIP add-ins
        self.ignore_pip = False

        # define LOGGING between DEBUG or INFO
        self.verbose = False

        self.last_url = None
        self.last_reply = None
        self.last_status = None
        self._last_uuid = None

        self._exclude = []

        return

    def run(self):
        """Dummy to satisfy CradlepointAppBase"""
        return

    def main(self):
        """

        :return int: code for sys.exit()
        """
        from cp_lib.load_settings_ini import load_sdk_ini_as_dict

        self.logger.debug("Make:, Action:{0}, Name:{1}".format(self.action,
                                                               self.app_path))

        # handle diverse app_path
        if self.app_path is not None:
            assert isinstance(self.app_path, str)
            # make sure is Linux-style PATH, not Windows nor 'dot' module name
            self.app_path = app_name_parse.get_app_path(self.app_path,
                                                        self.DEF_SEP)
            self.app_name = app_name_parse.get_app_name(self.app_path)
            self.mod_name = app_name_parse.get_module_name(self.app_path)

        # load the base config from raw INI. These are use of all actions,
        #  but not BUILD/PACKAGE
        self.settings = load_sdk_ini_as_dict(self.app_path)

        # confirm we have the APP PATH set okay
        if self.app_path is None:
            # without a path, might be just checking router status, etc
            self.attrib["path"] = DEF_DUMMY_NAME
            self.attrib["name"] = DEF_DUMMY_NAME
            self.app_path = DEF_DUMMY_NAME

        else:  # assume was passed in commandline
            self.attrib["name"] = self.app_name
            self.attrib["path"] = self.app_path

        # throws exception if environment is not sane & cannot be made sane
        self.sanity_check_environment()

        self.action = self.action.lower()
        if self.action in ("build", "package"):
            # go to our router & check status
            return self.action_package()

        elif self.action == "status":
            # go to our router & check status
            return self.action_status(verbose=True)

        elif self.action == "install":
            # try to send our TAR.GZIP to our router
            return self.action_install(self.app_path)

        elif self.action == "start":
            # go to our router & start (if installed?)
            return self.action_start()

        elif self.action == "stop":
            # go to our router & stop (if running?)
            return self.action_stop()

        elif self.action == "uninstall":
            # go to our router & do an install
            return self.action_uninstall()

        elif self.action == "purge":
            # go to our router & force a purge
            return self.action_purge()

        elif self.action == "uuid":
            # go to our router & check UUID in status
            return self.action_get_uuid_from_router()

        elif self.action == "reboot":
            # go to our router & force a reboot
            return self.action_reboot()

        elif self.action == "clean":
            # delete temp build files
            return self.action_clean()

        elif self.action == "ping":
            # delete temp build files
            return self.action_ping(self.app_path)

        else:
            raise ValueError("Unsupported Command:" + self.action)

    def get_app_name(self):
        """Return the path for the app files"""
        return self.settings["application"]["name"]

    def get_app_path(self):
        """Return the path for the app files"""
        if "path" in self.attrib:
            return self.attrib["path"]
        raise KeyError("App Path attrib is missing")

    def get_build_path(self):
        """Return the path for the app files - force Linux format"""
        if "build" not in self.attrib:
            # self.attrib["build"] = os.path.join(SDIR_BUILD,
            #                                     self.get_app_name())
            self.attrib["build"] = SDIR_BUILD + '/' + self.get_app_name() + '/'
        return self.attrib["build"]

    def get_main_file_name(self):
        """Return the MAIN file name to run"""
        if "main_file_name" in self.attrib:
            return self.attrib["main_file_name"]
        else:
            return FILE_NAME_MAIN

    def get_router_ip(self):
        return self.settings["router_api"]["local_ip"]

    def get_router_password(self):
        return self.settings["router_api"]["password"]

    def get_router_user_name(self):
        try:
            return self.settings["router_api"]["user_name"]
        except KeyError:
            return "admin"

    def sanity_check_environment(self):
        """
        Confirm the basic directories do exist - such as ./config

        :return None: Throws an exception if it fails
        """
        from cp_lib.load_product_info import load_product_info
        from cp_lib.load_firmware_info import load_firmware_info

        # confirm ./config exists and is not a file
        self._confirm_dir_exists(SDIR_CONFIG, "CONFIG dir")

        if "path" not in self.attrib:
            raise KeyError("SDK App Path missing in attributes")

        if "name" not in self.attrib:
            raise KeyError("SDK App Name missing in attributes")

        # fussy neatness - force Linux to propagate to - ["path"]
        self.attrib["path"] = app_name_parse.normalize_path_separator(
            self.attrib["path"], self.DEF_SEP)

        if self.action in self.ACTION_CALL_TO_ROUTER:
            self.logger.info("sets:{}".format(self.settings))
            # then check for Model & firmware
            save_value = self.cs_client.show_rsp
            self.cs_client.show_rsp = False
            self.settings = load_product_info(self.settings, self.cs_client)
            self.settings = load_firmware_info(self.settings, self.cs_client)
            # print(json.dumps(self.settings, ensure_ascii=True, indent=4))
            self.cs_client.show_rsp = save_value

            self.logger.info("Cradlepoint router is model:{}".format(
                self.settings["product_info"]["product_name"]))
            self.logger.info("Cradlepoint router FW version:{}".format(
                self.settings["fw_info"]["version"]))

        if self.action in self.ACTION_NEED_UUID:
            # these need the UUID
            if "uuid" not in self.attrib:
                # then try to read the ./config/last_uuid.txt file
                data = self._read_uid_file()
                if data is not None:
                    self.logger.debug("last_uuid=({})".format(data))
                    self.attrib["uuid"] = data

                # else:
                #     raise KeyError("SDK UUID missing in attributes")

        return

    def _delete_uid(self):
        """Delete any saved UUID file - ./config/_last_uuid.txt"""
        file_name = os.path.join(SDIR_CONFIG, FILE_NAME_UUID)
        if os.path.exists(file_name):
            self.logger.debug("Delete {}".format(file_name))
            os.remove(file_name)
        return

    def _read_uid_file(self):
        """Read / load a saved UUID from file - ./config/_last_uuid.txt"""
        file_name = os.path.join(SDIR_CONFIG, FILE_NAME_UUID)
        if os.path.exists(file_name):
            file_han = open(file_name, "r")
            data = file_han.read().strip()
            file_han.close()
            self.logger.debug("Read {} saw {}.".format(file_name, data))
            return data
        else:
            self.logger.debug("Read {} failed - does not exist.".format(
                file_name))

        return None

    def _write_uid(self, data: str):
        """Write / dump a saved UUID to file - ./config/_last_uuid.txt"""
        assert isinstance(data, str)

        file_name = os.path.join(SDIR_CONFIG, FILE_NAME_UUID)
        self.logger.debug("Write {} with {}".format(file_name, data))
        file_han = open(file_name, "w")
        file_han.write(data)
        file_han.close()
        return

    def action_package(self):
        """
        Build the actual package, copying to build

        :return int: value intended for sys.exit()
        """
        import tools.make_load_settings
        import cp_lib.load_settings_ini
        from tools.module_dependency import BuildDependencyList
        from tools.make_package_ini import make_package_ini
        from tools.package_application import package_application

        if self.attrib["name"] == DEF_DUMMY_NAME:
            self.logger.error("Cannot build - no app_path given")
            sys.exit(-1)

        self.logger.info("Building Package({0}) in dir({1}))".format(
            self.attrib["name"], self.attrib["path"]))

        # confirm PATH exists!
        if not os.path.isdir(self.attrib["path"]):
            raise FileNotFoundError(
                "Cannot build - app_path({}) is invalid".format(
                    self.attrib["path"]))

        # does nothing - just create so we can add files to it
        dep_list = BuildDependencyList()
        dep_list.ignore_pip = self.ignore_pip
        dep_list.logger = self.logger

        # confirm ./build exists and is not a file
        dst_file_name = SDIR_BUILD
        self.logger.debug("Confirm ./{} exists and is empty".format(
            dst_file_name))
        if os.path.isdir(dst_file_name):
            try:
                shutil.rmtree(dst_file_name, ignore_errors=True)
            except OSError:
                self.logger.error(
                    "Could not delete OLD ./" +
                    "{} - have you open files there?".format(dst_file_name))
                raise

        # confirm .build/{app_name} exists
        dst_file_name = self.get_build_path()
        self.logger.debug("Confirm ./{} exists".format(dst_file_name))
        self._confirm_dir_exists(dst_file_name, "BUILD dir")

        # start with the SETTINGS:
        # make sure has [application] section, plus "uuid" and "version"
        self.logger.info("Confirm App INI has required UUID and Version")
        tools.make_load_settings.validate_project_settings(
            self.get_app_path(), self.increment_version)

        # ./config/settings.ini then {app_path}/settings.ini
        #  (again, as UUID might have changed)
        self.settings = tools.make_load_settings.load_settings(
            self.get_app_path())

        # save as ./build/{project}/settings.json
        dst_file_name = os.path.join(
            self.get_build_path(),
            cp_lib.load_settings_ini.DEF_SETTINGS_FILE_NAME +
            cp_lib.load_settings_ini.DEF_JSON_EXT)
        cp_lib.load_settings_ini.save_root_settings_json(self.settings,
                                                         dst_file_name)

        # exclude the APP ini and json - save_root_settings_json() made
        # a combined copy
        app_file_name = os.path.join(
            self.app_path,
            cp_lib.load_settings_ini.DEF_SETTINGS_FILE_NAME +
            cp_lib.load_settings_ini.DEF_INI_EXT)
        self._exclude.append(app_file_name)
        app_file_name = os.path.join(
            self.app_path,
            cp_lib.load_settings_ini.DEF_SETTINGS_FILE_NAME +
            cp_lib.load_settings_ini.DEF_JSON_EXT)
        self._exclude.append(app_file_name)

        # do/copy over the SH files to BUILD, these have no dependencies
        self.create_install_sh()
        self.create_start_sh()

        # this will create a simple Windows batch file
        self.create_go_bat()

        # handle the main.py
        # GLOBAL = ./config/main.py
        glob_file_name = os.path.join(SDIR_CONFIG, self.get_main_file_name())
        # APP = ./{app_project}/main.py
        app_file_name = os.path.join(self.get_app_path(),
                                     self.get_main_file_name())
        # DST = ./build/{app_name}/main.py
        dst_file_name = os.path.join(self.get_build_path(),
                                     self.get_main_file_name())

        if os.path.exists(app_file_name):
            # if app developer supplies one, use it (TDB - do pre-processing)
            # for example, copy "network/tcp_echo/main.py" to "build/main.py"
            self.logger.info("Copy existing APP MAIN from [{}]".format(
                app_file_name))
            copy_file_nl(app_file_name, dst_file_name)
            # sh util.copyfile(app_file_name, dst_file_name)
            # make sure we add any required files from cp_lib
            dep_list.add_file_dependency(app_file_name)

            # we exclude it as "app_dir/main.py", because it will be
            # in archive as ./main.py!
            self.logger.debug("Add file [{}] to exclude list".format(
                app_file_name))
            self._exclude.append(app_file_name)

        elif os.path.exists(glob_file_name):
            # if root supplies one, use it (TDB - do pre-processing)
            self.logger.info("Copy existing ROOT MAIN from [{}]".format(
                glob_file_name))
            copy_file_nl(glob_file_name, dst_file_name)
            # sh util.copyfile(glob_file_name, dst_file_name)

            # make sure we add any required files from cp_lib
            dep_list.add_file_dependency(glob_file_name)

        else:
            raise ValueError("\'main\' script is missing!")

        # sys.exit(-99)

        # all will use this?
        # file_name = os.path.join("cp_lib", "app_base.py")
        # dep_list.add_file_dependency(file_name)
        #
        # dep_list.add_if_new("cp_lib.__init__")

        # make a list of files in app_dir, copy them to BUILD,
        # plus collect dependency list
        file_list = os.listdir(self.get_app_path())
        dst_path_name = os.path.join(self.get_build_path(),
                                     self.get_app_path())
        self._confirm_dir_exists(dst_path_name, "Project Directory")

        for file_name in file_list:

            if file_name[0] == SKIP_PREFACE_CHARACTER:
                # if file starts with '.', skip -
                # set SKIP_PREFACE_CHARACTER == None to skip this
                self.logger.debug("skip due to SKIP preface:{}".format(
                    file_name))
                continue

            path_name = os.path.join(self.get_app_path(), file_name)

            if os.path.isdir(path_name):
                # handle any sub-directories (TBD)

                if file_name in ("__pycache__", "test"):
                    self.logger.debug("skip sdir:[{}]".format(path_name))
                    pass

                else:  # TODO - recurse into it
                    self.logger.debug("see app sdir:[{}]".format(path_name))

            elif os.path.isfile(path_name):
                # handle any files
                # self.logger.debug("see app file:[{}]".format(path_name))
                if path_name in self._exclude:
                    self.logger.debug("skip file:[{}]".format(path_name))

                else:
                    # make sure we add any required files from cp_lib
                    dep_list.add_file_dependency(path_name)

                    dst_file_name = os.path.join(
                        self.get_build_path(),
                        self.get_app_path(), file_name)

                    # self.logger.debug("Make Dir [{0}]".format(dst_path_name))
                    self._confirm_dir_exists(dst_path_name, "File to Build")

                    self.logger.debug("Copy file [{0}] to {1}".format(
                        path_name, dst_file_name))
                    # note: copyfile requires 2 file names - 2nd cannot
                    # be a directory destination, we'll skip EMPTY files
                    copy_file_nl(path_name, dst_file_name, discard_empty=True)
                    # sh util.copyfile(path_name, dst_file_name)

        # copy everything from app_dir to build
        for source in dep_list.dep_list:
            self.logger.info("Copy Over Dependency {0}".format(source))
            self.copy_dep_name_to_build(source)

        # handle the package.ini
        file_name = os.path.join(self.get_build_path(), "package.ini")
        self.logger.debug("Make {}".format(file_name))
        make_package_ini(self.settings, file_name)

        # propagate to MANIFEST.json
        package_application(self.get_build_path(), pkey=None)

        return 0

    def copy_dep_name_to_build(self, source_file_name, fix_form=True):
        """
        Given a file name from an import (like "cp_lib.cp_logging"), which
        we assume is a .PY/python file, copy it to the build directory
        - such as "build/cp_lib/cp_logging.py"

        :param str source_file_name:
        :param bool fix_form: True if source is like "cp_lib.cp_logging",
                              False to treat as final
        :return:
        """
        assert isinstance(source_file_name, str)
        if fix_form:
            # convert "cp_lib.cp_logging" to "cp_lib/cp_logging.py"
            if source_file_name.endswith(".py"):
                # assume is already okay
                pass
            # TODO - fix this! How?
            elif source_file_name.endswith(".ico"):
                # assume is already okay
                pass
            elif source_file_name.endswith(".jpg"):
                # assume is already okay
                pass
            elif source_file_name.endswith(".md"):
                # assume is already okay
                return
            elif source_file_name.endswith(".ini"):
                # assume is already okay
                return
            else:
                source_file_name = source_file_name.replace(
                    '.', self.DEF_SEP) + ".py"

        # make up the destination as "build/cp_lib/cp_logging.py"
        build_file_name = os.path.join(self.get_build_path(), source_file_name)

        # breaks into ["build/cp_lib", "cp_logging.py"], make sure it exists
        path_name = os.path.split(build_file_name)
        self._confirm_dir_exists(path_name[0], "Dep 2 Build")

        self.logger.debug("Copy file [{0}] to {1}".format(source_file_name,
                                                          build_file_name))
        # copyfile requires 2 file names - 2nd cannot be a directory dest
        copy_file_nl(source_file_name, build_file_name, discard_empty=True)
        # sh util.copyfile(source_file_name, build_file_name)

        return

    def action_get_uuid_from_router(self):
        """
        Issue the STATUS, to check the UUID installed

        When at least one APP is installed, return is like this:
        {'summary': 'Service started', 'service': 'started',
         'mode': 'devmode', 'apps': [
            {'_id_': '8f828277-5e8f-4c90-9b99-a3eb61f3',
             'app': {
                 'uuid': '8f828277-5e8f-4c90-9b99-a3eb61f3',
                 'vendor': 'customer',
                 'version_minor': 2, 'restart': True, 'version_major': 1,
                 'name': 'probe_gps',
                 'date': '2016-03-21T22:46:39Z'},
             'summary': 'Started application', 'state': 'started'}]}

        When no APP is installed, return is like this:
        {'summary': 'Service started', 'service': 'started',
         'mode': 'devmode', 'apps': []}

        :return int: value intended for sys.exit()
        """
        self._last_uuid = None
        self.logger.info("Checking SDK status on router({})".format(
            self.get_router_ip()))

        # quietly get the STATUS into, will be saved as self.last_status
        self.action_status(verbose=False)

        if 'apps' not in self.last_status:
            self.logger.error(
                "SDK get UUID failed - missing \'apps\' key in response.")
            return EXIT_CODE_BAD_FORM

        if len(self.last_status['apps']) == 0:
            self.logger.error(
                "SDK get UUID failed - [\'apps\'] data is empty.")
            return EXIT_CODE_NO_APPS

        reply = self.last_status['apps']
        """ :type reply: list """
        assert isinstance(reply, list)

        # for now, we only allow 1 SDK app, so take index[0]
        if '_id_' in reply[0]:
            self._last_uuid = reply[0]['_id_']
            self.logger.info("Router has UUID:{} installed".format(
                self._last_uuid))

        if self._last_uuid is None:
            self.logger.error("SDK failed to get UUID from router.")
            return EXIT_CODE_BAD_ACTION

        return 0

    def action_status(self, verbose=True):
        """
        Go to our router and check SDK status

        :param bool verbose: T to see response via logging,
                             F to merely 'test status'
        :return int: value intended for sys.exit()
        """
        from cp_lib.status_tree_data import string_list_status_apps

        self.logger.info("Checking SDK status on router({})".format(
            self.get_router_ip()))

        # we save as 'last_status', as a few clients use as as proxy
        self.last_status = self.cs_client.get("status/system/sdk")
        self.logger.info("SDK status check successful")
        # self.logger.debug("RSP:{}".format(reply['data']))
        # {'service': 'started', 'apps': [], 'mode': 'devmode',
        #  'summary': 'Service started'}

        if verbose:
            # then put out all of the logging info, else don't
            result = self._string_list_status_basic(self.last_status)
            for line in result:
                self.logger.info(line)

            if len(self.last_status['apps']) > 0:
                _index = 0
                for one_app in self.last_status['apps']:
                    result = string_list_status_apps(_index, one_app)
                    for line in result:
                        self.logger.info(line)
                    _index += 1

        return 0

    @staticmethod
    def _string_list_status_basic(status):
        """
        Given STATUS return from Router, Make a list of strings to show
        of basic things like: {'service': 'started', 'apps': [],
         'mode': 'devmode', 'summary': 'Service started'}

        This does NOT enumerate through the APPS list

        :param dict status:
        :return list:
        """
        result = []

        if 'service' in status:
            result.append("SDK Service Status:{}".format(status['service']))

        if 'summary' in status:
            result.append("SDK Summary:{}".format(status['summary']))

        if 'mode' in status:
            if status['mode'].lower() == "devmode":
                result.append("SDK Router is in DEV MODE")
            elif status['mode'].lower() == "standard":
                    result.append(
                        "SDK Router is NOT in DEV MODE - is in STANDARD mode.")
            else:
                result.append("SDK Router Dev Mode Unknown:{}".format(
                    status['mode']))

        if 'apps' in status:
            if len(status['apps']) == 0:
                result.append("SDK - No Apps Installed")
            else:
                result.append("SDK App Count:{}".format(len(status['apps'])))

        return result

    def action_install(self, file_name):
        """
        SCP (copy/upload) the bundle to the router, which then installs

        :param str file_name: base file name to upload, without the ".tar.gz"
        :return int: value intended for sys.exit()
        """
        from cp_lib.app_name_parse import get_app_name

        self.logger.debug("file_name: {}".format(file_name))
        if file_name.startswith(DEF_DUMMY_NAME):
            file_name = None

        # confirm we have BUILD directory; if not, assume no package was built
        if not os.path.isdir(SDIR_BUILD):
            self.logger.error(
                "MAKE cannot install - no {} directory!".format(SDIR_BUILD))
            sys.exit(-11)

        result = self.action_status(verbose=False)
        if result == EXIT_CODE_NO_DATA:
            # then status failed
            self.logger.error(
                "MAKE cannot install - SDK appears to be disabled.")
            return result

        elif result != 0:
            # then status failed
            self.logger.error(
                "MAKE cannot install - SDK status check failed," +
                "code={}".format(result))
            return result

        # try to guess package from ./build
        # - find the tar.gz (such as tcp_echo.tar.gz) and deduce the name
        if file_name is None:
            self.logger.debug("No file given - search for one")
            assert os.path.isdir(SDIR_BUILD)
            result = os.listdir(SDIR_BUILD)
            file_name = None
            for name in result:
                if name.endswith(".tar.gz"):
                    file_name = name[:-7]
                    # self.logger.debug("Split ({})".format(file_name))
                    break

            if file_name is None:
                sys.exit(-12)

        # we want to reduce to just the 'app name' - might be anything
        # from path to file name: example, if network/tcp_echo/tcp_echo or
        # network.tcp_echo, just want tcp_echo
        file_name = get_app_name(file_name)

        # for now, just purge to remove any old files
        # self.action_purge()

        # minor fix-up - if file_name ends with .py, strip that off
        if file_name.endswith(".py"):
            file_name = file_name[:-3]

        # file_name should be like "tcp-echo"
        self.logger.debug("Install:({})".format(file_name))

        # confirm we have BUILD/{name} directory
        file_name = os.path.join(SDIR_BUILD, file_name + ".tar.gz")
        if not os.path.isfile(file_name):
            self.logger.error("MAKE cannot install - no {} archive!".format(
                file_name))
            sys.exit(-13)

        if sys.platform == "win32":
            self.logger.info(
                "Upload & Install SDK on router({}) (win32)".format(
                    self.get_router_ip()))

            # Windows is happy with a single string ... but
            cmd = "{0} -pw {1} -v {2} {3}@{4}:/app_upload".format(
                WIN_SCP_NAME, self.get_router_password(), file_name,
                self.get_router_user_name(),
                self.get_router_ip())

        else:
            self.logger.info(
                "Upload & Install SDK on router({}) (else)".format(
                    self.get_router_ip()))

            # ... but Linux requires the list
            if USE_SSH_PASS:
                # we allow user to select to use or not
                cmd = ["sshpass", "-p", self.get_router_password(),
                       DEF_SCP_NAME, file_name, "{0}@{1}:/app_upload".format(
                        self.get_router_user_name(), self.get_router_ip())]
            else:
                cmd = [DEF_SCP_NAME, file_name, "{0}@{1}:/app_upload".format(
                    self.get_router_user_name(), self.get_router_ip())]

        try:
            self.logger.debug("cmd:({})".format(cmd))
            result = subprocess.check_output(cmd)

        except subprocess.CalledProcessError as err:
            # return subprocess.CalledProcessError.returncode
            # <131>ERROR:make:res:(['probe_gps', 'probe_gps.tar',
            #                      'probe_gps.tar.gz'])
            self.logger.error("err:({})".format(err))
            return -1

        self.logger.debug("res:({})".format(result))

        # save _last_uuid, so for start/stop/uninstall don't have to re-enter
        if "application" in self.settings:
            # then we have
            if "uuid" in self.settings["application"]:
                self._write_uid(self.settings["application"]["uuid"])

        return 0

    def action_start(self, uuid=None):
        """
        Go to our router and start the SDK

        :param str uuid: optional UUID as string, else use self.attrib
        :return int: value intended for sys.exit()
        """
        if uuid is None:
            # if no UUID, then try to read the router
            result = self.action_get_uuid_from_router()
            if result not in (0, EXIT_CODE_NO_APPS):
                # then the action failed
                self.logger.error("SDK start failed - no SDK?")
                return result

            # last_uuid was either set to a found value, or None
            uuid = self._last_uuid

        if uuid is None:
            self.logger.error(
                "Start failed - UUID unknown, or nothing installed")
            return EXIT_CODE_NO_APPS

        self.logger.info(
            "Starting SDK on router({})".format(self.get_router_ip()))
        put_data = '\"start {0}\"'.format(uuid)
        result = self.cs_client.put("control/system/sdk/action", put_data)
        if result.startswith("start"):
            # then assume is okay
            # - need to delay and do new status to really see if started
            return 0

        self.logger.info("Start Result:{}".format(result))
        return EXIT_CODE_BAD_ACTION

    def action_stop(self, uuid=None):
        """
        Go to our router and stop the SDK

        :param str uuid: optional UUID as string, else use self.attrib
        :return int: value intended for sys.exit()
        """
        if uuid is None:
            # if no UUID, then try to read the router
            result = self.action_get_uuid_from_router()
            if result not in (0, EXIT_CODE_NO_APPS):
                # then the action failed
                self.logger.error("SDK stop failed - no SDK?")
                return result

            # last_uuid was either set to a found value, or None
            uuid = self._last_uuid

        if uuid is None:
            self.logger.error(
                "Stop failed - UUID unknown, or nothing installed")
            return EXIT_CODE_NO_APPS

        self.logger.info(
            "Stopping SDK on router({})".format(self.get_router_ip()))
        put_data = '\"stop {0}\"'.format(uuid)
        result = self.cs_client.put("control/system/sdk/action", put_data)
        if result.startswith("stop"):
            # then assume is okay
            # - need to delay and do new status to really see if started
            return 0

        self.logger.info("Stop Result:{}".format(result))
        return EXIT_CODE_BAD_ACTION

    def action_uninstall(self, uuid=None):
        """
        Go to our router and uninstall ONE SDK instance

        :param str uuid: optional UUID as string, else use self.attrib
        :return int: value intended for sys.exit()
        """
        if uuid is None:
            # if no UUID, then try to read the router
            result = self.action_get_uuid_from_router()
            if result not in (0, EXIT_CODE_NO_APPS):
                # then the action failed
                self.logger.error("SDK uninstall failed - no SDK?")
                return result

            # last_uuid was either set to a found value, or None
            uuid = self._last_uuid

        if uuid is None:
            self.logger.error(
                "Uninstalled failed - UUID unknown, or nothing installed")
            return EXIT_CODE_NO_APPS

        self.logger.info(
            "Uninstall SDK on router({})".format(self.get_router_ip()))
        put_data = '\"uninstall {0}\"'.format(uuid)
        result = self.cs_client.put("control/system/sdk/action", put_data)
        if result.startswith("uninstall"):
            # then assume is okay
            # - need to delay and do new status to really see if started

            # make sure none remaining
            self._delete_uid()
            return 0

        self.logger.info("Uninstall Result:{}".format(result))
        return EXIT_CODE_BAD_ACTION

    def action_purge(self):
        """
        Go to our router and purge ALL SDK instances

        :return int: value intended for sys.exit()
        """
        self.logger.info(
            "Purging SDK on router({})".format(self.get_router_ip()))
        put_data = '\"purge\"'
        result = self.cs_client.put("control/system/sdk/action", put_data)
        if result.startswith("purge"):
            # then assume is okay
            # - need to delay and do new status to really see if started
            return 0

        self.logger.info("Purge Result:{}".format(result))
        return EXIT_CODE_BAD_ACTION

    def action_reboot(self):
        """
        Go to our router, and reboot it

        :return int: value intended for sys.exit()
        """
        self.logger.info(
            "Reboot our development router({})".format(self.get_router_ip()))
        # put_data = '\"true\"'
        put_data = 'true'
        result = self.cs_client.put("control/system/reboot", put_data)
        # result will be boolean?
        if False:
            # then assume is okay
            # - need to delay and do new status to really see if started
            self.logger.info("SDK reboot successful")
            return 0

        self.logger.info("Reboot Result:{}".format(result))
        return EXIT_CODE_BAD_ACTION

    def action_clean(self):
        """
        Delete temp build files

        :return int: value intended for sys.exit()
        """
        self.logger.info("Clean temporary build files")

        # clean out the BUILD files
        path_name = SDIR_BUILD
        if os.path.isdir(path_name):
            self.logger.info("Delete BUILD directory")
            shutil.rmtree(path_name, ignore_errors=True)

        path_name = os.getcwd()
        # self.logger.info("Cleaning from directory {}".format(path_name))

        # clean out the Python cache directories
        del_list = []
        for path, dir_name, file_name in os.walk(path_name):

            # self.logger.debug("path:{0} dir:{1} fil:{2}".format(
            #     path, dir_name, file_name))

            if path.startswith(path_name + os.sep + '.'):
                # we'll skip everything like "./.idea" or any starting with '.'
                # self.logger.debug("skip:{}".format(path))
                continue

            if path.endswith("__pycache__"):
                # we'll want to delete this
                # self.logger.debug("add to list:{}".format(path))
                del_list.append(path)
                continue

            pass  # try next one

        for path_name in del_list:
            self.logger.info("Delete {} directory".format(path_name))
            shutil.rmtree(path_name, ignore_errors=True)

        for path_name in ("config/settings.json", "syslog1.txt"):
            # delete a few known temporary files
            if os.path.isfile(path_name):
                self.logger.info("Delete FILE {}".format(path_name))
                os.remove(path_name)

        # sometimes, we end up with .pyc in /tools?
        for path_name in ("tools", "test"):
            del_list = os.listdir(path_name)
            for file_name in del_list:
                if file_name.endswith(".pyc"):
                    self.logger.info("Delete FILE {}".format(file_name))
                    os.remove(file_name)
                if file_name.endswith(".pyo"):
                    self.logger.info("Delete FILE {}".format(file_name))
                    os.remove(file_name)

        return 0

    def action_ping(self, ip_address):
        """
        Go to our router, and try to ping remotely

        :param str ip_address: the IP to pin
        :return int: value intended for sys.exit()
        """
        # TODO - if ip_address IS our router, do ping from PC?

        self.logger.info("Send a PING to {} from router({})".format(
            ip_address, self.get_router_ip()))

        result = cs_ping(self, ip_address)
        if result['status'] == "success":
            return 0
        return EXIT_CODE_BAD_ACTION

    def _copy_a_file(self, file_name):
        """
        Copy the file over, using logic:
        1) if {app_path}/{file_name} exists, use that
        2) else is {config}/{file_name} exists, use that
        3) else return False

        :param str file_name: the file to handle
        :rtype: None
        """

        app_file_name = os.path.join(self.get_app_path(), file_name)
        cfg_file_name = os.path.join(SDIR_CONFIG, file_name)
        dst_file_name = os.path.join(self.get_build_path(), file_name)

        if os.path.exists(app_file_name):
            # if app developer supplies one, use it (TDB - do pre-processing)
            self.logger.debug("Copy existing app script from [{}]".format(
                app_file_name))
            copy_file_nl(app_file_name, dst_file_name)
            # sh util.copyfile(app_file_name, dst_file_name)
            self.logger.debug("Add file [{}] to exclude list".format(
                app_file_name))
            self._exclude.append(app_file_name)

        elif os.path.exists(cfg_file_name):
            # if root supplies one, use it (TDB - do pre-processing)
            self.logger.debug("Copy existing root script from [{}]".format(
                cfg_file_name))
            copy_file_nl(cfg_file_name, dst_file_name)
            # sh util.copyfile(cfg_file_name, dst_file_name)

        else:
            return False

        return True

    def create_install_sh(self, file_name=None):
        """
        Create the install.sh in BUILD, using logic:
        1) if {app_path}/install.sh exists, use that
        2) else is {config}/install.sh exists, use that
        3) else make a basic default

        Final name will be in build/install.sh

        :param str file_name: an alternative name for safe regression testing
        :rtype: None
        """
        self.logger.info("Create INSTALL.SH script")

        if file_name is None:
            file_name = FILE_NAME_INSTALL

        if not self._copy_a_file(file_name):
            file_name = os.path.join(self.get_build_path(), file_name)
            # self.logger.debug("create new {}".format(file_name))
            data = [
                '#!/bin/bash\n',
                'echo "INSTALLATION for {0}:" >> install.log\n'.format(
                    self.mod_name),
                'date >> install.log\n'
            ]
            file_han = open(file_name, 'wb')
            for line in data:
                # we don't want a Windows file, treat as binary ("wb" not "w")
                file_han.write(line.encode())
            file_han.close()

        return

    def create_start_sh(self, file_name=None):
        """
        Create the start.sh, or copy from config.

        Final name will be in router_app/start.sh

        :param str file_name: alternative name for safe regression testing
        :rtype: None
        """
        self.logger.info("Create START.SH script")

        if file_name is None:
            file_name = FILE_NAME_START

        if not self._copy_a_file(file_name):
            file_name = os.path.join(self.get_build_path(), file_name)

            # self.logger.debug("create new {}".format(file_name))
            data = [
                '#!/bin/bash\n',
                'cppython main.py %s\n' % self.mod_name
            ]
            file_han = open(file_name, 'wb')
            for line in data:
                # we don't want a Windows file, treat as binary ("wb" not "w")
                file_han.write(line.encode())
            file_han.close()

        return

    def create_go_bat(self):
        """
        Create a simple go.bat on Windows
        """
        if sys.platform == "win32":
            file_name = os.path.join(self.get_build_path(), "go.bat")
            self.logger.info("Create {} script".format(file_name))
            data = 'python main.py %s' % self.mod_name
            file_han = open(file_name, 'w')
            file_han.write(data)
            file_han.close()

        return

    def _confirm_dir_exists(self, dir_name, dir_msg=None):
        """
        Confirm the directory exists, create if required. If the name
        is blocked by a file of
        the same name, then rename as {name}.save

        :param str dir_name: the relative directory name
        :param str dir_msg: a message for errors, like "CONFIG dir"
        :return:
        """
        # confirm ./config exists and is not a file
        if os.path.isfile(dir_name):
            # rename as .save, then allow creation below
            shutil.copyfile(dir_name, dir_name + self.SDIR_SAVE_EXT)
            os.remove(dir_name)

        if not os.path.isdir(dir_name):
            # if not there, make it!
            self.logger.debug("{}({}) being created".format(dir_msg, dir_name))

            # NOT working under windows! Add delay, seems to be race condition
            # where adding immediately after delete fails as PermissionError!
            try:
                os.makedirs(dir_name)
            except PermissionError:
                time.sleep(1.0)
                os.makedirs(dir_name)

        # else:
            # self.logger.debug("{}({}) exists as dir".format(
            #                   dir_msg, dir_name))
        return

    @staticmethod
    def _remove_name_no_error(file_name):
        """
        Just remove if exists
        :param str file_name: the file
        :return:
        """
        if os.path.isdir(file_name):
            shutil.rmtree(file_name)

        else:
            try:  # second, try if common file
                os.remove(file_name)
            except FileNotFoundError:
                pass
        return

    def dump_help(self, args):
        """

        :param list args: the command name
        :return:
        """
        print("Syntax:")
        print('   {} -m <action> <applicationRoot>'.format(args[0]))
        print()
        print("   Default action = {}".format(self.ACTION_DEFAULT))
        for command in self.ACTION_NAMES:
            print()
            print("- action={0}".format(command))
            print("    {0}".format(self.ACTION_HELP[command]))

        return

if __name__ == "__main__":

    maker = TheMaker()

    if len(sys.argv) < 2:
        maker.dump_help(sys.argv)
        sys.exit(-1)

    # if cmdline is only "make", then run as "make build" but we'll
    # expect ["name"] in global sets

    # save this, just in case we care later
    utility_name = sys.argv[0]

    index = 1
    while index < len(sys.argv):
        # loop through an process the parameters

        if sys.argv[index] in ('-m', '-M'):
            # then what follows is the mode/action
            action = sys.argv[index + 1].lower()
            if action in maker.ACTION_NAMES:
                # then it is indeed an action
                maker.action = action
            index += 1  # need an extra ++ as -m includes 2 params

        elif sys.argv[index] in ('-i', '-I', '+i', '+I'):
            # then we'll want the [app][version] incremented in the system.ini
            maker.increment_version = True

        elif sys.argv[index] in ('-p', '-P'):
            # then we'll ignore some PIP dependencies, as we're running
            # on PC only
            maker.ignore_pip = True

        elif sys.argv[index] in ('-v', '-V', '+v', '+V'):
            # switch the logger to DEBUG from INFO
            maker.verbose = True

        else:
            # assume this is the app path
            maker.app_path = sys.argv[index]

        index += 1  # get to next setting

    if maker.verbose:
        logging.basicConfig(level=logging.DEBUG)
        maker.logger.setLevel(level=logging.DEBUG)

    else:
        logging.basicConfig(level=logging.INFO)
        maker.logger.setLevel(level=logging.INFO)
        # quiet INFO messages from requests module,
        #               "requests.packages.urllib3.connection pool"
        logging.getLogger('requests').setLevel(logging.WARNING)

    _result = maker.main()
    if _result != 0:
        logging.error("return is {}".format(_result))

    sys.exit(_result)
