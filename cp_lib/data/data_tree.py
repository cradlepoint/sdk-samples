"""
Manage a dictionary, such as imported from settings.json.
"""
from cp_lib.parse_duration import TimeDuration


class DataTreeItemNotFound(KeyError):
    """Thrown if a data tree item does NOT exist"""
    pass


class DataTreeItemBadValue(ValueError):
    """Thrown if a data tree item does NOT match expected type"""
    pass


class DataTreeBadPath(ValueError):
    """Thrown if part of the path is not a dict()"""
    pass


def get_item_value(tree, path, throw_exception=False, force_type=None):
    """
    For future use - see get_item().

    For now, get_item() tends to return "the value", but eventually it will
    return a data instance.

    Given path, like "route_api.local_ip", return raw (likely str)
    value

    If throw_exception=False (the default), then None is returned if the
    setting in 'path' is NOT FOUND, else throw a DataTreeItemNotFound
    exception. This allows distinguishing between an existing setting
    with value None, and one not found.

    Normally, the object returned is 'native' per the settings.json,
    which derived its values from the text settings.INI files.
    This means values are LIKELY string values. You can use force_type to
    do a smart-guess. For example, force_type=bool will cause the values
    (True, 1, "1", "true", "TRUE", "on", "enabled") to all return a
    simple bool() value True.

    :param dict tree:
    :param str path:
    :param bool throw_exception: return None, else DataTreeItemNotFound
    :param type force_type: if not None, try forcing a type
    :return:
    """
    if force_type is None:
        # then normal 'raw' handling
        result = get_item(tree, path, throw_exception)

    elif force_type == bool:
        # then handle things like T/F, "true"/"false", "0"/"1"
        result = get_item_bool(tree, path, throw_exception)

    elif force_type == int:
        # then handle things like 100, "  100", "0x234"
        result = get_item_int(tree, path, throw_exception)

    elif force_type == float:
        # then handle things like 100, "  100.3"
        result = get_item_float(tree, path, throw_exception)

    elif force_type == str:
        # then normal, but confirm is str(), except None != "None"
        result = get_item_value(tree, path, throw_exception)
        if result is not None:
            result = str(result)

    else:
        raise TypeError(
            "get_item_value doesn't handle type={}".format(force_type))

    return result


def get_item(tree, path, throw_exception=False):
    """
    Given a path, such as "route_api.local_ip", obtain the OBJECT it
    represents or None. For now, it works like get_item_value()

    If the path leads to nothing (doesn't exist) result is None, unless
    parameter throw_exception=True, which can be used to distinguish
    between a data tree item which exists but is None, verse not existing.

    :param dict tree: the data in dict tree
    :param str path: the path, such as "route_api.local_ip"
    :param bool throw_exception: if F return None, else DataTreeItemNotFound
    :return:
    """
    if not isinstance(tree, dict):
        raise TypeError("Data tree must be type(dict)")

    if not isinstance(path, str):
        raise TypeError("Data tree item path must be type(str)")

    tags = path.split('.')
    for leaf in tags:
        # walk down to find the desired node
        # print("Check tag:{}".format(leaf))
        if leaf not in tree:
            # then not found
            if throw_exception:
                raise DataTreeItemNotFound(
                    "Data tree item[{}] not found!".format(leaf))
            else:
                # print("Not found:{}".format(leaf))
                return None

        tree = tree[leaf]
        if isinstance(tree, dict):
            # see if we recurse, or return dict (sub-tree)
            if leaf != tags[-1]:
                # then NOT is the LAST tag in path, so loop for more
                continue

        return tree

    return None


def get_item_bool(tree, path, throw_exception=False):
    """
    Get the item value, intelligently forcing to True/False

    If value can't be forced well to bool, throw exception

    :param dict tree:
    :param str path:
    :param bool throw_exception:
    :return:
    """
    from cp_lib.parse_data import parse_boolean

    value = get_item(tree, path, throw_exception)
    if value is None:
        # assuming throw_exception=False, we'll return the None
        return None

    try:
        value = parse_boolean(value)

    except (ValueError, TypeError):
        raise DataTreeItemBadValue(
            "Item[{}] is not boolean type".format(value))

    return value


