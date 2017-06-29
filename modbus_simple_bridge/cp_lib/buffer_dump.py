"""
A custom pretty-print to dump protocol buffers for use with Syslog.

The form will be like, where ofs = the offset in the total buffer:
[ofs] 00 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF [0123456789ABCDEF]
00000000000000001111111111111111222222222222222233333333333333334444444444444
0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABC

[ofs] 00 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF 00 11 22 33 [0123456789
00000000000000001111111111111111222222222222222233333333333333334444444444444
0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABC

As shown above, chunks with a width of 16 are 48 bytes wide, and 20 is 58
"""
import logging

# how wide should the dumped lines be?
BUFFER_DUMP_WIDTH = 16


def buffer_dump(message, data, show_ascii=False, slash=False):
    """
    create a list of strings, dumping bytes in an insightful way

    :param str message: a display message
    :param data:
    :type data: str or bytes
    :param bool show_ascii: if True, append an ASCII approximation to line
    :param bool slash: if True, format as "\x00" instead of "00 "
    :return list:
    """
    if data is None:
        lines = ["dump:{0}, data=None".format(message)]
        return lines

    is_string = isinstance(data, str)

    if is_string:
        lines = ["dump:{0}, len={1}".format(message, len(data))]
    else:
        lines = ["dump:{0}, len={1} bytes()".format(message, len(data))]

    data_offset = 0
    while len(data) > 0:
        # loop until we've handled all of the data

        # handle data is chunks, sized to cleanly display by Syslog
        if len(data) > BUFFER_DUMP_WIDTH:
            chunk = data[:BUFFER_DUMP_WIDTH]
            data = data[BUFFER_DUMP_WIDTH:]
        else:
            chunk = data
            data = ""

        message = ["[%03d]" % data_offset]
        if is_string:
            # handle if string
            for x in chunk:
                if slash:
                    message.append("\\x%02X" % ord(x))
                else:
                    message.append(" %02X" % ord(x))

            if show_ascii:
                # only attach if we think is nearly ascii, else skip
                # (for example, binary Modbus will not show in a
                # meaningful way. string will show like \'Apple\n\'
                message.append("%s" % repr(chunk))

        else:
            # handle if bytes
            for x in chunk:
                if slash:
                    message.append("\\x%02X" % int(x))
                else:
                    message.append(" %02X" % int(x))

            if show_ascii:
                message.append("b%s" % repr(chunk.decode('utf8')))

        lines.append("".join(message))
        data_offset += BUFFER_DUMP_WIDTH

    return lines


def logger_buffer_dump(logger, message, data, show_ascii=False, slash=False):
    """
    carefully display a bytes string

    :param logging.Logger logger:
    :param str message: a display message
    :param data:
    :type data: str or bytes
    :param bool show_ascii:
    :param bool slash: if True, format as "\x00" instead of "00 "
    :return:
    """
    # import time

    results = buffer_dump(message, data, show_ascii, slash)
    for data in results:
        # the CP doesn't like no format?
        logger.debug("%s", data)
        # time.sleep(0.1)
    return
