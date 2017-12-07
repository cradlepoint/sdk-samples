# Input filters for smart import of data from unknown source
#

import struct
import unquote_string


def isolate_numeric_from_string(data):
    """
    Given a string, discard leading (and trailing) non numeric data. So
    convert "rate = 900 sec" or "900sec" to "900". Only the first numeric
    sequence is handled, so "1, 2, 3" returns "1"

    Passing in int or float causes TypeError, and ValueError occurs
    if NO number symbols are located such as in "Hello" or "\n".

    :param data:
    :type data: str or bytes
    :return: first numeric sequence is returned, or exception if none found
    :rtype: str
    """
    if isinstance(data, bytes):
        # make bytes into string
        data = data.decode()

    if not isinstance(data, str):
        raise TypeError(
            "isolate_numeric_from_string() requires string input, not %s",
            type(data))

    # strip off any leading whitespace
    data = data.strip()

    if not len(data):
        # we never found any numeric symbols!
        raise ValueError(
            "isolate_numeric_from_string(%s) found no numeric symbols",
            str(data))

    # now find the first numeric symbol, example start with "rate = 900 sec"
    # print "beg[%s]" % data
    index = 0
    while not (data[index].isdigit() or data[index] in ('.', '-')):
        index += 1
        if index >= len(data):
            # we never found any numeric symbols!
            raise ValueError(
                "isolate_numeric_from_string(%s) found no numeric symbols",
                str(data))

    if index:
        # data[index] is desired, and the start of the numeric
        data = data[index:]
    # print "1st[%s]" % data

    # now we are down to "900 sec"
    index = 0
    while data[index].isdigit() or data[index] in ('.', '-'):
        index += 1
        if index >= len(data):
            # then we hit the end-of-string as numeric
            return data

    # data[index] is first UNDESIRED symbol, the end of the numeric
    data = data[:index]
    # print "2nd[%s]" % data
    return data


def parse_integer_or_float_string(data):
    """
    Given string with mixed symbols, isolate the first INT or FLOAT from
    the string. See isolate_numeric_from_string() for a richer explanation
    of how complex strings are handled.

    TypeError or ValueError thrown if isolation fails

    :param data: a string with mixed symbols, such as "rate = 900 sec"
    :type data: str
    :return: the first isolated INT as int, or FLOAT as float
    :rtype: int or float
    """
    data = isolate_numeric_from_string(data)

    if data.find('.') >= 0:
        # then handle as float
        return parse_float(data)

    # else leave as int so that both "123" and "0x0123" handled correctly
    return parse_integer(data)


def parse_integer_or_float(data):
    """
    Take data of unknown type (but assume in int, bool, long, float, or str)

    :param data: a string with int or float
    :type data: str
    :return: the first isolated INT as int, or FLOAT as float
    :rtype: int or float
    """
    if type(data) in (int, float):
        return data

    if isinstance(data, bytes):
        # make bytes into string
        data = data.decode()

    if not isinstance(data, str):
        raise TypeError("parse_integer_or_float(%s) is unsupported type:%s",
                        str(data), type(data))

    # this handles things like " '125' " with embedded quotes
    data = clean_string(data)

    if data.find('.') >= 0:
        # then handle as float
        return parse_float(data)

    # else leave as int so that both "123" and "0x0123" handled correctly
    return parse_integer(data)


def parse_integer_string(data):
    """
    Given a string with mixed symbols, isolate the first INT from the string.
    See isolate_numeric_from_string() for a richer explanation of how
    complex strings are handled.

    If you know your data is string, use this for slightly faster processing.

    If you do not know type, use parse_integer(), which handles more types

    TypeError or ValueError thrown if isolation fails

    :param data: a string with mixed symbols, such as "rate = 900 sec"
    :type data: str
    :return: the first isolated INT as type int
    :rtype: int
    """
    data = isolate_numeric_from_string(data)

    if data.find('.') >= 0:
        # making a float will cause parse_integer() to round
        data = float(data)

    # leave as string for int so that "123" and "0x0123" handled correctly
    return parse_integer(data)


