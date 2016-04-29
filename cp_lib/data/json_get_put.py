"""
Simple JSON GET and PUT. Geared towards JSON-RPC, but assumes nitty-gritty
details of the protocol were handled externally.
"""
import json

from cp_lib.data.data_tree import get_item_value, put_item, \
    DataTreeItemNotFound

JSON_VERSION = "2.0"


def jsonrpc_check_request(source, test_params=True):
    """
    Given a JSONRPC request, confirm looks valid

    :param source: the JSON RPC request
    :type source: str or bytes or dict
    :param boot test_params: if True, confirm [params] exists
    :return:
    :rtype dict:
    """
    if isinstance(source, bytes):
        source = source.decode('utf-8')

    if isinstance(source, str):
        source = json.loads(source)

    assert isinstance(source, dict)

    if "jsonrpc" not in source:
        source["error"] = {
            "code": -32600,
            "message": "Invalid request - [jsonrpc] key missing"}

    elif source["jsonrpc"] != JSON_VERSION:
        source["error"] = {
            "code": -32600,
            "message": "Invalid request - [jsonrpc] != {}".format(
                JSON_VERSION)}

    elif "method" not in source:
        source["error"] = {
            "code": -32600,
            "message": "Invalid request - [method] key missing"}

    elif not isinstance(source["method"], str):
        source["error"] = {
            "code": -32600,
            "message": "Invalid request - [method] is not str"}

    else:
        if test_params and "params" not in source:
            source["error"] = {
                "code": -32600,
                "message": "Invalid request - [params] key missing"}

    return source


def jsonrpc_prep_response(source, encode=True):
    """
    Given a JSONRPC response, pop out unwanted keyes, plus confirm
    one and only one of the [error] or [result] keys

    :param dict source: the JSON RPC request
    :param bool encode: if T, then convert to str()
    :return:
    :rtype dict:
    """
    assert isinstance(source, dict)

    pop_list = []
    for key, value in source.items():
        # remove any unknown keys
        if key not in ("jsonrpc", "id", "result", "error"):
            pop_list.append(key)

    for key in pop_list:
        # expect to pop out [method] and [params]
        # print("Pop unwanted key:{}".format(key))
        source.pop(key)

    if "jsonrpc" not in source:
        # should be here, but add if missing
        source["jsonrpc"] = JSON_VERSION

    if "error" in source:
        # we only want error or result, not both
        if "result" in source:
            raise KeyError("Cannot have both [error] and [result]")

    elif "result" not in source:
        raise KeyError("Must have either [error] or [result]")

    if encode:
        source = json.dumps(source)

    return source


def jsonrpc_get(base, source):
    """
    Given a dict acting as data tree, fetch the item in
    JSON RPC ["params"]["path"]

    :param dict base: the data tree to search
    :param dict source: the parses json rpc request
    :return:
    """

    # we ignore keys "jsonrpc", "method", and "id"

    if not isinstance(source, dict):
        raise TypeError("jsonrpc source must be dict()")

    if "params" not in source:
        raise ValueError('jsonrpc["params"] key missing')

    if "path" not in source["params"]:
        raise ValueError('jsonrpc["params"]["path"] key missing')

    try:
        result = get_item_value(
            base, source["params"]["path"], throw_exception=True)
        source["result"] = result

    except DataTreeItemNotFound:
        source["error"] = {"code": -32602, "message": "path is not found"}

    # we 'key' into the messages, but we do NOT clean up the 'call' keys
    return source


def jsonrpc_put(base, source):
    """
    Given a dict acting as data tree, fetch the item in
    JSON RPC ["params"]["path"]

    :param dict base: the data tree to search
    :param dict source: the parses json rpc request
    :return:
    """

    # we ignore keys "jsonrpc", "method", and "id"

    if not isinstance(source, dict):
        raise TypeError("jsonrpc source must be dict()")

    if "params" not in source:
        raise ValueError('jsonrpc["params"] key missing')

    if "path" not in source["params"]:
        raise ValueError('jsonrpc["params"]["path"] key missing')

    try:
        result = put_item(
            base, path=source["params"]["path"],
            value=source["params"]["value"], throw_exception=True)
        source["result"] = result

    except DataTreeItemNotFound:
        source["error"] = {"code": -32602, "message": "path is not found"}

    # we 'key' into the messages, but we do NOT clean up the 'call' keys
    return source
