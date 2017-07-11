"""
CradlepointClient Object, is meant to run on the router.

Use CradlepointClientRemote() from a PC. I split the two up to make sure
the TAR.GZIP bundle never needs to deal with the dependencies of the
fancier PC/computer object. CradlepointClientRemote() is derived from
CradlepointClient primarily to help keep the functionality and call
format in sync.
"""

import json
import socket
import sys

# fix case where string "IBR1100" is actually returned as "\"IBR1100\""
from cp_lib.unquote_string import unquote_string
from cp_lib.buffer_dump import logger_buffer_dump


class CradlepointClient(object):
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 1337
    DEFAULT_SIZE = 1024

    """Wrapper for the TCP interface to the router config store."""

    RSP_SEEK_STATUS = 0
    RSP_SEEK_LENGTH = 1
    RSP_SEEK_DATA = 2

    LOG_SUCCESS = "Log added"
    ALERT_SUCCESS = "Alert added"

    def __init__(self):

        # save the last 'request' and 'response'
        self.last_url = None
        self.last_reply = None

        # chain in our logging instance
        self._logger = None

        # set False to not dump responses (they might be huge!)
        self.show_rsp = True

        # RSP_SEEK_STATUS, RSP_SEEK_LENGTH, RSP_SEEK_DATA = 2
        self._seek_state = self.RSP_SEEK_STATUS
        self._data_length = 0

        self.router_ip = 'localhost'

        return

    def set_logger(self, use_logger):
        """

        :param use_logger:
        :return:
        """
        self._logger = use_logger
        return

    def get(self, base, query='', tree=0):
        """
        Send a get request.
        - example: self.state = self.client.get('/status/gpio/%s' % self.name)

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param str query: ???
        :param int tree: ???
        """
        self._logger.debug("CSClient() GET={}".format(base))
        self.last_url = "get\n{}\n{}\n{}\n".format(base, query, tree)
        if self.show_rsp:
            logger_buffer_dump(self._logger, 'GET', self.last_url,
                               show_ascii=True)
        return self._dispatch(self.last_url)

    def get_bool(self, base, query='', tree=0):
        """
        Send a get request, force data to be BOOL.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param str query: ???
        :param int tree: ???
        """
        result = self.get(base, query, tree)
        if result is None:
            # most likely data item is NOT exist!
            return None

        if result in (0, '0', '\"0\"', False, 'false', 'False', 'FALSE'):
            # handle common known forms of False
            return False

        if result in (1, '1', '\"1\"', True, 'true', 'True', 'TRUE'):
            # handle common known forms of True
            return False

        return bool(result)

    def get_str(self, base, query='', tree=0):
        """
        Send a get request, force data to be BOOL.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param str query: ???
        :param int tree: ???
        """
        result = self.get(base, query, tree)
        if result is None:
            # most likely data item is NOT exist!
            return None

        if isinstance(result, bytes):
            return result.decode('ascii')
        else:
            return str(result)

    def get_typed(self, base, type_goal, query='', tree=0):
        """
        Send a get request.
        - example: self.state = self.client.get('/status/gpio/%s' % self.name)

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param type type_goal:
        :param str query: ???
        :param int tree: ???
        """
        if type_goal == bool:
            return self.get_bool(base, query, tree)

        elif type_goal == str:
            return self.get_str(base, query, tree)

        else:
            raise TypeError

    def put(self, base, value, query='', tree=0):
        """
        Send a put request.
        - example: self.client.put('/control/gpio', {self.name: self.state})

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param value: the payload, as JSON - such as {"LED_USB1_G":1}
        :type value: str or dict
        :param str query: ???
        :param int tree: ???
        """
        value = json.dumps(value).replace(' ', '')

        self._logger.debug("CSClient() PUT={} data={}".format(base, value))
        self.last_url = "put\n{}\n{}\n{}\n{}\n".format(base, query,
                                                       tree, value)
        logger_buffer_dump(self._logger, 'PUT', self.last_url, show_ascii=True)
        return self._dispatch(self.last_url)

    def append(self, base, value, query=''):
        """
        Send an append request.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param value: the payload, as JSON - such as {"LED_USB1_G":1}
        :type value: str or dict
        :param str query: ???
        :return str:
        """
        value = json.dumps(value).replace(' ', '')
        self._logger.debug("CSClient() APPEND={} data={}".format(base, value))
        self.last_url = "post\n{}\n{}\n{}\n".format(base, query, value)
        logger_buffer_dump(self._logger, 'APPEND', self.last_url,
                           show_ascii=True)
        return self._dispatch(self.last_url)

    def delete(self, base, query=''):
        """
        Send a delete request.

        :param str base: 'tree' element path, like '/status/gpio/LED_USB1_G'
        :param str query: the text
        :return str:
        """
        self._logger.debug("CSClient() DEL={}".format(base))
        self.last_url = "delete\n{}\n{}\n".format(base, query)
        logger_buffer_dump(self._logger, 'DELETE', self.last_url,
                           show_ascii=True)
        return self._dispatch(self.last_url)

    def alert(self, name, value):
        """
        Send a request to create an alert.

        :param str name: the name to use in log
        :param str value: the text
        :return str:
        """
        self._logger.debug("CSClient() ALERT={} {}".format(name, value))
        self.last_url = "alert\n{}\n{}\n".format(name, value)
        # logger_buffer_dump(self._logger, 'ALERT', self.last_url,
        #                    show_ascii=True)
        result = self._dispatch(self.last_url)
        # expect: "\r\n\r\nAlert added('RouterSDKDemo: ... "
        """ :type result: str """
        if result.startswith('Alert added'):
            # do simple comment - don't repeat the full response
            result = self.ALERT_SUCCESS
        else:
            self._logger.debug("CS ALERT={}".format(result))
        return result

    def log(self, name, value):
        """
        Send a request to create a log entry.
        example: client.log('RouterSDKDemo', 'Sending alert to ECM.')

        :param str name: the name to use in log
        :param str value: the text
        :return str:
        """
        self._logger.debug("CSClient() LOG={} {}".format(name, value))
        self.last_url = "log\n{}\n{}\n".format(name, value)
        # logger_buffer_dump(self._logger, 'LOG', self.last_url,
        #                    show_ascii=True)
        result = self._dispatch(self.last_url)
        # expect: "\r\n\r\nLog added('RouterSDKDemo: ... "
        """ :type result: str """
        if result.startswith('Log added'):
            # do simple comment - don't repeat the full response
            result = self.LOG_SUCCESS
        else:
            self._logger.debug("CS LOG={}".format(result))
        return result

    def _dispatch(self, cmd):
        """
        Send the command and return the response.

        How the router actually responds is a bit fuzzy, and I've seen
        several conflicting solutions which assume a more line-by-line
        behavior, which I am not seeing in 6.1 (Mar-16)

        :param str cmd: the prepared command
        :return str:
        """
        self.last_reply = None
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self.DEFAULT_HOST, self.DEFAULT_PORT))
            sock.sendall(cmd.encode('ascii'))

            data = sock.recv(self.DEFAULT_SIZE).decode('ascii').strip()
            """ :type data: str """
            # logger_buffer_dump(self._logger, 'header', data, show_ascii=True)
            if data.startswith('status: ok'):

                if len(data) > 18:
                    # on some occasions, 'content-length: ' will be appended!
                    # the length 18 is a bit arbitrary. The desired status
                    # is "status: ok\n", so 11 bytes
                    self._logger.debug(
                        "Special STATUS() packing, len={}".format(len(data)))
                    data = data[11:].strip()

                else:
                    data = sock.recv(self.DEFAULT_SIZE)

                if self.show_rsp:
                    data_expected, self.last_reply = _fetch_content_length(
                        data, self._logger)
                else:
                    data_expected, self.last_reply = _fetch_content_length(
                        data, None)

                retry = 0
                while data_expected > 0:
                    # data = sock.recv(self.DEFAULT_SIZE).decode('ascii')
                    data = sock.recv(self.DEFAULT_SIZE).decode('ascii')
                    if self.show_rsp:
                        logger_buffer_dump(self._logger, 'loop', data,
                                           show_ascii=True)
                    if data.startswith('\r\n\r\n'):
                        # this was form B, so second block of data started
                        # with the 2 dummy lines
                        data = data[4:]

                    if len(data) == 0:
                        if retry > 3:
                            self._logger.debug("CSClient len(data)==0, BREAK")
                            break
                        retry += 1
                        self._logger.debug(
                            "CSClient() len(data)==0, retry={}".format(retry))
                    self.last_reply += data
                    data_expected -= len(data)
                    if data_expected:
                        # only show is NOT zero
                        self._logger.debug(
                            "pst expected={}".format(data_expected))

        if len(self.last_reply) >= 2:
            # reply might be nothing, but if string, we make sure to handle
            if self.last_reply[0] == '\"':
                # remove leading/trailing quotes, so make "\"IBR1100LPE\""
                # into "IBR1100LPE"
                self.last_reply = unquote_string(self.last_reply)

            elif self.last_reply[0] == '{':
                # convert JSON string to dict(), like:
                # '{"enable_gps_keepalive": false, "pwd_enabled": false,
                #   "enabled": true}'

                # self._logger.debug("final{}".format(self.last_reply))
                try:
                    self.last_reply = json.loads(self.last_reply)

                except ValueError:
                    # some idiotic API calls return malformed JSON such as
                    # "{'enabled': true}" so not double quotes!
                    self.last_reply = self.last_reply.replace("\'", "\"")

                    # if it still fails, then assume worse error
                    self.last_reply = json.loads(self.last_reply)

        return self.last_reply


