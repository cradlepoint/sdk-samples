
from cp_lib.split_version import split_version_string
"""
Make a file such as:
[RouterSDKDemo]
uuid=7042c8fd-fe7a-4846-aed1-e3f8d6a1c91c
vendor=Cradlebox
notes=Router SDK Demo Application
firmware_major=6
firmware_minor=1
restart=true
reboot=true
version_major=1
version_minor=6
"""

DEF_FILE_NAME = "package.ini"


def make_package_ini(sets, output_file_name):
    """
    Assuming we have a 'standard' settings file as dict, create the
    ECM-expected file.

    :param dict sets:
    :param str output_file_name:
    :return:
    """
    data_lines = []
    app_sets = sets["application"]

    # [RouterSDKDemo]
    data_lines.append("[%s]" % app_sets["name"])
    data_lines.append("uuid=%s" % app_sets["uuid"])

    value = app_sets.get("vendor", "customer")
    data_lines.append("vendor=%s" % value)
    value = app_sets.get("description", "")
    data_lines.append("notes=%s" % value)

    value = app_sets.get("restart", "False").lower()
    data_lines.append("restart=%s" % value)
    value = app_sets.get("reboot", "False").lower()
    data_lines.append("reboot=%s" % value)
    value = app_sets.get("auto_start", "True").lower()
    data_lines.append("auto_start=%s" % value)

    value = app_sets.get("firmware", "6.1")
    major, minor = split_version_string(value)
    data_lines.append("firmware_major=%s" % major)
    data_lines.append("firmware_minor=%s" % minor)

    value = app_sets.get("version", "0.1")
    major, minor = split_version_string(value)
    data_lines.append("version_major=%s" % major)
    data_lines.append("version_minor=%s" % minor)

    _han = open(output_file_name, 'w')
    for line in data_lines:
        _han.write(line + "\n")
    _han.close()

    return


if __name__ == "__main__":

    import os

    settings = {
        "application": {
            "name": "tcp_echo",
            "uuid": "7042c8fd-fe7a-4846-aed1-e3f8d6a1TEST",
            "description": "Basic TCP echo server and client",
            "version": "1.3"
        },
        "base": {
            "vendor": "MySelf, Inc.",
            "firmware": "6.1",
            "restart": True,
            "reboot": True,
        }
    }

    ini_name = os.path.join("test", DEF_FILE_NAME)

    make_package_ini(settings, ini_name)
