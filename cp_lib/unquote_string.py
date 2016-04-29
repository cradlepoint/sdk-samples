def unquote_string(value):
    """
    If a string value is "\"value\"" or "\'value\'", remove unexpected quotes.

    Note that quote must be on EACH end. If only 1 quote, nothing changes.

    This happens when - for example - a JSON literal is treated as a binary
    string. So the value "hello" doesn't become the 5-byte string 'hello',
    but the 7-byte string '"hello"'

    :param str value:
    :return str:
    """
    if isinstance(value, str):
        x = value.strip()
        if len(x) >= 2:
            if x[0] in ('\"', "\'") and x[-1] in ('\"', "\'"):
                # remove leading & trailing quote
                return x[1:-1]

    # else is not string or too short
    return value
