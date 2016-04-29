# File: data_core.py
# Desc: the base class for the morsel project

# History:
#
# 1.0.0: 2015-Mar Lynn
#       * initial draft
#
# 1.1.0: 2016-Apr Lynn
#       * port to CP SDK
#
#

"""\
The data objects:

Attributes:
[
        self._required_keys = ['class', 'name', 'data_type']

Optional Attribute:
['description'] The user description, which is unicode. The description is
    usually something like "outdoor ambient temperature", or "the door
    switch on north wall".

['user_tag'] The user asset tag, which is unicode. The user asset tag is
    a user-assigned tag, such as "NE16273", which is used to identify
    something in other systems. It likely must be
    unique, however no uniqueness is enforced here!

"""

# from common.log_module import LogWrapper
from cp_lib.data.data_core import DataCore
# import cp_lib.data.cp_api as cp_api
# from data.data_types import validate_name

__version__ = "1.1.0"


_core_database = None


def get_core_database():
    """
    Obtain reference to the system's one central database object

    :rtype: DataBase
    """
    global _core_database

    if _core_database is None:
        _core_database = DataBase()
        assert _core_database.get_root() is not None
        # start_up_data_base(_core_database)

    return _core_database


def fetch_template_by_name(name: str):
    """
    Find an existing template, or return None (or throw exception)

    :rtype: DataTemplate or None
    """
    return _core_database.find_template_object(name)


