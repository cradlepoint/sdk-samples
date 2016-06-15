import cp_lib.modbus.transaction as transaction


class ModbusBadForm(ValueError):
    """A general failure in parsing Modbus"""
    pass


class ModbusBadChecksum(ValueError):
    """A bad CRC/LRC in parsing Modbus"""
    pass


class ModbusTransaction(transaction.IaTransaction):

    def __init__(self):
        super().__init__()
        return

    def set_request(self, data, protocol=None):
        """

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        # sets self[KEY_REQ_RAW] and self[KEY_REQ_PROTOCOL]
        super().set_request(data, protocol)

        if protocol == transaction.IA_PROTOCOL_MBASC:
            result = self._mbasc_set_request(data)
            max_data = 252

        elif protocol == transaction.IA_PROTOCOL_MBRTU:
            result = self._mbrtu_set_request(data)
            max_data = 252

        elif protocol == transaction.IA_PROTOCOL_MBTCP:
            result = self._mbtcp_set_request(data)
            max_data = 255

        else:
            raise transaction.IaBadProtocol(
                "Unknown IA Protocol:{}".format(protocol))

        if len(self[self.KEY_REQ]) > max_data:
            raise ModbusBadForm(
                "data length () is too long".format(len(self[self.KEY_REQ])))

        return result

    def get_request(self, protocol=None):
        """

        :param protocol: the supported protocol
        :return:
        """
        # sets self[KEY_REQ_RAW] and self[KEY_REQ_PROTOCOL]
        super().get_request(protocol)

        if protocol is None:
            # will throw exception, if neither DST or SRC set
            protocol = self.get_protocol()

        if protocol == transaction.IA_PROTOCOL_MBASC:
            result = self._mbasc_get_request()

        elif protocol == transaction.IA_PROTOCOL_MBRTU:
            result = self._mbrtu_get_request()

        elif protocol == transaction.IA_PROTOCOL_MBTCP:
            result = self._mbtcp_get_request()

        else:
            raise transaction.IaBadProtocol(
                "Unknown IA Protocol:{}".format(protocol))

        return result

    def set_response(self, data, protocol=None):
        """

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        # sets self[KEY_REQ_RAW] and self[KEY_REQ_PROTOCOL]
        super().set_response(data, protocol)

        if protocol == transaction.IA_PROTOCOL_MBASC:
            result = self._mbasc_set_response(data)
            max_data = 252

        elif protocol == transaction.IA_PROTOCOL_MBRTU:
            result = self._mbrtu_set_response(data)
            max_data = 252

        elif protocol == transaction.IA_PROTOCOL_MBTCP:
            result = self._mbtcp_set_response(data)
            max_data = 255

        else:
            raise transaction.IaBadProtocol(
                "Unknown IA Protocol:{}".format(protocol))

        if len(self[self.KEY_RSP]) > max_data:
            raise ModbusBadForm(
                "data length () is too long".format(len(self[self.KEY_RSP])))

        return result

    def get_response(self, protocol=None):
        """

        :param protocol: the supported protocol
        :return:
        """
        super().get_response(protocol)

        if protocol is None:
            # will throw exception, if neither DST or SRC set
            protocol = self.get_protocol()

        if protocol == transaction.IA_PROTOCOL_MBASC:
            result = self._mbasc_get_response()

        elif protocol == transaction.IA_PROTOCOL_MBRTU:
            result = self._mbrtu_get_response()

        elif protocol == transaction.IA_PROTOCOL_MBTCP:
            result = self._mbtcp_get_response()

        else:
            raise transaction.IaBadProtocol(
                "Unknown IA Protocol:{}".format(protocol))

        return result

    def get_no_response_error(self, protocol=None):
        """
        return the correct response for a time-out/no answer

        :param protocol: the supported protocol
        :return:
        """
        # super().get_response(protocol)

        if protocol is None:
            # will throw exception, if neither DST or SRC set
            protocol = self.get_protocol()

        if protocol == transaction.IA_PROTOCOL_MBASC:
            # Modbus/ASCII returns nothing
            result = None

        elif protocol == transaction.IA_PROTOCOL_MBRTU:
            # Modbus/RTU returns nothing
            result = None

        elif protocol == transaction.IA_PROTOCOL_MBTCP:
            # Modbus/TCP, we want the exception 0x0B, so in effect create a
            # 'fake' self[self.KEY_RSP]

            # start with the command, set the MSB and append the err code
            value = [self[self.KEY_REQ][0] | 0x80, 0x0B]
            self[self.KEY_RSP] = bytes(value)
            result = self._mbtcp_get_response()

        else:
            raise transaction.IaBadProtocol(
                "Unknown IA Protocol:{}".format(protocol))

        return result

    def _mbasc_set_request(self, data):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :return:
        """
        from cp_lib.modbus.modbus_asc import decode_from_wire

        self[self.KEY_REQ_PROTOCOL] = transaction.IA_PROTOCOL_MBASC

        # first, confirm is valid request, returns bytes
        request = decode_from_wire(data)

        self[self.KEY_DST_ID] = int(request[0])
        self[self.KEY_REQ] = request[1:]
        return True

    def _mbrtu_set_request(self, data, protocol=None):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        from cp_lib.modbus.modbus_rtu import decode_from_wire

        self[self.KEY_REQ_PROTOCOL] = transaction.IA_PROTOCOL_MBRTU

        # first, confirm is valid request, returns bytes
        request = decode_from_wire(data)

        self[self.KEY_DST_ID] = int(request[0])
        self[self.KEY_REQ] = request[1:]
        return True

    def _mbtcp_set_request(self, data, protocol=None):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        from cp_lib.modbus.modbus_tcp import validate_header

        self[self.KEY_REQ_PROTOCOL] = transaction.IA_PROTOCOL_MBTCP

        # this also tests length, etc
        validate_header(data)

        # sequence number is first 2 bytes
        self[self.KEY_SRC_SEQ] = data[:2]
        self[self.KEY_DST_ID] = int(data[6])
        self[self.KEY_REQ] = data[7:]
        return True

    def _mbasc_get_request(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        from cp_lib.modbus.modbus_asc import encode_to_wire

        indication = bytes([self.get_dst_id()]) + self[self.KEY_REQ]
        return encode_to_wire(indication)

    def _mbrtu_get_request(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        from cp_lib.modbus.modbus_rtu import encode_to_wire

        indication = bytes([self.get_dst_id()]) + self[self.KEY_REQ]
        return encode_to_wire(indication)

    def _mbtcp_get_request(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        indication = self._mbtcp_get_sequence_number() + b'\x00\x00\x00'
        indication += bytes([len(self[self.KEY_REQ]) + 1, self.get_dst_id()])
        indication += self[self.KEY_REQ]
        return indication

    def _mbasc_set_response(self, data):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :return:
        """
        from cp_lib.modbus.modbus_asc import decode_from_wire

        self[self.KEY_RSP_PROTOCOL] = transaction.IA_PROTOCOL_MBASC

        # first, confirm is valid request, returns bytes
        response = decode_from_wire(data)

        if self[self.KEY_DST_ID] != int(response[0]):
            raise ModbusBadForm("Unexpected Unit Id in response")

        self[self.KEY_RSP] = response[1:]
        return True

    def _mbrtu_set_response(self, data, protocol=None):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        from cp_lib.modbus.modbus_rtu import decode_from_wire

        self[self.KEY_RSP_PROTOCOL] = transaction.IA_PROTOCOL_MBRTU

        # first, confirm is valid request, returns bytes
        response = decode_from_wire(data)

        if self[self.KEY_DST_ID] != int(response[0]):
            raise ModbusBadForm("Unexpected Unit Id in response")

        self[self.KEY_RSP] = response[1:]
        return True

    def _mbtcp_set_response(self, data, protocol=None):
        """
        Given a raw MB/ASC request, break up to internal form

        :param bytes data:
        :param protocol: the supported protocol
        :return:
        """
        from cp_lib.modbus.modbus_tcp import validate_header

        self[self.KEY_RSP_PROTOCOL] = transaction.IA_PROTOCOL_MBTCP

        # this also tests length, etc
        validate_header(data, expect_seq=self[self.KEY_SRC_SEQ],
                        expect_uid=self[self.KEY_DST_ID])

        self[self.KEY_RSP] = data[7:]
        return True

    def _mbasc_get_response(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        from cp_lib.modbus.modbus_asc import encode_to_wire

        indication = bytes([self.get_dst_id()]) + self[self.KEY_RSP]
        return encode_to_wire(indication)

    def _mbrtu_get_response(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        from cp_lib.modbus.modbus_rtu import encode_to_wire

        indication = bytes([self.get_dst_id()]) + self[self.KEY_RSP]
        return encode_to_wire(indication)

    def _mbtcp_get_response(self):
        """
        Assuming internal form, create the raw wire request to send

        :return bytes:
        """
        indication = self._mbtcp_get_sequence_number() + b'\x00\x00\x00'
        indication += bytes([len(self[self.KEY_RSP]) + 1, self.get_dst_id()])
        indication += self[self.KEY_RSP]
        return indication

    def _mbtcp_get_sequence_number(self, value=None):
        """
        get sequence, making sure is 2 bytes

        :return bytes:
        """
        if value is None:
            value = self.get_sequence_number()

        if isinstance(value, int):
            # if an int, convert to 2 bytes, big-endian
            value = bytes([(value & 0xFF00) >> 8,
                                value & 0xFF])

        if not isinstance(value, bytes):
            raise TypeError("MB/TCP sequence must be type(bytes)")

        # force to be at least 2 bytes
        if len(value) < 2:
            value += b'\x01\x01'

        if len(value) > 2:
            value = value[:2]

        return value
