from cp_lib.modbus.transaction_modbus import ModbusBadForm, ModbusBadChecksum

# assume all valid functions are at least
MBASC_MINIMUM_LENGTH = 2


def calc_checksum(packet):
    """
    given an ASCII packet like b'\x01\x03\x00\x00\x00\x0A', return the LRC

    note that we need the raw binary, not the ASCII form!

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :return:
    """
    if not isinstance(packet, bytes):
        raise TypeError("MB/ASC packet must be type(bytes)")

    if len(packet) < MBASC_MINIMUM_LENGTH:
        raise ModbusBadForm("MB/ASC packet is too short")

    checksum = sum(by for by in packet) & 0xFF
    checksum = (checksum ^ 0xFF) + 1
    return checksum & 0xFF


def encode_to_wire(packet):
    """
    Given a packet array like b'\x01\x03\x00\x00\x00\x0A', encode it for the
    wire as b':01030000000AF2\r\n' (plus force to upper case)

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :return bytes:
    """
    from binascii import b2a_hex

    # will raise ModbusAsciiBadForm() if too short, TypeError
    calc_lrc = calc_checksum(packet)
    result = '%02X\r\n' % calc_lrc
    result = b':' + b2a_hex(packet) + result.encode()
    return result.upper()


def decode_from_wire(packet):
    """
    given an ASCII packet like b':01030000000AF2\r\n', return the raw data
    as byte array, so would be b'\x01\x03\x00\x00\x00\x0A'

    If LRC is bad, throw exception ModbusAsciiBadForm
    If data is odd-count, or bad chars, throw exception ModbusAsciiBadForm

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :return bytes:
    """
    from binascii import a2b_hex, Error

    if not isinstance(packet, bytes):
        raise TypeError("MB/ASC packet must be bytes")

    if packet[0] != 58:
        raise ModbusBadForm("bad START byte, {} != ':'".format(packet[0]))

    # missing \r\n is okay, so feel out
    if packet[-2] == 0x0D:
        # then full form
        packet = packet[1:-2]

    elif packet[-1] in (0x0D, 0x0A):
        # then only 1 EOLN
        packet = packet[1:-1]

    else:  # assume the EOL were stripped
        packet = packet[1:]

    try:
        see_lrc = a2b_hex(packet[-2:])[0]
        packet = a2b_hex(packet[:-2])
    except Error:
        # this is odd number of bytes, or invalid chars
        raise ModbusBadForm("Bad HEX form - odd byte count or bad chars")

    calc_lrc = calc_checksum(packet)
    if see_lrc != calc_lrc:
        raise ModbusBadChecksum(
            "bad LRC, see:{} calc:{}".format(see_lrc, calc_lrc))

    return packet


def test_end_of_message(data, is_request=True):
    """
    For use with the buffer object. A block of data is submitted, and this
    routine breaks it up to complete messages, or extra data not yet
    complete.

    :param bytes data:
    :param bool is_request: Modbus/ASCII doesn't care about this
    :return: list of complete packets, plus any extra
    """

    # first we discard any leading garbage - looking for the ':'
    while True:
        if not len(data):
            # then no more data
            return None, None

        if data[0] == 58:
            # then good start delimiter
            break
        # discard first byte of garbage
        data = data[1:]

    # at this point, have START, look for \N
    assert data[0] == 58

    if is_request:
        # suppress warning about unused parameter
        pass

    messages = []
    extra = data
    while len(data):
        offset = data.find(b'\n')
        if offset < 0:
            # then no \N
            extra = data
            break

        messages.append(data[:offset + 1])
        data = data[offset + 1:]
        extra = None

    return messages, extra