class DataBase(DataCore):

    # singleton to hold the hashed object names
    # the pointer to the ROOT object, whose child list ultimately
    # holds every other object
    _DATA_ROOT = None

    # _DATA_SETTINGS is a special case of object, as the values are assumed
    # not to change often, plus MUST be held locally in non-volatile storage
    _DATA_SETTING = None

    # root template, acts as parent for all 'templates'
    _DATA_TEMPLATE = None

    # a simple list of objects, which can be processed in a loop; order
    # defined by creation time
    _DATA_ARRAY = []

    # These are what API element paths begin with, so like "data/tank/0/alarm"
    API_BASE_NAME_LIST = ('data', 'templates', 'settings', 'status',
                          'config', 'state', 'control')

    def __init__(self, name=None):

        if name is None:
            name = "database"

        if self._DATA_ROOT is None:

            super().__init__(name)

            # for the data base to have no parent
            self._parent = None

            self._attrib['class'] = self.code_name()

            # then this is the first init!
            DataBase._DATA_ROOT = DataCore('data')
            DataBase._DATA_TEMPLATE = DataCore('templates')
            DataBase._DATA_SETTING = DataCore('settings')

            DataBase._DATA_ARRAY = list()

            node = self._DATA_ROOT
            assert(isinstance(node, DataCore))
            node.set_parent(self)
            node.set_index(0)
            node.refresh_full_name()
            self._DATA_ARRAY.append(node)

            node = self._DATA_TEMPLATE
            assert(isinstance(node, DataCore))
            node.set_parent(self)
            node.set_index(1)
            node.refresh_full_name()
            self._DATA_ARRAY.append(node)

            node = self._DATA_SETTING
            assert(isinstance(node, DataCore))
            node.set_parent(self)
            node.set_index(2)
            node.refresh_full_name()
            self._DATA_ARRAY.append(node)

            # each module has it's own logger instance, which allows
            # varying logger output in larger systems.
            # DataBase.logger = LogWrapper("DataBase")
            # DataBase.logger.setLevel('DEBUG')

        # else is subsequent

        return

    @staticmethod
    def code_name():
        return 'DataBase'

    @staticmethod
    def code_version():
        return __version__

    def get_root(self):
        """
        :return: the root DataList instance
        :rtype: DataList
        """
        return self._DATA_ROOT

    def find_template_object(self, name: str):
        """
        Search for an object based on name, limiting search to the
        db_object._DATA_TEMPLATES list

        :param name:
        :return:
        """
        if self._DATA_TEMPLATE is not None:
            return self._DATA_TEMPLATE.find_child(name)
        return None

    def find_setting_object(self, name: str):
        """
        Search for an object based on name, limiting search to the
        db_object._DATA_SETTINGS list

        :param name:
        :return:
        """
        if self._DATA_SETTING is not None:
            return self._DATA_SETTING.find_child(name)
        return None

    def find_data_object(self, name: str):
        """
        Search for an object based on name, limiting search to the
        db_object._DATA_SETTINGS list

        :param name:
        :return:
        """
        if self._DATA_ROOT is not None:
            return self._DATA_ROOT.find_child(name)
        return None

    def find_object(self, name: str):
        """
        Search for an object based on name, limiting search to the
        db_object._DATA_SETTINGS list

        :param name:
        :return:
        """
        # this throws error is anything is wrong with the name, plus
        #   forces case, etc
        if self._DATA_ROOT is not None:
            node = self._DATA_ROOT.find_child(name)
            if node is not None:
                return node

        if self._DATA_SETTING is not None:
            node = self._DATA_SETTING.find_child(name)
            if node is not None:
                return node

        if self._DATA_TEMPLATE is not None:
            node = self._DATA_TEMPLATE.find_child(name)
            if node is not None:
                return node

        return None

    # messages.extend(make_data_array_report(db_object._DATA_ARRAY))

    def add_to_data_base(self, node, overwrite=False):
        """

        :param node: the node to add, must be derived from DataCore (won't
                     be None - just include to suppress warnings)
        :type node: DataCore or None
        :param overwrite: if False, throw exception for a duplicate name
        :type overwrite: bool
        :return:
        :rtype: str
        """

        # first, handle the need for a unique ['data_name']

        full_name = node.get_full_name()

        role = node['role']
        if role == "setting":
            assert self._DATA_SETTING is not None
            self._DATA_SETTING.add_child(node)
            # DataBase.logger.debug("Add Setting({0})".format(node.get_name()))

        elif role == "template":
            assert self._DATA_TEMPLATE is not None
            self._DATA_TEMPLATE.add_child(node)
            # .logger.debug("Add Template({0})".format(node.get_name()))

        elif role != "core":   # if role any other
            if node.get_parent() is None:
                # then add to the root
                assert self._DATA_ROOT is not None
                self._DATA_ROOT.add_child(node)
                # .logger.debug("Add Data({0})".format(node.get_name()))

        assert self._DATA_ARRAY is not None
        index = len(self._DATA_ARRAY)
        DataBase._DATA_ARRAY.append(node)

        node.set_index(index)
        return full_name

    def build_list_names(self, recursive=True):
        """
        :return: a list of DataList names starting at our root
        :rtype: list of str
        """
        return self._DATA_ROOT.build_list_names(None, recursive)

    def build_object_names(self, root=None, recursive=True):
        """
        :return: a list of DatObject names starting at our root
        :rtype: list of str
        """
        return self._DATA_ROOT.build_object_names(None, recursive)

    def get_data_array(self):
        return self._DATA_ARRAY

    def get_data_root(self):
        return self._DATA_ROOT

    def get_template_root(self):
        return self._DATA_TEMPLATE

    def get_setting_root(self):
        return self._DATA_SETTING

    def split_object_path(self, path: str):
        """
        Given a path such as "/data/tank/0/alarm/hi_alm", return a list
        of the base names, such as ["data", "tank", "0", "alarm", "hi_alm"]
        Any leading or trailing empty names are discarded, plus filesystem
        names such as "C:", "users", or "api" are also deleted.

        Note that this routine does NOT validate any of the names! This is
        merely the splitters.
        """
        if not isinstance(path, str) or len(path) < 1:
            raise ValueError("API Path must be longer than zero/None")

        path = path.lower()
        # value = path.split(cp_api.ApiRouter.SEP)
        value = path.split('.')

        if value[-1] == "":
            # then remove - is created in case of "... anything/"
            value.pop(-1)

        while len(value) and value[0] not in self.API_BASE_NAME_LIST:
            # then remove this undesired name
            value.pop(0)

        return value

    def fetch_object_path_list(self, path: str):
        """
        Given path such as "/data/tank/0/alarm/hialm", return a list of DATA
        object references. See split_object_path() to understand how split.
        """
        path_list = self.split_object_path(path)
        value = list()

        if path_list[0] == 'data':
            value.append(self._DATA_ROOT)

        elif path_list[0] == 'templates':
            value.append(self._DATA_TEMPLATE)

        elif path_list[0] == 'settings':
            value.append(self._DATA_SETTING)

        else:
            raise ValueError("API Path objects are not valid")

        return value


def start_up_data_base(db):
    """

    :param db:
    :type db: DataBase
    :return:
    """
    from cp_lib.data.templates.template_health import TemplateHealth
    # define and add the default templates

    value = TemplateHealth()
    db.add_to_data_base(value)

    return


def print_base_report(db_object: DataBase, do_print=True):

    messages = list()
    messages.append("Database Report: name({0})".format(db_object.get_name()))

    # db_object._DATA_OBJECTS is None:
    messages.extend(db_object.get_data_root().my_report())
    messages.extend(db_object.get_template_root().my_report())
    messages.extend(db_object.get_setting_root().my_report())
    # messages.extend(db_object.get_data_array().my_report())

    if do_print:
        for line in messages:
            print(line)

    return messages
