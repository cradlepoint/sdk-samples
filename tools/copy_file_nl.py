import logging
import os


def copy_file_nl(source_name, destination_name, discard_empty=False):
    """
    Mimic "shutil.copyfile(src_name, dst_name)", however if the file ends in .py, .ini, .json, or .sh, then
    make sure EOL is LINUX style "\n"

    :param str source_name: the source file name
    :param str destination_name: the destination FILE name (cannot be the sub-directory!)
    :param bool discard_empty: if T, we skip copying an empty file.
    :return:
    """
    # logging.debug("copy file {0} to {1}".format(source_name, destination_name))
    if not os.path.isfile(source_name):
        # the source file is missing
        raise FileNotFoundError

    # first, see if we should SKIP this file
    if discard_empty:
        stat_data = os.stat(source_name)
        if stat_data.st_size <= 0:
            logging.debug("Skip Source({}) because is empty".format(source_name))
            return

    # logging.debug("read in file:[{}]".format(source_name))
    lines = []
    file_han = open(source_name, "rb")
    for line in file_han:
        lines.append(line)
    file_han.close()

    if source_name.endswith(".py") or source_name.endswith(".ini") or source_name.endswith(".json") or \
            source_name.endswith(".sh"):
        # then we make sure line ends in
        clear_eol = True
    else:
        clear_eol = False

    # logging.debug("write out file:[{}]".format(destination_name))
    file_han = open(destination_name, "wb")
    for line in lines:
        if clear_eol:
            # this is text file, force to be Linux style '\n'
            file_han.write(line.rstrip() + b'\n')
        else:   # else write as is, with 'line' being an unknown quantity
            file_han.write(line)
    file_han.close()

    return
