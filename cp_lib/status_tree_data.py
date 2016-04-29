"""
Read/Write our data in status tree ( /status/system/sdk/apps[0] )
"""
import json

from cp_lib.app_base import CradlepointAppBase


class StatusTreeData(object):

    def __init__(self, app_base):
        """

        :param CradlepointAppBase app_base: resources: logger, settings, etc
        """
        assert isinstance(app_base, CradlepointAppBase)
        self.base = app_base

        # start out, we don't know our data
        self.slot = None
        self.uuid = None

        self.data = dict()
        self.clean = False
        return

    @staticmethod
    def get_url_sdk():
        """Return the URL in status tree for full SDK data"""
        return "status/system/sdk"

    def get_url_app_slot(self):
        """Return the URL for one specific APPS within status tree"""
        return "status/system/sdk/apps/{}".format(self.slot)

    def get_url_app_data(self):
        """Return URL for one specific APPS['usr_data'] within status tree"""
        return "status/system/sdk/apps/{}/usr_data".format(self.slot)

    def set_uuid(self, uuid):
        """

        :param uuid: the UUID to locate our apps[] slot
        """
        assert isinstance(uuid, str)

        result = self.base.cs_client.get(self.get_url_sdk())
        if not isinstance(result, dict):
            raise ValueError("SDK status tree not valid")

        # tree always has at least 'apps': [] (empty list)
        if 'apps' not in result:
            raise KeyError("SDK status tree, lacks ['apps'] data")

        if len(result['apps']) < 1:
            raise ValueError("No APPS installed in SDK status tree")

        # force back to None
        self.slot = None
        self.uuid = None

        try_index = 0
        for app in result['apps']:
            if "_id_" in app:
                data = string_list_status_apps(try_index, app)
                for line in data:
                    self.base.logger.debug("{}".format(line))
                if uuid == app["_id_"]:
                    self.slot = try_index
                    break

            try_index += 1

        if self.slot is None:
            # then NOT found!
            raise ValueError("UUID is not installed on router!")

        self.base.logger.debug("Found UUID in ['apps'][{}]".format(self.slot))
        self.uuid = uuid
        return

    def set_data_value(self, tag, value):
        """
        Set some value into our data block

        :param str tag:
        :param value:
        :return:
        """
        if tag in self.data:
            # then already here
            if self.data[tag] == value:
                # no change
                return False

        self.data[tag] = value
        self.clean = False
        return True

    def clear_data(self):
        """
        Delete our data from router, start clean with nothing here

        :return:
        """
        result = self.base.cs_client.delete(self.get_url_app_data())
        self.base.logger.debug("DATA={}".format(result))
        self.data = dict()
        self.clean = True
        return True

    def get_data(self):
        """
        Set some value into our data block

        :return:
        """
        result = self.base.cs_client.get(self.get_url_app_data())
        if result is None:
            self.base.logger.debug("DATA is empty")
            self.data = dict()
        else:
            self.data = result
            self.base.logger.debug("DATA={}".format(result))
        return True

    def put_data(self, force=False):
        """
        Set some value into our data block

        :param bool force: if T, write even if self.Clean
        :return:
        """
        if force or not self.clean:
            # then need to write our data
            if self.data is None:
                # then remove ['apps'][slot] from router
                raise NotImplementedError

            elif len(self.data) == 0:
                # then is empty item
                result = self.base.cs_client.put(
                    self.get_url_app_data(), "{}")

            else:
                # else has some data
                data = json.dumps(self.data)
                result = self.base.cs_client.put(
                    self.get_url_app_data(), data)

            self.base.logger.debug("RSP={}".format(result))
            self.clean = True

        return True


def string_list_status_apps(index, one_app, all_data=False):
    """
    Given STATUS return from Router, Make a list of strings to show ONE
    entry in APPS array value:
    {
        "_id_": "ae151650-4ce9-4337-ab6b-a16f886be569",
        "app": {
            "date": "2016-04-15T21:58:30Z",
            "name": "do_it",
            "restart": false,
            "uuid": "ae151650-4ce9-4337-ab6b-a16f886be569",
            "vendor": "Sample Code, Inc.",
            "version_major": 1,
            "version_minor": 0
        },
        "state": "stopped",
        "summary": "Stopped application",
        "type": "developer"
    }

    Results in the following lines
    SDK APP[0]    Name:do_it
    SDK APP[0]   State:stopped
    SDK APP[0] Summary:Stopped application
    SDK APP[0]    Date:2016-04-15T21:58:30Z
    SDK APP[0] Version:1.0
    SDK APP[0]    UUID:ae151650-4ce9-4337-ab6b-a16f886be569

    This does NOT enumerate through the APPS list

    :param int index: the index in ['apps']
    :param dict one_app: one entry in the array
    :param bool all_data: if T, include RESTART and VENDOR, else ignore
    :return list:
    """
    result = []

    app_tag = "SDK APP[%d]" % index

    if 'name' in one_app["app"]:
        result.append(
            "{0}    Name:{1}".format(app_tag, one_app['app']['name']))

    if 'state' in one_app:
        result.append(
            "{0}   State:{1}".format(app_tag, one_app['state']))

    if 'summary' in one_app:
        result.append(
            "{0} Summary:{1}".format(app_tag, one_app['summary']))

    if 'date' in one_app["app"]:
        result.append(
            "{0}    Date:{1}".format(app_tag, one_app['app']['date']))

    if 'version_major' in one_app["app"]:
        result.append("{0} Version:{1}.{2}".format(
            app_tag, one_app['app']['version_major'],
            one_app['app']['version_minor']))

    if '_id_' in one_app:
        result.append(
            "{0}    UUID:{1}".format(app_tag, one_app['_id_']))

    if all_data:
        # then include all data
        if 'type' in one_app:
            result.append(
                "{0}    type:{1}".format(app_tag, one_app['type']))

        if 'restart' in one_app["app"]:
            result.append(
                "{0} Restart:{1}".format(app_tag, one_app['app']['restart']))

        if 'vendor' in one_app["app"]:
            result.append(
                "{0}  Vendor:{1}".format(app_tag, one_app['app']['vendor']))

    return result
