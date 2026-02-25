"""
Inkpilot MCP — Live Preview Server
HTTP + Server-Sent Events for real-time SVG preview in browser.
"""
import http.server
import json
import os
import queue
import threading
import time
from pathlib import Path

VIEWER_DIR = Path(__file__).parent / "viewer"
DEFAULT_PORT = 7878


class LiveServer:
    """
    Serves the live preview page and pushes SVG updates via SSE.
    """

    def __init__(self, canvas, port=DEFAULT_PORT, open_inkscape_fn=None):
        self.canvas = canvas
        self.port = port
        self.clients = []
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self.open_inkscape_fn = open_inkscape_fn

        canvas.on_change(self._on_canvas_change)

    def _on_canvas_change(self, svg_str):
        with self._lock:
            dead = []
            for q in self.clients:
                try:
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            break
                    q.put(svg_str)
                except Exception:
                    dead.append(q)
            for q in dead:
                self.clients.remove(q)

    def _add_client(self):
        q = queue.Queue(maxsize=5)
        with self._lock:
            self.clients.append(q)
        return q

    def _remove_client(self, q):
        with self._lock:
            if q in self.clients:
                self.clients.remove(q)

    def start(self):
        server_ref = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self._serve_file("index.html", "text/html")
                elif self.path == "/events":
                    self._serve_sse()
                elif self.path == "/svg":
                    svg = server_ref.canvas.to_svg()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/svg+xml")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(svg.encode("utf-8"))
                elif self.path == "/status":
                    state = server_ref.canvas.get_state()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "running", "canvas": state}).encode())
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path == "/open-inkscape":
                    self._handle_open_inkscape()
                else:
                    self.send_error(404)

            def _handle_open_inkscape(self):
                """Open current canvas in Inkscape (triggered from browser button)."""
                try:
                    if server_ref.open_inkscape_fn:
                        result = server_ref.open_inkscape_fn()
                    else:
                        result = "No open_inkscape function configured"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"result": result}).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())

            def _serve_file(self, filename, content_type):
                filepath = VIEWER_DIR / filename
                if filepath.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.end_headers()
                    self.wfile.write(filepath.read_bytes())
                else:
                    self.send_error(404)

            def _serve_sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                client_q = server_ref._add_client()

                try:
                    svg = server_ref.canvas.to_svg()
                    self.wfile.write(f"data: {json.dumps({'svg': svg})}\n\n".encode())
                    self.wfile.flush()
                except Exception:
                    server_ref._remove_client(client_q)
                    return

                try:
                    while True:
                        try:
                            svg = client_q.get(timeout=15)
                            self.wfile.write(f"data: {json.dumps({'svg': svg})}\n\n".encode())
                            self.wfile.flush()
                        except queue.Empty:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    server_ref._remove_client(client_q)

            def log_message(self, format, *args):
                pass

        # Allow port reuse to prevent "address already in use" after restart
        http.server.HTTPServer.allow_reuse_address = True
        
        for attempt in range(3):
            try:
                self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
                break
            except OSError as e:
                if attempt < 2:
                    # Port may be held by a dead process — wait and retry
                    import time as _time
                    _time.sleep(1)
                else:
                    # Last resort: try next port
                    self.port += 1
                    self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://localhost:{self.port}"

    def stop(self):
        if self._server:
            self._server.shutdown()
