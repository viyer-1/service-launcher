#!/usr/bin/env python3
"""
Simple web application example (Zero-dependency)
Demonstrates how to create a web app that can be launched via Service Launcher.
Uses only Python standard library.
"""

import http.server
import socketserver
import argparse
import sys
import threading

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Example Web App</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.6;
            color: #333;
        }
        .container {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background-color: #f9f9f9;
        }
        h1 { color: #2563eb; }
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            background-color: #dcfce7;
            color: #166534;
            font-weight: bold;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hello from the Example App!</h1>
        <div class="status">Running via Service Launcher</div>
        
        <p>This is a simple web application started as a background process.</p>
        
        <p><strong>How it works:</strong></p>
        <ul>
            <li>Service Launcher executes the command: <code>python3 ./examples/example_webapp.py --port 8080</code></li>
            <li>The script starts this web server.</li>
            <li>The UI provides an "Open" button linked to this port.</li>
            <li>When you click "Stop" in Service Launcher, this process is terminated.</li>
        </ul>
        
        <p>Current Time: <span id="time"></span></p>
    </div>

    <script>
        document.getElementById('time').textContent = new Date().toLocaleTimeString();
        setInterval(() => {
            document.getElementById('time').textContent = new Date().toLocaleTimeString();
        }, 1000);
    </script>
</body>
</html>
"""

class SimpleHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode())

    def log_message(self, format, *args):
        # Log to stdout so it shows up in Service Launcher's live output
        sys.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format%args))
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description='Example zero-dependency web app')
    parser.add_argument('--port', type=int, default=8080, help='Port to run on')
    args = parser.parse_args()

    # Use ThreadingTCPServer to handle multiple requests if needed
    with socketserver.ThreadingTCPServer(("", args.port), SimpleHandler) as httpd:
        print(f"Example web app starting on port {args.port}...")
        print(f"Access it at http://localhost:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.shutdown()

if __name__ == "__main__":
    main()
