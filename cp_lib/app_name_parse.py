"""
Misc path tools for handling the app file name. In examples below,
assume "src" is "network/tcp_echo/__init__.py"
- get_app_name(src), which returns "tcp_echo"
- get_app_path(src, sep=os), which returns "network/tcp_echo/"
- get_module_name(src), which returns "network.tcp_echo"
- get_run_name(src), returns "network/tcp_echo/__init__.py" (if > 5 bytes), else
                                                                   "network/tcp_echo/tcp_echo.py"
- normalize_app_name(src), ["network", "tcp_echo", ""] or ["network", "tcp_echo", "__init__.py"]
- normalize_path_separator(src, sep=os), forces all '\\' or '/' to be as desired.

The routines: get_app_name(), get_app_path(), get_module_name(), get_run_name() all
use normalize_app_name() to parse the source. So their 'src' input can be either a str, or
list[] as output by normalize_app_name
"""
import os.path

# assume a valid __init__.py is at least 5 bytes?
MIN_INIT_PY_SIZE = 5


def get_app_name(source):
    """
    Given one of a variety of 'path names', return a string like "tcp_echo"

    :param source:
    :type source: str or list
    :return:
    """
    if isinstance(source, str):
        source = normalize_app_name(source)
    # else assume is already normalized!
    assert isinstance(source, list)
    assert len(source) >= 2

    # print("source:%s" % str(source))

    # ["network", "tcp_echo", "__init__.py"] - we want "tcp_echo"
    # ["network", "tcp_echo", ""] - we want "tcp_echo"
    # ["tcp_echo", "__init__.py"] - we want "tcp_echo"
    # ["tcp_echo", ""] - we want "tcp_echo"
    # ["", "__init__.py"] - we want ""

    return source[-2]


def get_app_path(source, separator=None):
    """
    Given one of a variety of 'path names', return a path string like "network/tcp_echo/"

    :param source:
    :type source: str or list
    :param separator: optional forced separator as '\\' or '/', else use os.sep
    :return:
    """
    if isinstance(source, str):
        source = normalize_app_name(source)
    # else assume is already normalized!
    assert isinstance(source, list)
    assert len(source) >= 2

    if separator is None:
        separator = os.sep

    # print("source:%s" % str(source))

    # ["network", "tcp_echo", "__init__.py"] - we want "network/tcp_echo/"
    # ["network", "tcp_echo", ""] - we want "network/tcp_echo/"
    # ["tcp_echo", "__init__.py"] - we want "tcp_echo/"
    # ["tcp_echo", ""] - we want "tcp_echo/"
    # ["", "__init__.py"] - we want ""

    if source[0] == "":
        # the special NO path case (likely is not useful, but let the caller decide!)
        return ""

    result = ""
    for index in range(0, len(source) - 1):
        result += source[index] + separator

    return result


def get_module_name(source):
    """
    Given one of a variety of 'path names', return a string like "network.tcp-echo"

    :param source:
    :type source: str or list
    :return:
    """
    if isinstance(source, str):
        source = normalize_app_name(source)
    # else assume is already normalized!
    assert isinstance(source, list)
    assert len(source) >= 2

    # print("source:%s" % str(source))

    # ["network", "tcp_echo", "__init__.py"] - we want "network.tcp_echo"
    # ["network", "tcp_echo", ""] - we want "network.tcp_echo"
    # ["tcp_echo", "__init__.py"] - we want "tcp_echo"
    # ["tcp_echo", ""] - we want "tcp_echo"
    # ["", "__init__.py"] - we want ""

    if source[0] == "":
        # the special NO path case (likely is not useful, but let the caller decide!)
        return ""

    result = ""
    for index in range(0, len(source) - 1):
        result += source[index] + "."

    return result[:-1]


