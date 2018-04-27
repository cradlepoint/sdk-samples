'''
Gets the '/status' from the router config store and send it
to a test server.
'''


import cs
import datetime
import urllib.request
import urllib.parse


APP_NAME = 'send_to_server'


def post_to_server():
    try:
        # The tree item to get from the router config store
        tree_item = '/status/system/sdk'
        start_time = datetime.datetime.now()

        # Get the item from the router config store
        tree_data = cs.CSClient().get(tree_item)
        cs.CSClient().log(APP_NAME, "{}: {}".format(tree_item, tree_data))

        time_to_get = datetime.datetime.now() - start_time
        encode_start_time = datetime.datetime.now()

        # URL encode the tree_data
        params = urllib.parse.urlencode(tree_data)

        # UTF-8 encode the URL encoded data
        params = params.encode('utf-8')

        time_to_encode = datetime.datetime.now() - encode_start_time
        send_to_server_start_time = datetime.datetime.now()

        # Send a post request to a test server. It will respond with the data sent
        # in the request
        response = urllib.request.urlopen("http://httpbin.org/post", params)
        end_time = datetime.datetime.now()

        # Log the response code and the processing timing information.
        cs.CSClient().log(APP_NAME, "data sent, http response code: {}".format(response.code))
        cs.CSClient().log(APP_NAME, 'Time to get data from router config store: {}'.format(time_to_get))
        cs.CSClient().log(APP_NAME, 'Time to urlencode data: {}'.format(time_to_encode))
        cs.CSClient().log(APP_NAME, 'Time to get reply from server: {}'.format(end_time - send_to_server_start_time))
        cs.CSClient().log(APP_NAME, 'Time to get and send data in post request: {}'.format(end_time - start_time))

    except Exception as ex:
        cs.CSClient().log(APP_NAME, 'Something went wrong! ex: {}'.format(ex))


if __name__ == "__main__":
    post_to_server()