def get_item_int(tree, path, throw_exception=False):
    """
    Get the item value, intelligently forcing to integer

    If value can't be forced well to int, throw exception

    :param dict tree:
    :param str path:
    :param bool throw_exception:
    :return:
    """
    from cp_lib.parse_data import parse_integer

    value = get_item(tree, path, throw_exception)
    if value is None:
        # assuming throw_exception=False, we'll return the None
        return None

    try:
        value = parse_integer(value)

    except (ValueError, TypeError):
        raise DataTreeItemBadValue(
            "Item[{}] is not integer type".format(value))

    return value


def get_item_float(tree, path, throw_exception=False):
    """
    Get the item value, intelligently forcing to float

    If value can't be forced well to int, throw exception

    :param dict tree:
    :param str path:
    :param bool throw_exception:
    :return:
    """
    from cp_lib.parse_data import parse_integer_or_float

    value = get_item(tree, path, throw_exception)
    if value is None:
        # assuming throw_exception=False, we'll return the None
        return None

    try:
        value = parse_integer_or_float(value)

    except (ValueError, TypeError):
        raise DataTreeItemBadValue(
            "Item[{}] is not float type".format(value))

    # since may be int, force to float
    return float(value)


_time_duration = TimeDuration(0)


def get_item_time_duration_to_seconds(tree, path, throw_exception=False):
    """
    Get the item value, running through TimeDuration() to convert things
    like 300, "300 sec", and "5 min" to seconds

    If value can't be forced well to int, throw exception

    :param dict tree:
    :param str path:
    :param bool throw_exception:
    :return:
    """
    value = get_item(tree, path, throw_exception)
    if value is None:
        # assuming throw_exception=False, we'll return the None
        return None

    try:
        value = _time_duration.parse_time_duration_to_seconds(value)

    except (ValueError, TypeError):
        raise DataTreeItemBadValue(
            "Item[{}] is not duration type".format(value))

    return value


def put_item(tree, path, value, throw_exception=False):
    """
    Given a path, such as "route_api.local_ip", obtain the OBJECT it
    represents or None. For now, it works like get_item_value()

    If the path leads to nothing (doesn't exist) result is None, unless
    parameter throw_exception=True, which can be used to distinguish
    between a data tree item which exists but is None, verse not existing.

    :param dict tree: the data in dict tree
    :param str path: the path, such as "route_api.local_ip"
    :param value: the value to set - can be anything
    :param bool throw_exception: if F return None, else DataTreeItemNotFound
    :return:
    """
    if not isinstance(tree, dict):
        raise TypeError("Data tree must be type(dict)")

    if not isinstance(path, str):
        raise TypeError("Data tree item path must be type(str)")

    tags = path.split('.')
    item_tag = tags[-1]
    tags = tags[:-1]

    # first, make sure the 'path' exists
    for stem in tags:
        # walk down to find the desired node
        # print("Check tag:{}".format(leaf))
        if stem not in tree:
            # then not found
            tree[stem] = dict()

        elif not isinstance(tree[stem], dict):
            raise DataTreeBadPath("path element [{}] is not dict".format(stem))

        tree = tree[stem]

    # at this point, tree should 'point' to the location for item_tag
    tree[item_tag] = value
    return True


def data_tree_clean(tree):
    """
    Given a data tree, walk through and convert any "null", "true", or
    "False" to the raw Python values - it is not case sensitive.

    Note that this "clean" does not convert "0" to False, as at this level
    we cannot tell if is False or integer of 0

    :param dict tree:
    :return:
    """
    for tag, value in tree.items():
        # walk down to find the desired node
        if isinstance(value, dict):
            # then recurse
            data_tree_clean(value)

        elif isinstance(value, str):
            value = value.lower()
            if value == 'true':
                tree[tag] = True
            elif value == 'false':
                tree[tag] = False
            elif value in ('none', 'null'):
                tree[tag] = None

        # else, leave alone

    return


