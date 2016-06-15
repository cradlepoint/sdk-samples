from cp_lib.modbus.transaction_modbus import ModbusBadForm

# assume all valid functions are at least 6 x header plus uid + func
MBTCP_MINIMUM_LENGTH = 8


def encode_to_wire():
    """Is more complex than this simple routine supports"""
    raise NotImplementedError


def decode_from_wire():
    """Is more complex than this simple routine supports"""
    raise NotImplementedError


def validate_header(packet, test_len=True, expect_seq=None, expect_uid=None):
    """
    Confirm the header is as expected

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :param bool test_len: if True, confirm header len == packet len
    :param bytes expect_seq: if not None, confirm is a match
    :param int expect_uid: if not None, confirm is a match
    :return bool:
    """
    if len(packet) < MBTCP_MINIMUM_LENGTH:
        raise ModbusBadForm("MB/TCP packet is too short")

    if packet[2] != 0 and packet[3] != 0:
        raise ModbusBadForm("MB/TCP header has bad protocol version")

    value = (packet[4] * 256) + packet[5]
    if value + 6 != len(packet):
        raise ModbusBadForm("MB/TCP header has bad length")

    if expect_seq is not None:
        # sequence number is first 2 bytes
        if expect_seq != packet[:2]:
            raise ModbusBadForm("Unexpected Sequence Number")

    if expect_uid is not None:
        if expect_uid != int(packet[6]):
            raise ModbusBadForm("Unexpected Unit Id")

    if packet[4] != 0:
        raise ModbusBadForm("MB/TCP header has more than 256 bytes")

    if test_len:
        value = (packet[4] * 256) + packet[5]
        if value + 6 != len(packet):
            raise ModbusBadForm(
                "MB/TCP header length:{} != packet length:{}".format(
                    value + 6, len(packet)))

    return True


def test_end_of_message(data, is_request=True):
    """
    For use with the buffer object. A block of data is submitted, and this
    routine breaks it up to complete messages, or extra data not yet
    complete.

    :param bytes data:
    :param bool is_request: Modbus/TCP doesn't care about this
    :return: list of complete packets, plus any extra
    """

    # to have even a chance, we need at least 6 bytes, to see LENGTH field
    if len(data) < 6:
        return [], data

    if is_request:
        # suppress warning about unused parameter
        pass

    # now, have at least a full header
    if data[2] != 0 or data[3] != 0 or data[4] != 0:
        # then bad protocol version or length - discard all!
        return None, None

    if data[5] < 2:
        # then not enough data for uid + fnc
        return None, None

    messages = []
    extra = data
    while len(data):
        # print("data:{}".format(data))
        # print("msgs:{}".format(messages))
        if len(data) < 6:
            # then not a full header yet
            extra = data
            break

        length = int(data[5]) + 6
        if length > len(data):
            # then not a full packet yet
            extra = data
            break

        messages.append(data[:length])
        data = data[length:]
        extra = None

    return messages, extra
