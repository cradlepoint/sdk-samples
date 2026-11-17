# tornado_sample
A minimal web server example using the Tornado framework. Serves a simple "Hello Cradlepoint!" page on the app's web port (usually 9001). Use as a starting point for building web applications with Tornado on Cradlepoint routers.

## How It Works

The app creates a Tornado web application with a single GET route at `/` that returns "Hello Cradlepoint!" as plain text. The server listens on the port described in [Port](#port) and runs the Tornado IOLoop.

```python
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Cradlepoint!")

application = tornado.web.Application([(r"/", MainHandler)])
sock = cp.bind_web_port(start_port=9001)
server = tornado.httpserver.HTTPServer(application)
server.add_sockets([sock])
tornado.ioloop.IOLoop.current().start()
```

## Accessing the Web UI

1. Forward the Primary LAN Zone to the Router Zone in the firewall settings (Default Allow All)
2. Browse to `http://<router_ip>:<port>`, using the port shown in the app log
3. You should see: `Hello Cradlepoint!`

If you cannot connect, ensure a zone forwarding rule exists from the LAN zone to the Router zone so LAN clients can reach the app's web port.

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

The port is shown in the app log and saved in the `tornado_sample_web_port` SDK Data field (usually 9001, or the next free port if 9001 is taken). The startup log shows it, for example `Bound port 9001 (discovered, saved to tornado_sample_web_port)` then `Web server started on port 9001`.

To change the port for one router or a group, set `tornado_sample_web_port` in NCM SDK Data (device or group) and restart the app. Delete the field and restart to go back to automatic selection. A configured port that is busy is retried for about 10 seconds. If the port is not a number from 1 to 65535, or stays busy, the app stops itself and logs why. Fix or delete the field, then start the app.

## Appdata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `tornado_sample_web_port` | No | Web UI port (1-65535). If set, the app uses exactly this port. If not set, it uses the first free port from 9001 and saves it here. Delete it to pick a port automatically again. |

## Requirements

- Router firmware 7.26 or later
- `tornado` library (included in app directory)
- Firewall zone forwarding from LAN to Router zone for LAN client access

## Notes

- The Tornado IOLoop blocks the main thread — the server runs until the app is stopped
- For production web apps, consider using the built-in `http.server` module instead (no dependencies needed)
- If you set `tornado_sample_web_port`, use a port above 1024 (SDK apps cannot bind to privileged ports)
