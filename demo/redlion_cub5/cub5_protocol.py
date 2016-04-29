"""
The Redlion CUB5 protocol module
"""


class RedLionCub5(object):

    # will be like "N17" or "N5"
    CMD_NODE = "N"
    CMD_TRANSMIT = "T"  # means read ...

    NODE_MIN = 0
    NODE_MAX = 99

    MAP_ID = {
        "CTA": "A",  # counter A
        "CTB": "B",  # counter B
        "RTE": "C",  # rate
        "SFA": "D",  # scale factor A
        "SFB": "E",  # scale factor B
        "SP1": "F",  # setpoint 1 (reset output 1)
        "SP2": "G",  # setpoint 2 (reset output 2)
        "CLD": "H",  # counter A Count Load Value
    }

    # "*" means 50msec; "$" means 2msec
    TERMINATOR = "*"

    def __init__(self):

        self.node_address = 0
        # if node address = 0, can avoid sending, set this to True to override
        # and send anyway
        self.force_use_node_address = False

        # if set, allows normal logger output
        self.logger = None

        return

    def set_node_address(self, address):
        """
        Set the node address, which must be in value range 0-99

        :param int address: the new address
        :rtype str:
        """
        if address is None or not isinstance(address, int):
            raise ValueError("Invalid value for Node Address")

        assert self.NODE_MIN <= address <= self.NODE_MAX
        self.node_address = address
        return

    def format_node_address_string(self, address=None):
        """
        Fetch the Node string, which might be ""

        :param int address: optional pass in, else use self.node_address
        :rtype str:
        """
        if address is None:
            address = self.node_address

        address = int(address)

        if address == 0:
            # special case, return empty, unless forced
            if not self.force_use_node_address:
                return ""
            # else is being forced, so return as "N0"

        assert self.NODE_MIN <= address <= self.NODE_MAX
        # not width is auto, so 1 digit or two
        return "N%d" % address

    def format_read_value(self, mnemonic, address=None):
        """
        read a value
        :param str mnemonic: assume is  like "CTA", "SFA" and so on
        :param int address: optional pass in, else use self.node_address
        :return:
        """
        if address is None:
            address = self.node_address

        mnemonic = mnemonic.upper()
        code = self.MAP_ID[mnemonic]
        # throws KeyError if bad mnemonic
        return self.format_node_address_string(address) +\
            self.CMD_TRANSMIT + code + self.TERMINATOR

    def parse_response(self, response):
        """
        Parse a counter response
        :param response:
        :rtype dict:
        """
        if isinstance(response, bytes):
            # Convert bytes to string
            response = response.decode()

        if not isinstance(response, str):
            raise TypeError("bad response type")

        result = dict()
        result['raw'] = response.strip()
        result["status"] = True

        # address is bytes 1-2, then #3 = <space>
        x = response[:2]
        if x == "  ":
            result["adr"] = 0
        else:
            # else assume is a number?
            result["adr"] = int(x.strip())

        # get the mnemonic
        x = response[3:6].upper()
        if x in self.MAP_ID:
            result["id"] = x
        else:
            result["id"] = 'err?'
            result["status"] = False

        # get the data value
        # TODO - signed?
        x = response[6:18]
        try:
            result["data"] = int(x.strip())
        except ValueError:
            result["data"] = None
            result["status"] = False

        return result
