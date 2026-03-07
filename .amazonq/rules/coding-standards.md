# Cradlepoint SDK Coding Standards

Applications run on Cradlepoint routers using Python 3.8.

## Python 3.8 Constraints

- **NEVER use bitwise OR (|) for types** - Python 3.8 doesn't support `str | None` syntax
- **NEVER use arrow functions (=>) in JavaScript** - Python 3.8 environment doesn't support ES6, use ES5 `function(){}` syntax
- **NEVER use template literals in JavaScript** - use string concatenation instead: `'text' + var + 'more'`
- **NEVER pass parameters in onclick attributes** - quote escaping is error-prone, use data attributes and `this` instead
- **ALWAYS use try/except** - never raise exceptions, catch and log them
- **NEVER use random or generated data** - only use real data from router APIs, sensors, or external sources; if data is unavailable, use None or empty values
- Use 4 spaces, follow PEP 8, keep lines under 100 chars
- Never use bare `except:` clauses

## Router Environment

- **No screen** - use `cp.log()` for all output (never print())
- **No keyboard** - never use `input()` or `KeyboardInterrupt`
- **Relative paths only** - use `tmp/`, never absolute like `/tmp`
- **Python is "cppython"** - start.sh must use `cppython`
- **Static apps** - no .pyc or .so files
- **Boot logging** - `cp.log('Starting...')` ASAP at startup
- **Wait for connectivity** - use `cp.wait_for_wan_connection()` if internet is needed

## Python Libraries and Dependencies

- **Install libraries directly to app folder**: `pip3 install -t path/to/app_folder library_name`
- **Example**: `pip3 install -t gpio_modem_control requests`
- **CRITICAL: No .pyc or .so files** - routers only support pure Python (.py) files
- Libraries are packaged with the app and deployed to the router
- Keep dependencies minimal - routers have limited storage
- Test that libraries work on Python 3.8

## Error Handling

Always wrap API calls in try/except and log errors:

```python
try:
    data = cp.get('status/system')
    if data:
        # process data
except Exception as e:
    cp.log(f"Error getting system status: {e}")
```

## Web Development

- **Default port: 8000** - use port 8000 for web applications unless there's a conflict
- **ALWAYS set SO_REUSEADDR** before binding: `server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)`
- **ALWAYS use ES5 JavaScript syntax** - NO arrow functions `=>`, NO template literals - Python 3.8 environment doesn't support ES6
- **Use `function(){}` instead of `()=>{}`** for all functions
- **Use string concatenation `'text'+var+'more'` instead of template literals**
- **Use data attributes instead of onclick parameters** - Example: `<button data-id="123" onclick="handler(this)">` then `btn.getAttribute('data-id')`
- **Auto-refresh dashboards must preserve user input** - Save `document.activeElement.id` and `.value`, restore after innerHTML update
- Vanilla JavaScript, semantic HTML5, CSS Grid/Flexbox
- CSS variables for theming, mobile-first responsive
- Use @web_app_template as style reference
- Proper error handling with try/catch
- Serve assets locally (no external dependencies)
- Implement signal handlers for graceful shutdown
- Log which port server started on