def parse_integer(data, none_is_zero=False):
    """
    Take data of unknown type (but assume in int, bool, long, float, or str)

    Floats are rounded. Strings need to be like "99" or " 99 ". For
    complex things like " = 99 seconds", use the parse_integer_string() call

    :param data: the source, which may be almost anything
    :type data: int, str
    :param bool none_is_zero: if T, None returns False, else it returns None
    :return:
    """
    if isinstance(data, int):
        # this also gets BooleanType, and in Python3, all ints are 'long'
        return int(data)

    if isinstance(data, float):
        # just round
        return int(round(data))

    if data is None:
        if none_is_zero:
            return 0
        else:
            return None

    try:
        # this works if data is types.IntType, or strings for base 10,
        # so like 10, or '10'
        return int(data, 10)

    except ValueError:
        # then might have been '0x10' (or 0X10 ...)
        if isinstance(data, str):
            if len(data) > 2:
                if data[:2] in ('0x', '0X'):
                    # pity python doesn't just handle this already
                    return int(data[2:], 16)

    except TypeError:
        # might be None, or other complex type
        pass

    # if still here, we can't make into integer
    raise ValueError("parse_integer(%s) is not a valid integer", data)


def parse_boolean(data, none_is_false=False):
    """
    # parse in T/F, true/False, 0/1, on/off (case ignored)

    :param data: the source, which may be almost anything
    :type data: int, str, bool
    :param bool none_is_false: if T, None returns False, else it returns None
    :return:
    """
    if isinstance(data, int):
        # then is already Boolean, which is type Int really
        #     (BooleanType is subset of IntType!)
        return bool(data)

    if data is None and none_is_false:
        return False
    # else let the ValueError hit below

    if isinstance(data, bytes):
        # make bytes into string
        data = data.decode()

    if isinstance(data, str):
        # this handles things like " '125' " with embedded quotes
        work = clean_string(data).lower()
        if work in ('0', 'f', 'false', 'off', 'disable', 'disabled'):
            return False
        if work in ('1', 't', 'true', 'on', 'enable', 'enabled'):
            return True

    # if still here, we can't make into integer
    raise ValueError("parse_boolean(%s) is not a valid boolean", data)


def parse_none(data):
    """
    # parse in None or null (JSON)

    :param data: the source, which may be almost anything
    :type data: int, str, bool, bytes
    :return:
    """
    if data is None:
        return None

    if isinstance(data, bytes):
        # make bytes into string
        data = data.decode()

    if isinstance(data, str):
        work = clean_string(data).lower()
        if work in ('', 'none', 'null'):
            # we allow empty string, Python None, or JSON null
            return None

    # if still here, we can't make into None
    raise ValueError("parse_none(%s) is not a valid None/Null value", data)


def parse_float_string(data):
    """
    Given string with mixed symbols, isolate the first numeric from the
    string. See isolate_numeric_from_string() for a richer explanation
    of how complex strings are handled.

    TypeError or ValueError thrown if isolation fails

    :param data: a string with mixed symbols, such as "rate = 900.23 sec"
    :type data: str
    :return: the first isolated FLOAT as type float
    :rtype: float
    """
    return parse_float(isolate_numeric_from_string(data))


def parse_float(data, none_is_zero=False):
    """
    Given data, map to floating point. String is simple, like "9.34" only

    For complex things like "rate = 9.34 seconds",
    use the parse_float_string() call

    :param data:
    :type data: str or int or float
    :param none_is_zero:
    :type none_is_zero: bool
    :return:
    :rtype: float
    """
    if isinstance(data, float):
        return data

    if data is None:
        if none_is_zero:
            return 0.0
        else:
            return None

    try:
        return float(str(data))

    # except ValueError: - leave this one as is

    except TypeError:
        # might be None, or other complex type
        pass

    # if still here, we can't make into integer
    raise ValueError("parse_float(%s) is not a valid float", data)


def parse_binst_to_int(binary_string):
    """
    Convert the binary string as returned by serial protocol into integer

    :param binary_string:
    :type binary_string: bytes
    :return:
    """
    # a bit convoluted; data looks like BE
    if isinstance(binary_string, bool):
        binary_string = int(binary_string)

    elif binary_string is None or len(binary_string) == 0:
        binary_string = 0

    elif len(binary_string) == 1:
        binary_string = struct.unpack('>B', binary_string)[0]
    elif len(binary_string) == 2:
        binary_string = struct.unpack('>H', binary_string)[0]
    elif len(binary_string) == 4:
        binary_string = struct.unpack('>I', binary_string)[0]
    else:
        raise ValueError("binary_string is not as expected")

    return binary_string


def clean_string(value: str):
    """
    trim a string, and remove any leading/trailing quotes. String is
    stripped of white space again, after removing quotes.

    If we passed in bytes, convert to str with UTF-8, for other unexpected
    types, force TypeError, else it might be AttributeError
    """
    if isinstance(value, bytes):
        # convert bytes to UTF-8
        value = value.decode()

    elif not isinstance(value, str):
        raise TypeError(
            "clean_string() requires str type, not {}".format(type(value)))

    value = unquote_string(value)
    value = value.strip()
    return value
