#
#        File: CRC16.PY
#              CRC-16 (reverse) table lookup for Modbus or DF1
#
#     Project: Modbus
#      Author: Lynn August Linse, based on method used by XMODEM
#    Language: Python 3.3
#
#     History:
#       2003Jun17 - Port from VB version
#       2016May09 - Port to Python v3
#

table = tuple()

MODBUS_START_CRC = 0xFFFF
DF1_START_CRC = 0


# crc16_Init() - Initialize the CRC-16 table (crc16_Table[])
def init_table():
    """
    Pre-seed our XMODEM look up table
    :return:
    """
    global table

    if (len(table) == 256) and (table[1] == 49345):
        # print("Table already init!")
        return

    lst = []
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

        lst.append(crc)
        # print("entry %d = %x" % ( i, table[i]))
        i += 1

    table = tuple(lst)
    return


# given a Byte, Calc a modbus style CRC-16 by look-up table
def calc_byte(ch, crc):
    """
    Give 1 byte and building CRC, cacl next single CRC

    :param ch: the byte to add
    :type ch: str or bytes
    :param int crc:
    :return:
    :rtype: int
    """
    init_table()
    if isinstance(ch, str):
        # then assume is a single character
        by = ord(ch)
    else:  # else assume is bytes
        by = _ch
    crc = (crc >> 8) ^ table[(crc ^ by) & 0xFF]
    return crc & 0xFFFF


def calc_string(st, crc=MODBUS_START_CRC):
    """
    Give a string (or bytes), plus an initial seed CRC, calc the final CRC

    Note: it doesn't try to ignore existing appended CRC, so if as example
    this is a Modbus/RTU string, you'll need to decide to manually exclude
    any existing CRC

    :param st: the message to calc over
    :type st: str or bytes
    :param int crc:
    :return:
    :rtype: int
    """
    init_table()
    # print("st = ", list(st))
    if isinstance(st, str):
        # then assume is a single character
        for ch in st:
            crc = (crc >> 8) ^ table[(crc ^ ord(ch)) & 0xFF]
            # print("crc=%x" % crc)
    else:  # else assume is bytes
        for ch in st:
            crc = (crc >> 8) ^ table[(crc ^ ch) & 0xFF]
    return crc

if __name__ == '__main__':

    init_table()

    # test Modbus
    print("testing Modbus messages with crc16.py")
    print("test case #1:", end=" ")
    _crc = MODBUS_START_CRC
    _st = "\xEA\x03\x00\x00\x00\x64"
    for _ch in _st:
        _crc = calc_byte(_ch, _crc)
    if _crc != 0x3A53:
        print("\n BAD - ERROR - FAILED! expect:0x3A53 but saw 0x%x" % _crc)
    else:
        print("Ok")

    print("test case #2:", end=" ")
    _st = "\x4b\x03\x00\x2c\x00\x37"
    _crc = calc_string(_st)
    if _crc != 0xbfcb:
        print("\n BAD - ERROR - FAILED! expect:0xBFCB but saw 0x%x" % _crc)
    else:
        print("Ok")

    print("test case #3:", end=" ")
    _st = "\x0d\x01\x00\x62\x00\x33"
    _crc = calc_string(_st, MODBUS_START_CRC)
    if _crc != 0x0ddd:
        print("\n BAD - ERROR - FAILED! expect:0x0DDD but saw 0x%x" % _crc)
    else:
        print("Ok")

    print("\ntesting DF1 messages with crc16.py")

    print("test case #1:", end=" ")
    _st = "\x07\x11\x41\x00\x53\xB9\x00\x00\x00\x00\x00\x00\x00" +\
          "\x00\x00\x00\x00\x00"
    # DF1 uses same algorithm - just starts with CRC=0x0000 instead of 0xFFFF
    _crc = calc_string(_st, DF1_START_CRC)
    _crc = calc_byte("\x03", _crc)
    if _crc != 0x4C6B:
        print("\n BAD - ERROR - FAILED! expect:0x4C6B but saw 0x%x" % _crc)
    else:
        print("Ok")