def _fetch_content_length(data, logger=None):
    """
    handle the situation where response might be either:

    form A = 'content-length: 12\n\r\n\r\n"IBR1150LPE"'
    form B = 'content-length: 189'

    :param data:
    :return:
    """
    if isinstance(data, bytes):
        data = data.decode('ascii')
    data = data.strip()

    if logger is not None:
        logger_buffer_dump(logger, 'length', data, show_ascii=True)

    if not data.startswith('content-length: '):
        # then it is mal-formed!
        return None, None

    # chop off the 'content-length: ' with the ending space
    data = data[16:]
    # form A now = '12\n\r\n\r\n"IBR1150LPE"'
    # form B now = '189'

    offset = data.find('\n')
    if offset <= 0:
        # then form B like, so data_length = '189'
        data_length = data.strip()
        all_data = ""

    else:
        # else is form A like
        #  data_length = '12'
        #  data = '"IBR1150LPE"'
        data_length = data[:offset].strip()
        all_data = data[offset + 4:].strip()

    try:
        data_length = int(data_length)
    except ValueError:
        # then bad length field!
        if logger is not None:
            logger.error("CSClient() content length not INT()")
        return None, None

    if logger is not None:
        logger.debug("data_length={}".format(data_length))
        if len(all_data):
            logger_buffer_dump(logger, 'ready', all_data, show_ascii=True)
        # else is empty

    # change to be REMAINING data
    data_length -= len(all_data)

    return data_length, all_data

    # The actual response to GET status/product_info/product_name is:
    #     status: ok\n
    #     content-length: 12\n
    #     \r\n
    #     \r\n
    #     "IBR1100LPE"
    # First 2 lines ONLY end in '\n', then 2 blank lines with both '\r\n',
    # then data without any EOL.

    # The actual response to GET status/product_info/junkie (invalid path) is:
    #     status: ok\n
    #     content-length: 4\n
    #     \r\n
    #     \r\n
    #     null
    # So like a good path, but the word null is the data


def init_cs_client_on_my_platform(logger, sets):
    """
    Do the platform-specific init for the logger.

    :param logger: a log/trace object which acts like logging (but may not be)
    :param dict sets: the processed settings.json file
    :return: given platform LINUX2 or other, init the native CP CSClient
             or a computer-based one
    """
    if sys.platform == "linux2":
        # then this is a Cradlepoint router
        client = CradlepointClient()
        client.set_logger(logger)

    else:
        # assume is a PC with full library -
        #   including http://docs.python-requests.org
        from cp_lib.cs_client_remote import CradlepointClientRemote

        client = CradlepointClientRemote()
        client.set_logger(logger)

        # these MUST be true, else we fail
        if "router_api" not in sets:
            raise KeyError("settings missing [router_api] section")

        client.set_router_ip(sets["router_api"]["local_ip"])
        user = sets["router_api"].get("user_name", "admin")
        client.set_user_password(user, sets["router_api"]["password"])

    return client