def get_run_name(source, app_path=None, app_name=None):
    """
    Given one of a variety of 'path names', return file to run, like "network/tcp-echo/__init__.py"

    :param source:
    :type source: str or list
    :param str app_path: optional app path, like "network/tcp_echo/"
    :param str app_name: optional app name, like "tcp_echo"
    :return str:
    """
    if isinstance(source, str):
        source = normalize_app_name(source)
    # else assume is already normalized!
    assert isinstance(source, list)
    assert len(source) >= 2

    # print("source:%s" % str(source))

    # ["network", "tcp_echo", "__init__.py"] - we want "network.tcp_echo"
    # ["network", "tcp_echo", ""] - we want "network.tcp_echo"
    # ["tcp_echo", "__init__.py"] - we want "tcp_echo"
    # ["tcp_echo", ""] - we want "tcp_echo"
    # ["", "__init__.py"] - we want ""

    if app_path is None:
        # if not passed in, then make the hard way
        app_path = get_app_path(source)

    # see if the main app is like "network/tcp_echo/__init__.py"
    result = app_path + "__init__.py"
    # print("Test RUN name:{}".format(result))
    if os.path.exists(result):
        # if it exists, make sure is a bit larger than 5(?) bytes
        stat_data = os.stat(result)
        if stat_data.st_size > MIN_INIT_PY_SIZE:
            return result
        # else, skip try the named app

    if app_name is None:
        # if not passed in, then make the hard way
        app_name = get_app_name(source)

    # if still here, then __init__.py is not there, or too small
    # assume the app is like "network/tcp_echo/tcp_echo.py"
    result = app_path + app_name + ".py"
    # print("Test RUN name:{}".format(result))
    if os.path.exists(result):
        return result

    # # if "network/tcp_echo/tcp_echo.py" also doesn't exist, then must have "network/tcp_echo/make.py"
    # result = app_path + "main.py"
    # print("Test RUN name:{}".format(result))
    # if not os.path.exists(result):
    #     raise FileNotFoundError("Router App: targeted APP {} doesn't exist!".format(result))

    return result


def normalize_app_name(source):
    """
    Given one of a variety of 'path names', return a consistent LIST of path segments

    [-1] will be the file name or "" is none included
    all items NOT including [-1] are the path segments

    :param str source:
    :return list:
    """
    if source.find("\\") >= 0:
        # then we have the Windows style os.sep
        value = source.split("\\")
        if value[-1].endswith(".py"):
            # if source = "network\\tcp_echo\\file.py", return ["network", "tcp_echo", "file.py"]
            pass
        elif value[-1] != "":
            # if source = "network\\tcp_echo", return ["network", "tcp_echo", ""]
            value.append("")
        # else, if source = "network\\tcp_echo\\", return ["network", "tcp_echo", ""]

    elif source.find("/") >= 0:
        # then we have the Linux style os.sep
        value = source.split("/")
        if value[-1].endswith(".py"):
            # if source = "network/tcp_echo/file.py", return ["network", "tcp_echo", "file.py"]
            pass
        elif value[-1] != "":
            # if source = "network/tcp_echo", return ["network", "tcp_echo", ""]
            value.append("")
        # else, if source = "network/tcp_echo/", return ["network", "tcp_echo", ""]

    elif source.find(".") >= 0:
        # then we have the DOTS from module name
        value = source.split(".")
        if value[-1] == "py":
            # if source = "network.tcp_echo.file.py", return ["network", "tcp_echo", "file.py"]
            value[-2] += ".py"
            value.pop(-1)

            # special case for "network.py" without a path
            if len(value) == 1:
                value = ["", value[0]]

        elif value[-1] != "":
            # if source = "network.tcp_echo", return ["network", "tcp_echo", ""]
            value.append("")
        # else, if source = "network.tcp_echo.", return ["network", "tcp_echo", ""]

    else:  # assume is "my_file" and return ["my_file", ""]
        value = [source, ""]

    return value


def normalize_path_separator(source, separator=None):
    """
    Given a path name as text, make sure has a single form of separator

    :param str source: the path as text
    :param str separator:
    :return str:
    """
    if separator is None:
        # if none defined, use the OS default
        separator = os.sep

    if separator not in ('\\', '/'):
        raise ValueError("normalize_path_separator() requires valid Unix or Windows separator.")

    if separator == "\\":
        # then is Windows, force any LINUX style to Windows
        if source.find("/") >= 0:
            # logging.debug("Change to Windows Style OS.Sep")
            source = source.replace("/", "\\")

    else:  # assume is Linux, force Windows style to Linux
        if source.find("\\") >= 0:
            # logging.debug("Change to Linux Style OS.Sep")
            source = source.replace("\\", "/")

    return source
