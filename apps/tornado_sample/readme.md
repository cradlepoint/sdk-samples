# tornado_sample
A minimal web server example using the Tornado framework. Serves a simple "Hello Cradlepoint!" page on port 9001. Use as a starting point for building web applications with Tornado on Cradlepoint routers.

## How It Works

The app creates a Tornado web application with a single GET route at `/` that returns "Hello Cradlepoint!" as plain text. The server listens on port 9001 and runs the Tornado IOLoop.

```python
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Cradlepoint!")

application = tornado.web.Application([(r"/", MainHandler)])
application.listen(9001)
tornado.ioloop.IOLoop.current().start()
```

## Accessing the Web UI

1. Forward the Primary LAN Zone to the Router Zone in the firewall settings (Default Allow All)
2. Browse to `http://<router_ip>:9001`
3. You should see: `Hello Cradlepoint!`

If you cannot connect, ensure a zone forwarding rule exists from the LAN zone to the Router zone.

## Customization

Add more routes by extending the URL patterns:
```python
application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/api/data", DataHandler),
    (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static/"}),
])
```

## Port

The server runs on port 9001. Change it by modifying `application.listen(9001)`.

## Requirements

- Router firmware 7.26 or later
- `tornado` library (included in app directory)
- Firewall zone forwarding from LAN to Router zone for LAN client access

## Notes

- The Tornado IOLoop blocks the main thread — the server runs until the app is stopped
- For production web apps, consider using the built-in `http.server` module instead (no dependencies needed)
- Port must be above 1024 (SDK apps cannot bind to privileged ports)
