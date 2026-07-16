# hspt
Demonstrates how to serve a custom HotSpot captive portal splash page using the router's built-in HTTP server control API. When clients connect to the device's HotSpot WiFi, they are presented with a custom landing page instead of the default.

## How It Works

The app registers route maps with the router's internal HTTP server (`/control/system/httpserver`) to serve static files from the app directory. This replaces the default captive portal page with custom HTML and resources.

The app:
1. Builds route maps for the root path (`/`) and resources path (`/resources/`)
2. Sends a `start` action to the `hotspotServer` via the control API
3. The router then serves the app's static files as the captive portal

## File Structure

Place your custom splash page files in the app directory:
- HTML files in the root of the app directory
- CSS, JS, images in a `resources/` subdirectory

## Configuration

The router's HotSpot feature must be enabled and configured:
1. Enable HotSpot in the router's WiFi settings
2. Configure the captive portal to use the SDK-provided page
3. Install and start this app

## Customizing the Splash Page

Edit or replace the HTML files in the app directory to customize the captive portal appearance. The `resources/` directory is mapped separately for serving static assets like stylesheets, scripts, and images.

For detailed information about the HTTP server control API and route configuration, see `dynui.txt` in the application directory (if included).

## Sample Log Output

```
Started Hotspot Server
```

## Requirements

- WiFi-enabled Cradlepoint router
- HotSpot feature enabled and configured
- Router firmware 7.26 or later
