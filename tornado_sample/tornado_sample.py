# tornado_sample - simple web server using tornado

import cp
import tornado.web

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Cradlepoint!")

if __name__ == "__main__":
    cp.log('Starting...')
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    application.listen(9001)
    tornado.ioloop.IOLoop.current().start()
