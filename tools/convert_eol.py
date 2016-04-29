import os


def convert_eol_linux(base_directory):
    """
    Given a sub-directory, walk it and convert EOL in all "text" files

    :param str base_directory:
    :return:
    """
    if not os.path.isdir(base_directory):
        raise FileNotFoundError("dir {} doesn't exist".format(base_directory))

    for path_name, dir_name, file_name in os.walk(base_directory):
        for name in file_name:
            # see about converting the file's EOL
            if name.endswith(".py"):
                pass
            elif name.endswith(".ini"):
                pass
            elif name.endswith(".json"):
                pass
            elif name.endswith(".sh"):
                pass
            else:
                print("Pass name:[{}]".format(name))
                continue

            # read in all the old lines as binary
            full_path_file = os.path.join(path_name, name)
            print("read in file:[{}]".format(full_path_file))

            lines = []
            file_han = open(full_path_file, "rb")
            for line in file_han:
                lines.append(line.rstrip())
            file_han.close()

            print("write out file:[{}]".format(full_path_file))
            file_han = open(full_path_file, "wb")
            for line in lines:
                file_han.write(line + b'\n')
            file_han.close()

    return True

if __name__ == '__main__':
    import sys

    convert_eol_linux(sys.argv[1])
