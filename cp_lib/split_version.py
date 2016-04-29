
def split_version_string(value, default=None):
    """
    Given a string in the form X.Y, split to two integers. Trailing text is
    discarded, so X.Y.Z returns (x, y) and the Z is discarded.

    :param str value: a string version such as "6.1" or "7.345.beta"
    :param str default:
    :return: major and minor as ints
    :rtype: int, int
    """
    if value is None or value == "":
        if default is None:
            return None, None
        else:
            value = default

    if not isinstance(value, str):
        # we don't expect int or float or other types
        raise TypeError

    value = value.strip()

    # hope value is like "X.y"

    offset = value.find(".")
    if offset >= 0:
        # then we found a ".", assume major is first part - the "X"
        major = int(value[:offset])

        # now test the second part
        value = value[offset + 1:]
        offset = value.find(".")
        if offset >= 0:
            # assume was had an X.Y.Z, so just ignore/discard the Z + more
            minor = int(value[:offset])
        else:  # was just X.Y, so this is the Y part
            minor = int(value)
    else:  # was just X, so force Y to be 0
        major = int(value)
        minor = 0

    return major, minor

SETS_NAME_MAJOR = 'major_version'
SETS_NAME_MINOR = 'minor_version'


def split_version_save_to_dict(value, sets, default=None, section=None):
    """
    Given a string in the form X.Y, split to two integers and save as
    ['major_version'] and ['minor_version'] in the [section] of sets.

    :param str value: a string version such as "6.1" or "7.345.beta"
    :param dict sets: the settings, as per normal SDK
    :param str default:
    :param str section: the sub-section in sets, like "application" or
                        "fw_info"; if None, assume in base setts
    :return dict:
    """
    major, minor = split_version_string(value, default)

    if section is None:
        sets[SETS_NAME_MAJOR] = major
        sets[SETS_NAME_MINOR] = minor
    else:
        if section not in sets:
            sets[section] = dict()

        sets[section][SETS_NAME_MAJOR] = major
        sets[section][SETS_NAME_MINOR] = minor

    return sets


def sets_version_to_str(sets, section=None):
    """
    Given a dict() (the 'sets'), see if at least one of ['major_version']
    and ['minor_version'] exist, if so
    return a string formed as "major.minor", with 0 being a default.

    If neither exist, then return None

    :param dict sets: the settings, as per normal SDK
    :param str section: the sub-section in sets, like "application" or
                        "fw_info"; if None, assume in base setts
    :rtype str:
    """
    if section is None:
        major = sets.get(SETS_NAME_MAJOR, None)
        minor = sets.get(SETS_NAME_MINOR, None)
    else:
        major = sets[section].get(SETS_NAME_MAJOR, None)
        minor = sets[section].get(SETS_NAME_MINOR, None)

    if major is None and minor is None:
        # then we've failed
        return None

    if major is None:
        major = 0
    else:
        major = int(major)

    if minor is None:
        minor = 0
    else:
        minor = int(minor)

    return "%d.%d" % (major, minor)
