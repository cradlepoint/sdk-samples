# Web Development Standards

- **ALWAYS use Python's built-in `http.server` module** - never use third-party web frameworks (Flask, Bottle, CherryPy, etc.). The native `http.server.HTTPServer` is available on cppython and has zero dependencies
- **ALWAYS start the web server with `cp.start_web_server(Handler)` - NEVER hardcode a port** - it picks the port, serves in a daemon thread, and returns the server (`server.server_port` is the port). See `main()` in `apps/templates/web_app_template/web_app_template.py`. How the port is chosen:
  - Appdata `<app_name>_web_port` set (NCM group/device SDK Data): that exact port, retried ~10 s if busy. It never moves to another port, so pinned LAN Manager connections and firewall rules stay valid
  - Not set: first free port from 8000, saved to `<app_name>_web_port` so it stays the same across reboots. This records a real assignment; it is not writing a default to appdata
  - On failure (invalid value, port busy) on the router it stops the app via the SDK and never returns - do not `sys.exit()` around it, that causes a `restart = true` loop. Off-router it returns `None`. Pass `required=False` when the app's main job does not need the UI (NTP server, data recorder): it then returns `None` and the app keeps running
  - The main thread must stay alive after it returns (`while True: time.sleep(60)` or the app's work loop) - code that used to block in `serve_forever()` would otherwise fall off the end of `main()`
  - Renaming an existing app's port field: pass `legacy_field='old_field_name'` so the old NCM setting is still honoured when `<app_name>_web_port` is unset, and list the old field as deprecated in the readme
  - Apps with their own server class or tornado: `sock = cp.bind_web_port()` returns the bound socket (same rules, returns `None` on failure). For `http.server`: build with `bind_and_activate=False`, close its placeholder `server.socket`, then assign `server.socket = sock`. For tornado: `sock.setblocking(False)`, then `tornado.httpserver.HTTPServer(app).add_sockets([sock])` (see `apps/tornado_sample`). On `None`, call `cp.stop_app()` and idle - never exit. A second listener in one app uses `cp.bind_web_port(name='api')` → `<app_name>_api_port`
  - Document `<app_name>_web_port` in the readme's Appdata Fields table (optional; set it to pin the port, delete it to rediscover). Readme URLs say `http://router_ip:<port>`, not `:8000`
- **Custom server classes must skip the FQDN lookup** (not needed with `cp.start_web_server`, which never binds through `server_bind`) - `http.server.HTTPServer.server_bind()` calls `socket.getfqdn()`, which runs the router's hostname through the `idna` codec. On routers whose hostname does not conform to IDNA (common), this raises `UnicodeError: encoding with 'idna' codec failed (UnicodeError: label too long)` and the server never starts. No SDK web app needs the FQDN (clients connect by IP), so bypass it. Subclass the server and override `server_bind` to call `socketserver.TCPServer.server_bind(self)` then set `server_name`/`server_port` from the bound socket:
  ```python
  class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
      daemon_threads = True
      allow_reuse_address = True

      def server_bind(self):
          socketserver.TCPServer.server_bind(self)  # skips socket.getfqdn()
          host, port = self.socket.getsockname()[:2]
          self.server_name = host
          self.server_port = port
  ```
- **LAN client access to router ports requires firewall zone forwarding** - For a client device on the LAN to reach a port on the router (SDK app web UI, SNMP agent, container-published port, etc.), the firewall must have a forwarding rule from the Primary LAN Zone to the Router Zone. If an app is running but LAN clients get connection timeouts, the zone forwarding is the first thing to check. This is configured at `config/firewall/zone_fwd` or via the NCOS UI under Security > Zone Firewall.
- **NCM API does NOT support CORS** - the NetCloud Manager API at `us0.cradlepointecm.com` blocks cross-origin browser requests (no `Access-Control-Allow-Origin` header). Browser JS from third-party origins (e.g., GitHub Pages) cannot call NCM APIs directly. Use server-side calls (curl, Python requests) or the NCM web UI for uploads
- **Background web server pattern** - the server runs in a daemon thread (`cp.start_web_server` does this); the main thread runs the app's primary loop and must not fall off the end of `main()`
- **Dashboard auto-refresh with server-side timestamps** - compute `_ago` values (seconds since event) on the server, not the client. Client clocks may differ from router. Return `connected_ago`, `last_rx_ago` etc. as integers
- **Dynamic download filenames** - use router hostname and timestamp: `cp.get('config/system/system_id')` + `datetime.now().strftime('%Y%m%d_%H%M%S')`
- **Light/dark mode** - use `data-theme` attribute on `<html>` element, persist with `localStorage.setItem('theme', 'light'|'dark')`, load on page init
- **ES6+ JavaScript is fine** - arrow functions, template literals, const/let, async/await, destructuring all work in modern browsers that access the router UI
- **NEVER pass raw parameters in onclick attributes** - quote escaping is error-prone. Prefer data attributes plus `this`. If you must inline arguments, use `&quot;` HTML entities (`onclick="func(&quot;a&quot;,&quot;b&quot;)"`), never backslash-escaped quotes
- **Auto-refresh dashboards must preserve user input** - Save `document.activeElement.id` and `.value`, restore after innerHTML update
- **A config field rebuilt from form inputs is silently blanked when those inputs are not rendered** - the usual pattern for "clearing a field should remove it" is to reset the collection to `{}`/`[]` and refill it from the DOM. The moment any part of that form is conditionally rendered (a column hidden by a mode toggle, a section only drawn for certain states, a second page not built yet), a save wipes stored values the user never saw. Two fixes, both worth having: reset only the fields that actually have inputs on the page, and prefer `display:none` over not rendering, so the inputs stay in the DOM and keep their values. The template's `.element-section` hides inactive sections rather than removing them, so a multi-page form can collect every page in one pass

- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- CSS variables for theming, mobile-first responsive
- **ALWAYS copy `static/` folder from `apps/templates/web_app_template` into new web apps** - this includes `css/style.css`, `js/script.js`, `libs/font-awesome.min.css`, `libs/jquery-3.5.1.min.js`, and `libs/webfonts/`. These are required for the design system to work
- **The template's `script.js` calls `showElement('homepage')` on init, which strips `active` from EVERY `.element-section`** - if your page has no section with `id="homepage"`, all sections end up `display: none` and the content area renders completely blank while the header and sidebar look fine. Name your landing section `id="homepage"` (with `data-element="homepage"` on its nav item) rather than fighting the framework; the sidebar Homepage link targets the same id, so it then works too
- **The template's `initTabs()` binds `.tab-btn` clicks once at page load, so dynamically generated tabs are dead** - if you build tabs after the initial render, add your own delegated click handler scoped to your container. Reuse the template's class names (`tab-navigation`, `tab-btn`, `tab-content`, `data-tab`) so the styling still comes from the design system
- **`window.webAppTemplate.showToast(message, type, duration)` is available from the template**, but it needs a `<div class="toast-container" id="toast-container"></div>` in your HTML or it silently does nothing
- **ALWAYS use `your_web_app.html` from `apps/templates/web_app_template` as the starting HTML** - copy it as `index.html` into your app, then modify the title, sidebar nav, and content sections. NEVER write HTML from scratch
- **NEVER write custom CSS or include external stylesheets** - the template's `style.css` provides the complete design system (layout, colors, dark mode, components). Add app-specific styles in a `<style>` block or a separate file that supplements (not replaces) the template CSS
- Proper error handling with try/catch
- Serve assets locally (no external dependencies)
- Implement signal handlers for graceful shutdown
