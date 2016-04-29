import os
import shutil


DEF_INI_EOL = "\n"
DEF_BACKUP_EXT = ".BAK"


def clean_ini_file(ini_name, eol=None, backup=False):
    """
    Given an INI file, walk through and 'clean up' as required. The primary changes:
    1) string unnecessary white space
    2) insure all lines end in consistent end-of-line (is OS default, unless user passes in another form)
    3) force all section headers to lower case - per spec, INI files are NOT case sensitive
    4) strip off leading or trailing empty/blank lines
    5) reduce sequential blank lines to one only
    6) note: the keys and values are NOT affected (at this time)

    :param str ini_name: relative path (with directories) to the INI file
    :param str eol: optional end-of-line string. default is OS default, but user can pass in another
    :param bool backup: T if you want to save the original file
    :return: None
    """
    if os.path.exists(ini_name):
        # only do if it exists
        print("Cleaning INI file {}".format(ini_name))

        # read the original file, clean up various things
        lines = []
        was_blank = False
        file_han = open(ini_name, "r")
        for line in file_han:
            # go through and clean up any lines
            line = line.strip()
            if not len(line):
                # then is blank line, if 2 in a row skip appending!
                if was_blank:
                    continue
                else:
                    was_blank = True

            elif line[0] == "[":
                # then is section heading, since is not case sensitive, make lower case
                line = line.lower()
                was_blank = False

            elif line[0] == "#":
                # make Python-like comments into INI standard comments
                if line[1] != " ":
                    line = "; " + line[1:]
                else:
                    line = ";" + line[1:]
                was_blank = False

            # else, leave as is
            lines.append(line)
        file_han.close()

        try:
            while len(lines[0]) == 0:
                # strip off leading blank lines
                lines.pop(0)

            while len(lines[-1]) == 0:
                # strip off leading blank lines
                lines.pop(-1)

        except IndexError:
            # file was too short? Ehh, is okay.
            return

        # optionally back up the original (mainly used during testing)
        if backup:
            shutil.copyfile(ini_name, ini_name + DEF_BACKUP_EXT)

        # rewrite the INI with the new cleaned and EOL-normalized data
        if eol is None:
            eol = DEF_INI_EOL

        file_han = open(ini_name, "w")
        for line in lines:
            file_han.write(line + eol)
        file_han.close()

    return
