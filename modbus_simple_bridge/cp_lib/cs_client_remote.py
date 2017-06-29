"""CSClient Object"""

import json
import requests

from cp_lib.cs_client import CradlepointClient


class CradlepointClientRemote(CradlepointClient):

    # this makes our PUT match the CURL method, so we can send "data=x",
    # "application/json" doesn't work
    DEF_PUT_HEADER = {"Content-Type": "application/x-www-form-urlencoded"}
    # DEF_PUT_HEADER = {"Content-Type": "application/json"}
    APP_JSON = False

    def __init__(self):

        CradlepointClient.__init__(self)

        # save the last 'request' and 'response' - init in the base class
        # self.last_url = None, self.last_reply = None

        # this is the base URL used by request calls,
        # and will be like "http://192.168.1.1/api"
        # self.router_ip = None
        self.base_url = None

        # self.digest will hold the HTTPDigestAuth(),
        # ONCE the user/password are properly set
        self.digest = None

        return

    def get_url(self, path):
        """
        Append the existing 'base_url' (like "http://192.168.1.1/api/)
        with the path to create something
        like "http://192.168.1.1/api/status/system/sdk"

        :param str path:
        :return:
        """
        assert self.base_url is not None
        assert path is not None and isinstance(path, str)

        if path[0] == '/':
            # then we already have the '/'
            return self.base_url + path
        else:
            # else we're missing the slash, so add it here
            return self.base_url + '/' + path

    def set_router_ip(self, router_ip):
        """
        Create the DIGEST authentication handler, which handles the
        Cradlepoint's challenge/response to
        remote Router API (CURL-like) calls.

        :param str router_ip:
        :return:
        """
        assert router_ip is not None and isinstance(router_ip, str)

        self.router_ip = router_ip
        self.base_url = "http://{}/api".format(self.router_ip)

        # if self._logger is not None:
        #     self._logger.debug("CSClient() set router IP, url={}".format(
        #        self.base_url))
        return

    def set_user_password(self, user_name, password):
        """
        Create the DIGEST authentication handler, which handles the
        Cradlepoint's challenge/response to Router API (CURL-like) calls.

        :param str user_name:
        :param str password:
        :return:
        """
        from requests.auth import HTTPDigestAuth

        assert user_name is not None and isinstance(user_name, str)
        assert password is not None and isinstance(password, str)

        self.digest = HTTPDigestAuth(user_name, password)

        # if self._logger is not None:
        #     self._logger.debug("CSClient() set user={}, pass=*****".format(
        # user_name))
        return

    def get(self, base, query='', tree=0):
        """
        Send a get request, using the URI/element path name
        - example: self.state = self.client.get('/status/gpio/%s' % self.name)

        :param str base: element path, like /status/gpio/CGPIO_CONNECTOR_INPUT
        :param str query: ???
        :param int tree: ???
        """
        assert self.digest is not None
        assert self._logger is not None

        self.last_url = self.get_url(base)
        self._logger.debug("CSClient() GET {}".format(self.last_url))
        try:
            self.last_reply = requests.get(self.last_url, auth=self.digest)

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError):
            self._logger.error(
                "Timeout: router at {} did not respond.".format(
                    self.router_ip))
            return None

        return self._clean_up_reply()

    def _clean_up_reply(self):
        """

        :return:
        """
        if self.last_reply.status_code == 401:
            # then bad authentication
            result = "code=401 Unauthorized - is your password correct???"
            self._logger.error(result)

        elif self.last_reply.status_code != 200:
            result = "code={} other error".format(self.last_reply.status_code)
            self._logger.error(result)

        else:
            # was 200, so okay ... but response might be unexpected or error
            # self._logger.debug("RSP = [{}]".format(self.last_reply.json()))

            # example: {'data': None, 'success': True}
            result = self.last_reply.json()['data']

            if result is None:
                self._logger.error("no data returned")

            elif self.show_rsp:
                self._logger.debug("CSClient() RSP {}".format(result))
            # else we've suppressed the RSP

        return result

    # def get_typed(self, base, type_goal, query='', tree=0):

    def put(self, base, value, query='', tree=0):
        """
        Send a put request, which includes a bit of adjustment.

        The direct on router CSClient wants this form
        - example: self.client.put('/control/gpio', {self.name: self.state})

        However, since we are sending as "Content-Type":
        "application/x-www-form-urlencoded", we need to instead have
        client.put("control/gpio/CGPIO_CONNECTOR_OUTPUT", "data=%s" % value)

        :param str base: the element path, like '/status/gpio/LED_USB1_G'
        :param value: the payload, as JSON - such as {"LED_USB1_G":1}
        :param str query: ???
        :param int tree: ???
        """
        assert self.digest is not None
        assert self._logger is not None

        if self.APP_JSON:
            pass

        else:
            if isinstance(value, str):
                self.last_url = self.get_url(base)
                value = {'data': value}

            elif isinstance(value, dict):
                # change the client.put("control/gpio",
                # {"CGPIO_CONNECTOR_OUTPUT": value}) to be
                # like: client.put("control/gpio/CGPIO_CONNECTOR_OUTPUT",
                # "data=%s" % value)
                if len(value) == 1:
                    key_value = list(value.keys())[0]
                    data_value = value[key_value]
                    self.last_url = self.get_url(base + '/' + key_value)
                    if isinstance(data_value, str):
                        value = 'data=\"{}\"'.format(data_value)
                    else:
                        value = 'data={}'.format(data_value)

                else:
                    value = json.dumps(value)
                    self.last_url = self.get_url(base)

        self._logger.debug("CSClient() PUT {} {}".format(self.last_url, value))
        self.last_reply = requests.put(
            self.last_url, headers=self.DEF_PUT_HEADER,
            data=value, auth=self.digest)

        return self._clean_up_reply()

    def delete(self, base, query=''):
        """
        Send a delete request.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param str query: the text
        :return str:
        """
        assert self.digest is not None
        assert self._logger is not None

        self.last_url = self.get_url(base)
        self._logger.debug("CSClient() DELETE {}".format(self.last_url))
        try:
            self.last_reply = requests.delete(self.last_url, auth=self.digest)

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError):
            self._logger.error(
                "Timeout: router at {} did not respond.".format(
                    self.router_ip))
            return None

        result = self._clean_up_reply()
        # if there, then == True
        # if not there, then == {'exception': 'key', 'key': 'udata'}
        return result

    def append(self, base, value, query=''):
        """
        Send an append request.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param value: the payload, as JSON - such as {"LED_USB1_G":1}
        :type value: str or dict
        :param str query: ???
        :return str:
        """
        raise NotImplementedError

    def alert(self, name, value):
        """
        Send a request to create an alert.

        :param str name: the name to use in log
        :param str value: the text
        :return str:
        """
        result = "ALERT: {}: {}".format(name, value)
        self._logger.warning(result)
        # do simple comment - don't repeat the full response
        result = self.ALERT_SUCCESS
        return result

    def log(self, name, value):
        """
        Send a request to create a log entry.
        example: client.log('RouterSDKDemo', 'Sending alert to ECM.')

        :param str name: the name to use in log
        :param str value: the text
        :return str:
        """
        result = "LOG: {}: {}".format(name, value)
        self._logger.info(result)
        # do simple comment - don't repeat the full response
        result = self.LOG_SUCCESS
        return result

    def _dispatch(self, cmd):
        """
        Send the command and return the response.

        :param str cmd: the prepared command
        :return str:
        """
        raise NotImplementedError
