#!/usr/bin/env python3
"""
Simple web application example
Demonstrates how to create a web app that can be launched via Script Runner
"""

from flask import Flask, render_template_string
import argparse

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Example Web App</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        h1 {
            margin-top: 0;
        }
        .info {
            background: rgba(255, 255, 255, 0.2);
            padding: 20px;
            border-radius: 5px;
            margin-top: 20px;
        }
        .status {
            display: inline-block;
            background: #10b981;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Example Web Application</h1>
        <p><span class="status">● Running</span></p>
        
        <div class="info">
            <h2>This is a demo web application</h2>
            <p>This application was started via Script Runner!</p>
            <p>You can:</p>
            <ul>
                <li>Start the app from the Script Runner interface</li>
                <li>Click the "Open" button to view it</li>
                <li>Monitor its output in real-time</li>
                <li>Stop it when you're done</li>
            </ul>
        </div>
        
        <div class="info">
            <h3>Running on port: {{ port }}</h3>
            <p>Access at: <strong>http://localhost:{{ port }}</strong></p>
            <p><em>Or use your server's IP address to access from other devices</em></p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, port=app.config['PORT'])

def main():
    parser = argparse.ArgumentParser(description='Example web application')
    parser.add_argument('--port', type=int, default=8080, help='Port to run on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    
    args = parser.parse_args()
    
    app.config['PORT'] = args.port
    
    print(f"Starting Example Web Application...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"URL: http://localhost:{args.port}")
    print("-" * 50)
    print("Server is running. Press Ctrl+C to stop.")
    
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()
