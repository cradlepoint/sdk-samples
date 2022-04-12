# tornado_sample - simple web server using tornado

from csclient import EventingCSClient
import tornado.web


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Cradlepoint!")


if __name__ == "__main__":
    cp = EventingCSClient("tornado_sample")
    cp.log("Starting...")
    application = tornado.web.Application(
        [
            (r"/", MainHandler),
        ]
    )
    application.listen(9001)
    tornado.ioloop.IOLoop.current().start()
