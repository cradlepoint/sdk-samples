"""
Obtain module dependencies for Cradlepoint SDK
"""

import os.path

# from make import EXIT_CODE_MISSING_DEP


class BuildDependencyList(object):

    # these are modules on Cradlepoint FW with Python 3.3 (/usr/lib/python3.3)
    COMMON_STD_MODULES = [
        "OpenSSL", "__future__", "abc", "argparse", "base64", "bisect",
        "calendar", "cgi", "chunk", "cmd", "code", "codecs", "codeop",
        "collections", "configparser", "contextlib", "copy", "copyreg",
        "ctypes", "datetime", "dateutil", "difflib", "dnslib", "dnsproxy",
        "dummy_threading", "email", "encodings", "fnmatch", "functools",
        "getopt", "gettext", "glob", "gzip", "hashlib", "heapq", "hmac",
        "html", "http", "importlib", "io", "ipaddress", "json", "keyword",
        "linecache", "locale", "logging", "lzma", "mailbox", "mimetypes",
        "numbers", "os", "pickle", "pkgutil", "platform", "pprint",
        "py_compile", "pyrad", "queue", "quopri", "random", "re", "reprlib",
        "runpy", "serial", "shlex", "smtplib", "socket", "socketserver",
        "sre_compile", "sre_constants", "sre_parse", "ssl", "stat", "string",
        "stringprep", "struct", "subprocess", "tarfile", "telnetlib",
        "textwrap", "threading", "token", "tokenize", "traceback", "tty",
        "types", "urllib", "uu", "uuid", "weakref", "xml",

        # these exist on router, but you probably should not be using!
        # are either Cradlepoint-specific, or obsolete, or depend on STDIO
        # access you lack; shutil & tempfile in this list because large file
        # ops on router flash is risky
        "_compat_pickle", "_pyio", "_strptime", "_weakrefset", "bdb",
        "compileall", "cProfile", "cp", "cpsite", "dis", "genericpath",
        "imp", "inspect", "lib-dynload", "opcode", "pdb",
        "posixpath", "shutil", "ssh", "tempfile", "tornado", "warnings",

        # exist, but not in /usr/lib/python3.3? builtin?
        # maybe inside cradlepoint.cpython-33m?
        "binascii", "errno", "fcntl", "ioctl", "gc", "math",
        "pydoc", "select", "sys", "time"
    ]

    # others? _ssh.cpython-33m.so, cradlepoint.cpython-33m.so

    # these are used in sys.platform != CP router only
    COMMON_PIP = [
        "requests", "requests.auth", "requests.exceptions"
    ]

    def __init__(self):

        # # load the CP sample built-in list, will be of form: {
        # #       "cp_lib.clean_ini": [],
        # #       "cp_lib.cp_logging": ["cp_lib.hw_status",
        #                               "cp_lib.load_settings"],
        # # }
        # json_name = os.path.join("tools", "module_dependency.json")
        # file_han = open(json_name, "r")
        # self._cp_lib_details = json.load(file_han)
        # file_han.close()

        self.dep_list = []

        self.ignore_pip = False

        self.logger = None

        return

    def add_file_dependency(self, file_name=None):
        """
        Given a single file which ends in .py, scan for import lines.

        :param str file_name:
        :return:
        """
        # self.logger.debug("add_file_dependency({0})".format(file_name))

        if not isinstance(file_name, str):
            raise TypeError

        if not os.path.exists(file_name):
            raise FileNotFoundError(
                "module_dependency: file({}) doesn't exist.".format(file_name))

        if not os.path.isfile(file_name):
            raise FileNotFoundError(
                "module_dependency: file({}) doesn't exist.".format(file_name))

        value = os.path.splitext(file_name)
        # should be like ('network\\tcp_echo\\tcp_echo', '.py') or
        # ('network\\tcp_echo', '')
        # self.logger.debug("value({})".format(value))
        if value[1] != ".py":
            # self.logger.debug(
            #   "module_dependency: file({}) is not PYTHON (.py)normal file.")
            return None

        # at this point, the file should be a .PY file at least
        file_han = open(file_name)
        for line in file_han:
            offset = line.find("import")
            if offset >= 0:
                # then we found a line
                tokens = line.split()

                if len(tokens) >= 2 and tokens[0] == "import":
                    # then like "import os.path" or "import os, sys, socket"

                    if tokens[1][-1] != ",":
                        # then is like "import os.path"
                        self.logger.debug("add_file_dep:{}".format(tokens[1]))
                        self.add_if_new(tokens[1])

                    else:  # like "import os, sys, socket"
                        for name in tokens[1:]:
                            self.logger.debug("token({})".format(name))
                            if name[-1] == ',':
                                value = name[:-1]
                            else:
                                value = name
                            self.add_if_new(value)

                elif len(tokens) >= 4 and tokens[0] == "from" and \
                        tokens[2] == "import":
                    # then is like "from cp_lib.cp_self.logger import
                    #       get_recommended_logger"
                    self.add_if_new(tokens[1])

        file_han.close()

        # self.logger.debug("module_dependency: {}".format(self.dep_list))
        return self.dep_list

    def add_if_new(self, new_name):
        """
        Given new module, see if already known or to be skipped

        :param str new_name: the gathering list of names
        :return int: return count of names added
        """
        # self.logger.debug("add_if_new({0})".format(new_name))

        if new_name in self.COMMON_STD_MODULES:
            # scan through existing STD LIB like "self.logger", "sys", "time"
            # self.logger.debug("Mod({}) is in std lib.".format(new_name))
            return 0

        # if self.ignore_pip and new_name in self.COMMON_PIP:
        if new_name in self.COMMON_PIP:
            # scan through existing STD LIB like "requests"
            self.logger.debug("Mod({}) is in PIP lib.".format(new_name))
            return 0

        # handle importing sub modules, like os.path or self.logger.handlers
        if new_name.find('.') >= 0:
            # then we have a x.y
            name = new_name.split('.')
            if name[0] in self.COMMON_STD_MODULES:
                # self.logger.debug("Mod({}) is in std lib.".format(new_name))
                return 0

        if new_name in self.dep_list:
            # scan through existing names
            self.logger.debug("Mod({}) already known.".format(new_name))
            return 0

        # if still here, then is a new name
        self.logger.debug("Mod({}) is NEW!".format(new_name))

        # convert from network.tcp_echo.ftplib to network/tcp_echo/ftplib
        path_name = new_name.replace('.', os.sep)

        added_count = 0
        if not os.path.isdir(path_name):
            # only ADD is not a subdirectory
            self.dep_list.append(new_name)
            added_count = 1

        # handle is file or sub-directory
        self.logger.info("_add_recurse:{} {}".format(path_name, new_name))
        added_count += self._add_recurse(path_name, new_name)

        return added_count

    def _add_recurse(self, path_name, dot_name):
        """
        Assume new_name is like "network/tcp_echo/xmlrpc/" or
        "network/tcp_echo/ftplib.py"

        :param str path_name: the path name, like "network/tcp_echo/xmlrpc"
        :param str dot_name: the dot name, like "network.tcp_echo.xmlrpc"
        :return int: return if files were added
        """
        # self.logger.debug(
        #   "_add_recurse({0},{1})".format(path_name, dot_name))

        added_count = 0
        if os.path.isdir(path_name):
            # then is module, such as xmlrpc, with includes:
            #   network/tcp_echo/xmlrpc/__init__.py
            #   network/tcp_echo/xmlrpc/client.py
            #   network/tcp_echo/xmlrpc/server.py
            self.logger.debug("Recurse into directory ({})".format(path_name))

            dir_list = os.listdir(path_name)
            for name in dir_list:
                if name == "__pycache__":
                    self.logger.debug(
                        "  skip known skipper ({})".format(name))
                    continue

                if name == "test":
                    self.logger.debug(
                        "  skip known skipper ({})".format(name))
                    continue

                if name[0] == ".":
                    self.logger.debug(
                        "  skip pattern skipper ({})".format(name))
                    continue

                # still here, see if file or subdirectory
                file_name = os.path.join(path_name, name)
                if os.path.isdir(file_name):
                    # then another sub-directory
                    added_count += self._add_recurse(
                        file_name, dot_name + '.' + name)

                else:  # assume is a file?
                    # for example, name=client.py
                    if name.endswith(".py"):
                        self.dep_list.append(file_name)
                        added_count += 1
                        try:
                            self.logger.debug(
                                "Recurse into s-file ({})".format(file_name))
                            self.add_file_dependency(file_name)

                        except FileNotFoundError:
                            self.logger.error(
                                "Could NOT find above dependency within" +
                                "({})".format(file_name))
                            # sys.exit(EXIT_CODE_MISSING_DEP)

                    else:
                        # expects network.tcp_echo.xmlrpc.something.txt
                        value = path_name + os.sep + name
                        self.logger.debug(
                            "Add file as dependency({})".format(value))
                        self.dep_list.append(value)
                        added_count += 1

        else:
            # might be file, like network/tcp_echo/ftplib.py as
            #   network.tcp_echo.ftplib
            if not path_name.endswith(".py"):
                path_name += ".py"
            self.logger.debug("Recurse into d-file ({})".format(path_name))
            self.add_file_dependency(path_name)

        return added_count
