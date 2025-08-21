"""cp_shell is a web interface on port 8022.
It allows you to interact with the Cradlepoint router linux shell."""

import os
import subprocess
import time
from select import select
import tornado.web
from functools import partial
import cp

server_port = 8022

static_path = os.path.dirname(__file__)


def shell(cmd):
    """
    execute a linux shell command and returns the output.

    :param path: string
        API path triggering callback
    :param cmd: string
        command to be executed. e.g. "ls -al"
    :arg *args
    """
    from subprocess import Popen, PIPE
    output = ''
    cmd = cmd.split(' ')
    tail = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    for line in iter(tail.stdout.readline, ''):
        if tail.returncode:
            break
        if line:
            output += line + '<br>'
    return output


class ShellHandler(tornado.web.RequestHandler):
    """handle requests for the /shell endpoint."""

    def get(self):
        """return command response."""
        response = ''
        try:
            cmd = self.get_argument('cmd')
            response = shell(cmd) or 'No Response'
        except Exception as e:
            cp.log(e)
        self.write(response)


if __name__ == "__main__":
    cp.log(f'Starting webserver on port {server_port}...')
    application = tornado.web.Application([
        (r"/shell", ShellHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
         {"path": static_path, "default_filename": "index.html"}),
    ])
    application.listen(server_port)
    tornado.ioloop.IOLoop.current().start()
