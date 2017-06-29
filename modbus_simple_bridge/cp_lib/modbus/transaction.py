
IA_PROTOCOL_ASCII = 'ascii'
IA_PROTOCOL_MBRTU = 'mbrtu'
IA_PROTOCOL_MBASC = 'mbasc'
IA_PROTOCOL_MBTCP = 'mbtcp'

IA_PROTOCOL_LIST = (IA_PROTOCOL_ASCII,
                    IA_PROTOCOL_MBRTU, IA_PROTOCOL_MBASC, IA_PROTOCOL_MBTCP)


class IaBadProtocol(ValueError):
    """
    An unknown protocol was referenced
    """
    pass


def validate_ia_protocol(value):
    """
    Confirm the 'value' string is a supported value

    :param str value:
    :return:
    """
    if not isinstance(value, str):
        raise TypeError(
            "IA Protocol must be type STR, not {}".format(type(value)))

    value = value.lower()
    if value not in IA_PROTOCOL_LIST:
        # then is not 'perfect' value
        if value in ('modbus/ascii', 'modbus/asc'):
            return IA_PROTOCOL_MBASC
        if value in ('modbus/rtu', 'mbus/rtu'):
            return IA_PROTOCOL_MBRTU
        if value in ('modbus/tcp', 'mbus/tcp'):
            return IA_PROTOCOL_MBTCP

        # else still here, thrown exception
        raise ValueError(
            "Unknown IA Protocol {}".format(type(value)))

    return value


class IaTransaction(object):
    """
    keyed data values:
    ['raw'] = the raw source request
    ['raw_protocol'] = what protocol the original/raw packet is, as str
    ['dst'] = destination, likely int but could be string
    ['src'] = optional source, likely int but could be string
    ['msg'] = the raw protocol message

    """

    # ['dst_id'] is the slave address, ['src_id'] is often not used
    KEY_SRC_ID = 'src_id'
    KEY_DST_ID = 'dst_id'

    # ['req_raw'] is the raw request, formatted as ['req_pro']
    KEY_REQ_RAW = 'req_raw'
    KEY_REQ_PROTOCOL = 'req_pro'
    KEY_RSP_RAW = 'rsp_raw'
    KEY_RSP_PROTOCOL = 'rsp_pro'

    # ['req_data'] is the stripped request, as Modbus ADU (no uid)
    KEY_REQ = 'req_adu'
    KEY_RSP = 'rsp_adu'

    # ['src_seq'] is saved, to allow RSP match up
    # ['dst_seq'] would be used uf different from ['src_seq']
    KEY_SRC_SEQ = 'src_seq'
    KEY_DST_SEQ = 'dst_seq'

    DEF_ID = 1
    DEF_SEQ = 0

    def __init__(self):
        self.attrib = dict()
        return

    def __getitem__(self, item):
        """Treat instance like keyed object"""
        return self.attrib[item]

    def __setitem__(self, key, value):
        """Treat instance like keyed object"""
        self.attrib[key] = value

    def get_dst_id(self, default=None):
        """return a default Id"""
        if default is None:
            default = self.DEF_ID
        return self.attrib.get(self.KEY_DST_ID, default)

    def get_src_id(self, default=None):
        """return a default Id"""
        if default is None:
            default = self.DEF_ID
        return self.attrib.get(self.KEY_SRC_ID, default)

    def get_sequence_number(self, default=None):
        """return a default Id"""
        if default is None:
            default = self.DEF_SEQ
        return self.attrib.get(self.KEY_SRC_SEQ, default)

    def get_protocol(self):
        """Get any set protocols"""
        if self.KEY_RSP_PROTOCOL in self.attrib:
            return self.attrib[self.KEY_RSP_PROTOCOL]

        if self.KEY_REQ_PROTOCOL in self.attrib:
            return self.attrib[self.KEY_REQ_PROTOCOL]

        raise ValueError("don't know which protocol to use")

    @staticmethod
    def validate_protocol(value):
        """
        Confirm the 'value' string is a supported value

        :param value:
        :return:
        """
        return validate_ia_protocol(value)

    def set_request(self, data, protocol):
        """
        Feed the request into the transaction

        :param bytes data: the raw data source
        :param protocol: the supported protocol (is required)
        :return:
        """
        # save the formatted source packet & what protocol it is
        self.attrib[self.KEY_REQ_RAW] = data

        # confirm the protocol is valid, will throw exception if not valid
        self.attrib[self.KEY_REQ_PROTOCOL] = self.validate_protocol(protocol)
        return True

    def get_request(self, protocol=None):
        """
        fetch the request, doing protocol form conversion

        :param protocol: if given, over-ride existing SRC protocol
        :return:
        """
        if self.KEY_REQ not in self.attrib:
            raise ValueError("No request data")

        if protocol is None:
            # if no protocol given, we'll want one of these
            if self.KEY_REQ_PROTOCOL in self.attrib:
                pass
            elif self.KEY_RSP_PROTOCOL in self.attrib:
                pass
            else:
                raise ValueError("Transaction lacks protocol")

        else:  # confirm protocol is valid, throw exception if not valid
            self.validate_protocol(protocol)

        return None

    def set_response(self, data, protocol):
        """
        Feed the response into the transaction

        :param bytes data: the raw data source
        :param protocol: the supported protocol
        :return:
        """
        # save the formatted source packet & what protocol it is
        self.attrib[self.KEY_RSP_RAW] = data
        # confirm the protocol is valid, will throw exception if not valid
        self.attrib[self.KEY_RSP_PROTOCOL] = self.validate_protocol(protocol)
        return True

    def get_response(self, protocol=None):
        """
        fetch the request, doing protocol form conversion

        :param protocol: if given, over-ride existing SRC protocol
        :return:
        """
        if self.KEY_RSP not in self.attrib:
            raise ValueError("No response data")

        if protocol is None:
            # if no protocol given, we'll want one of these
            if self.KEY_REQ_PROTOCOL in self.attrib:
                pass
            elif self.KEY_RSP_PROTOCOL in self.attrib:
                pass
            else:
                raise ValueError("Transaction lacks protocol")

        else:  # confirm protocol is valid, throw exception if not valid
            self.validate_protocol(protocol)

        return None

