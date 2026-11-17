# tornado_sample - simple web server using tornado

import time

import cp
import tornado.httpserver
import tornado.ioloop
import tornado.web


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Cradlepoint!")


if __name__ == "__main__":
    cp.log('Starting...')
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    # Port: appdata tornado_sample_web_port, else the first free port from
    # 9001 (saved there). Tornado takes the pre-bound socket directly.
    sock = cp.bind_web_port(start_port=9001)
    if sock is None:
        # Never exit: restart = true would relaunch the app in a loop.
        if cp.stop_app():
            time.sleep(30)
        while True:
            time.sleep(3600)
    sock.setblocking(False)
    server = tornado.httpserver.HTTPServer(application)
    server.add_sockets([sock])
    cp.log('Web server started on port %d' % sock.getsockname()[1])
    tornado.ioloop.IOLoop.current().start()
