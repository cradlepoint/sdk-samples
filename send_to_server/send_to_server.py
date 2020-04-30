'''
Gets the '/status' from the router config store and send it
to a test server.
'''

import datetime
import urllib.request
import urllib.parse
from csclient import EventingCSClient

cp = EventingCSClient('send_to_server')


def post_to_server():
    try:
        # The tree item to get from the router config store
        tree_item = '/status/system/sdk'
        start_time = datetime.datetime.now()

        # Get the item from the router config store
        tree_data = cp.get(tree_item)
        cp.log("{}: {}".format(tree_item, tree_data))

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
        cp.log("data sent, http response code: {}".format(response.code))
        cp.log('Time to get data from router config store: {}'.format(time_to_get))
        cp.log('Time to urlencode data: {}'.format(time_to_encode))
        cp.log('Time to get reply from server: {}'.format(end_time - send_to_server_start_time))
        cp.log('Time to get and send data in post request: {}'.format(end_time - start_time))

    except Exception as ex:
        cp.log('Something went wrong! ex: {}'.format(ex))


if __name__ == "__main__":
    post_to_server()
