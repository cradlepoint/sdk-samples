from cp_lib.modbus.transaction_modbus import ModbusBadForm, ModbusBadChecksum

# assume all valid functions are at least {uid} {function}
MBRTU_MINIMUM_LENGTH = 2
_crc_table = None
MODBUS_START_CRC = 0xFFFF


def _init_table():
    """Pre-seed our XMODEM look up table"""
    global _crc_table

    if _crc_table is None:
        # then we do need to create it
        _crc_table = []
        i = 0
        while i < 256:
            data = i << 1
            crc = 0
            j = 8
            while j > 0:
                data >>= 1
                if (data ^ crc) & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
                j -= 1

            _crc_table.append(crc)
            # print("entry %d = %x" % ( i, table[i]))
            i += 1

    return


def _calc_byte(_ch, crc):
    """
    Give 1 byte and building CRC, calculate next single CRC

    :param _ch: the byte to add
    :type _ch: str or bytes
    :param int crc:
    :return:
    :rtype: int
    """
    assert _crc_table is not None

    if isinstance(_ch, str):
        # then assume is a single character
        by = ord(_ch)
    else:  # else assume is bytes
        by = _ch
    crc = (crc >> 8) ^ _crc_table[(crc ^ by) & 0xFF]
    return crc & 0xFFFF


def calc_checksum(packet, checksum=MODBUS_START_CRC):
    """
    given an ASCII packet like b'\x01\x03\x00\x00\x00\x0A', return the LRC

    note that we need the raw binary, not the ASCII form!

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :param int checksum: starting CRC, 0xFFFF for Modbus
    :return:
    """
    if not isinstance(packet, bytes):
        raise TypeError("MB/RTU packet must be bytes")

    if len(packet) < MBRTU_MINIMUM_LENGTH:
        raise ModbusBadForm("MB/RTU packet is too short")

    _init_table()
    for ch in packet:
        checksum = (checksum >> 8) ^ _crc_table[(checksum ^ ch) & 0xFF]
    return checksum


def encode_to_wire(packet):
    """
    Given a packet array like b'\x01\x03\x00\x00\x00\x0A', encode it for the
    wire as b':01030000000AF2\r\n' (plus force to upper case)

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :return bytes:
    """
    # will raise ModbusRtuBadForm() if too short, TypeError
    calc_crc = calc_checksum(packet)
    return packet + bytes([calc_crc & 0xFF, (calc_crc & 0xFF00) >> 8])


def decode_from_wire(packet):
    """
    given an ASCII packet like b':01030000000AF2\r\n', return the raw data
    as byte array, so would be b'\x01\x03\x00\x00\x00\x0A'

    If LRC is bad, throw exception ModbusAsciiBadForm
    If data is odd-count, or bad chars, throw exception ModbusAsciiBadForm

    :param bytes packet: the raw packet, assumed Modbus/RTU
    :return bytes:
    """
    if not isinstance(packet, bytes):
        raise TypeError("MB/RTU packet must be bytes")

    see_crc = (packet[-1] * 256) + packet[-2]
    packet = packet[:-2]
    calc_crc = calc_checksum(packet)

    if see_crc != calc_crc:
        raise ModbusBadChecksum(
            "bad CRC, see:{} calc:{}".format(see_crc, calc_crc))

    return packet


def test_end_of_message(data, is_request=True):
    """
    For use with the buffer object. A block of data is submitted, and this
    routine breaks it up to complete messages, or extra data not yet
    complete.

    :param bytes data:
    :param bool is_request: if T, is expecting request/indication, else is
                            expecting response/confirmation
    :return: list of complete packets, plus any extra
    """
    messages = []
    extra = data
    while len(data):
        if is_request:
            expected = modbus_adu_estimate_request_length(data)
        else:
            expected = modbus_adu_estimate_response_length(data)

        # print("exp:{}".format(expected))

        if expected == MODBUS_ADU_LENGTH_NOT_YET:
            # could not even estimate length yet, return as extra
            extra = data
            break

        elif expected == MODBUS_ADU_LENGTH_UNKNOWABLE:
            messages.append(data)
            extra = None
            break

        # add in the 2 CRC bytes
        expected += 2

        if expected > len(data):
            # have an estimate, but need more data
            extra = data
            break

        messages.append(data[:expected])
        data = data[expected:]
        extra = None

    return messages, extra

MODBUS_ADU_LENGTH_NOT_YET = 0
MODBUS_ADU_LENGTH_UNKNOWABLE = -1


def modbus_adu_estimate_request_length(data):
    """
    given a building Modbus/RTU buffer, estimate byte count. The CRC-16 is
    not included, which allows this to be used on MB/ASCII and other forms

    :param bytes data:
    :return int:
    """

    # to have even a chance, we need to see at least the function byte
    if len(data) < 2:
        return MODBUS_ADU_LENGTH_NOT_YET

    command = int(data[1])
    if command in (1, 2, 3, 4, 5, 6):
        # then is {id}{fnc}{off 2}{cnt 2}
        return 6

    elif command in (7, 11, 12, 17):
        # then is {id}{fnc}
        return 2

    elif command in (15, 16):
        # then is {id}{fnc}{off 2}{cnt 2}{bytes}...
        if len(data) < 7:
            return MODBUS_ADU_LENGTH_NOT_YET
        return 7 + data[6]

    return MODBUS_ADU_LENGTH_UNKNOWABLE


def modbus_adu_estimate_response_length(data):
    """
    given a building Modbus/RTU buffer, estimate byte count. The CRC-16 is
    not included, which allows this to be used on MB/ASCII and other forms

    :param bytes data:
    :return int:
    """

    # to have even a chance, we need to see at least the function byte
    if len(data) < 2:
        return MODBUS_ADU_LENGTH_NOT_YET

    command = int(data[1])
    if command & 0x80:
        # error code / exception
        return 3

    elif command in (1, 2, 3, 4, 11):
        # then is {id}{fnc}{bytes}...
        if len(data) < 3:
            return MODBUS_ADU_LENGTH_NOT_YET
        return 3 + data[2]

    elif command in (5, 6, 15, 16):
        # then is {id}{fnc}{off 2}{val 2}
        return 6

    return MODBUS_ADU_LENGTH_UNKNOWABLE
