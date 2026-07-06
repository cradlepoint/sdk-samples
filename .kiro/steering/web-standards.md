---
inclusion: auto
description: "Web development standards for Cradlepoint SDK apps"
---
# Web Development Standards

- **ALWAYS use Python's built-in `http.server` module** - never use third-party web frameworks (Flask, Bottle, CherryPy, etc.). The native `http.server.HTTPServer` is available on cppython and has zero dependencies
- **LAN client access to router ports requires firewall zone forwarding** - For a client device on the LAN to reach a port on the router (SDK app web UI, SNMP agent, container-published port, etc.), the firewall must have a forwarding rule from the Primary LAN Zone to the Router Zone. If an app is running but LAN clients get connection timeouts, the zone forwarding is the first thing to check. This is configured at `config/firewall/zone_fwd` or via the NCOS UI under Security > Zone Firewall.
- **NCM API does NOT support CORS** - the NetCloud Manager API at `us0.cradlepointecm.com` blocks cross-origin browser requests (no `Access-Control-Allow-Origin` header). Browser JS from third-party origins (e.g., GitHub Pages) cannot call NCM APIs directly. Use server-side calls (curl, Python requests) or the NCM web UI for uploads
- **Default port: 8000** - use port 8000 for web applications unless there's a conflict
- **ALWAYS set SO_REUSEADDR** before binding: `server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)`
- **Port conflicts on redeployment** - SO_REUSEADDR doesn't prevent "Address in use" errors when redeploying without router reboot. If port 8000 is in use, either reboot router or use a different port (8001, 8002, etc.)
- **Background web server pattern** - run `http.server.HTTPServer` in a daemon thread: `Thread(target=server.serve_forever, daemon=True).start()`. Main thread runs the app's primary loop
- **Dashboard auto-refresh with server-side timestamps** - compute `_ago` values (seconds since event) on the server, not the client. Client clocks may differ from router. Return `connected_ago`, `last_rx_ago` etc. as integers
- **Dynamic download filenames** - use router hostname and timestamp: `cp.get('config/system/system_id')` + `datetime.now().strftime('%Y%m%d_%H%M%S')`
- **Light/dark mode** - use `data-theme` attribute on `<html>` element, persist with `localStorage.setItem('theme', 'light'|'dark')`, load on page init
- **ES6+ JavaScript is fine** - arrow functions, template literals, const/let, async/await, destructuring all work in modern browsers that access the router UI
- **NEVER pass parameters in onclick attributes** - Use HTML entities (&quot;) or data attributes instead
- **For onclick with params**: Use `onclick="func(&quot;param1&quot;,&quot;param2&quot;)"` with &quot; entities, NOT escaped quotes
- **Auto-refresh dashboards must preserve user input** - Save `document.activeElement.id` and `.value`, restore after innerHTML update
- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- CSS variables for theming, mobile-first responsive
- **ALWAYS copy `static/` folder from `apps/templates/web_app_template` into new web apps** - this includes `css/style.css`, `js/script.js`, `libs/font-awesome.min.css`, `libs/jquery-3.5.1.min.js`, and `libs/webfonts/`. These are required for the design system to work
- **ALWAYS use `your_web_app.html` from `apps/templates/web_app_template` as the starting HTML** - copy it as `index.html` into your app, then modify the title, sidebar nav, and content sections. NEVER write HTML from scratch
- **NEVER write custom CSS or include external stylesheets** - the template's `style.css` provides the complete design system (layout, colors, dark mode, components). Add app-specific styles in a `<style>` block or a separate file that supplements (not replaces) the template CSS
- Proper error handling with try/catch
- Serve assets locally (no external dependencies)
- Implement signal handlers for graceful shutdown
- Log which port server started on
