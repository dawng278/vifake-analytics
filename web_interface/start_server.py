#!/usr/bin/env python3
"""
ViFake Analytics Web Interface Server
Simple HTTP server for local testing interface
"""

import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

def start_web_server(port=8080):
    """Start web server for the interface"""
    
    # Change to web interface directory
    web_dir = Path(__file__).parent
    os.chdir(web_dir)
    
    print(f"🚀 Starting ViFake Analytics Web Interface")
    print(f"📁 Serving from: {web_dir}")
    print(f"🌐 Server URL: http://localhost:{port}")
    print(f"📖 Open browser to: http://localhost:{port}")
    print(f"⚠️  Make sure API Gateway is running on http://localhost:8000")
    print(f"🛑 Press Ctrl+C to stop server")
    print("=" * 50)
    
    # Create handler
    handler = http.server.SimpleHTTPRequestHandler
    
    try:
        # Start server
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"✅ Server started on port {port}")
            
            # Auto-open browser
            try:
                webbrowser.open(f'http://localhost:{port}')
                print(f"🌐 Browser opened automatically")
            except:
                print(f"⚠️  Could not open browser automatically")
                print(f"💡 Please open http://localhost:{port} manually")
            
            print(f"🔄 Server running... (Press Ctrl+C to stop)")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n🛑 Server stopped by user")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use")
            print(f"💡 Try a different port: python3 start_server.py 8081")
        else:
            print(f"❌ Server error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    import sys
    
    # Get port from command line or use default
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    
    start_web_server(port)
