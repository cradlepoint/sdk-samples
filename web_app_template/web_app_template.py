#!/usr/bin/env python3
"""
Web App Template Server
Serves the web app template style guide using Python's built-in HTTP server.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Default port
PORT = 8000

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler to set proper MIME types and handle routes."""
    
    def end_headers(self):
        # Add CORS headers if needed
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Override to customize log format."""
        sys.stderr.write("%s - - [%s] %s\n" %
                        (self.address_string(),
                         self.log_date_time_string(),
                         format % args))


def main():
    """Start the HTTP server."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Check if index.html exists
    if not (script_dir / 'index.html').exists():
        print(f"Error: index.html not found in {script_dir}")
        print("Please make sure you're running this from the web_app_template directory.")
        sys.exit(1)
    
    # Create server
    handler = CustomHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("", PORT), handler) as httpd:
            print("=" * 60)
            print("Web App Template Server")
            print("=" * 60)
            print(f"Server running at: http://0.0.0.0:{PORT}")
            print(f"Serving directory: {script_dir}")
            print(f"\nPress Ctrl+C to stop the server")
            print("=" * 60)
            
            # Start serving
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"\nError: Port {PORT} is already in use.")
            print(f"Please stop the process using port {PORT} or change the PORT variable.")
        else:
            print(f"\nError starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
