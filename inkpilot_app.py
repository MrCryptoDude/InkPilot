"""
Inkpilot — Local Bridge Server
HTTP API that lets Claude (via browser) control Inkscape.
Works with both Claude in Chrome (HTTP) and Claude Desktop (MCP).

Usage: python inkpilot_app.py
"""
import json
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from inkpilot_mcp.canvas import SVGCanvas
from inkpilot_mcp.inkscape import InkscapeController, find_inkscape

# ── Paths ────────────────────────────────────────────────────────

HOME = os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or os.path.expanduser("~")
WORK_DIR = os.path.join(HOME, ".inkpilot")
WORK_FILE = os.path.join(WORK_DIR, "canvas.svg")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── State ────────────────────────────────────────────────────────

canvas = SVGCanvas(512, 512)
inkscape = InkscapeController(WORK_FILE)
ink_opened = False


def save_and_sync():
    canvas.save(WORK_FILE)


# ── Tool dispatch ────────────────────────────────────────────────

def handle_tool(name, args):
    global ink_opened

    if name == "setup_canvas":
        canvas.clear()
        r = canvas.set_canvas(args.get("width", 512), args.get("height", 512))
        save_and_sync()
        if not ink_opened:
            r += "\n" + inkscape.open_file()
            ink_opened = True
            r += f"\nFile: {WORK_FILE}"
        return r

    elif name == "create_layer":
        r = canvas.create_layer(args["label"])
        save_and_sync()
        return r

    elif name == "switch_layer":
        r = canvas.switch_layer(args["label"])
        save_and_sync()
        return r

    elif name == "draw_pixel_region":
        r = canvas.draw_pixel_region(
            pixels=args["pixels"], size=args.get("size", 8),
            offset_x=args.get("offset_x", 0), offset_y=args.get("offset_y", 0),
            label=args.get("label"),
        )
        save_and_sync()
        return r

    elif name == "draw_pixel_row":
        ids = canvas.draw_pixel_row(
            y=args["y"], colors=args["colors"],
            size=args.get("size", 8), start_x=args.get("start_x", 0),
        )
        save_and_sync()
        return f"Drew {len(ids)} pixels on row {args['y']}"

    elif name == "draw_rect":
        safe = {k: v for k, v in args.items() if v is not None}
        eid = canvas.draw_rect(**safe)
        save_and_sync()
        return f"rect {eid}"

    elif name == "draw_circle":
        safe = {k: v for k, v in args.items() if v is not None}
        eid = canvas.draw_circle(**safe)
        save_and_sync()
        return f"circle {eid}"

    elif name == "draw_path":
        safe = {k: v for k, v in args.items() if v is not None}
        eid = canvas.draw_path(**safe)
        save_and_sync()
        return f"path {eid}"

    elif name == "draw_text":
        safe = {k: v for k, v in args.items() if v is not None}
        eid = canvas.draw_text(**safe)
        save_and_sync()
        return f"text {eid}"

    elif name == "draw_polygon":
        safe = {k: v for k, v in args.items() if v is not None}
        eid = canvas.draw_polygon(**safe)
        save_and_sync()
        return f"polygon {eid}"

    elif name == "insert_svg":
        r = canvas.insert_svg(args["svg"])
        save_and_sync()
        return r

    elif name == "delete":
        r = canvas.delete_element(args["element_id"])
        save_and_sync()
        return r

    elif name == "get_state":
        return canvas.get_state() + f"\nFile: {WORK_FILE}"

    elif name == "refresh":
        save_and_sync()
        return inkscape.reopen()

    elif name == "save":
        fname = args.get("filename", f"inkpilot_{int(time.time())}.svg")
        path = os.path.join(OUTPUT_DIR, fname)
        canvas.save(path)
        return f"Saved to {path}"

    elif name == "clear":
        canvas.clear()
        canvas.set_canvas(512, 512)
        save_and_sync()
        return "Canvas cleared"

    else:
        return f"Unknown tool: {name}"


# ── HTTP Server ──────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self._ok({"status": "running", "inkscape_found": find_inkscape() is not None,
                       "file": WORK_FILE})
        elif self.path == "/state":
            self._ok({"state": canvas.get_state(), "file": WORK_FILE})
        elif self.path == "/svg":
            svg = canvas.to_svg()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(svg.encode())
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/tool":
            name = body.get("name", "")
            args = body.get("args", {})
            try:
                result = handle_tool(name, args)
                self._ok({"result": result})
            except Exception as e:
                self._err(str(e))

        elif self.path == "/batch":
            # Execute multiple tools in sequence
            steps = body.get("steps", [])
            results = []
            for step in steps:
                try:
                    r = handle_tool(step.get("name", ""), step.get("args", {}))
                    results.append({"ok": True, "result": r})
                except Exception as e:
                    results.append({"ok": False, "error": str(e)})
            self._ok({"results": results, "count": len(results)})

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _ok(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _err(self, msg):
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

    def log_message(self, *args):
        pass


# ── Main ─────────────────────────────────────────────────────────

def main():
    port = 7878
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  ✦ Inkpilot — Claude ↔ Inkscape Bridge       ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print(f"  🌐 API running on http://localhost:{port}")
    print(f"  📁 Working file: {WORK_FILE}")
    print(f"  📂 Saved SVGs:   {OUTPUT_DIR}")

    ink = find_inkscape()
    if ink:
        print(f"  ✓ Inkscape found")
    else:
        print(f"  ⚠ Inkscape not found in PATH")

    print()
    print("  Ready! Tell Claude to draw something.")
    print("  Press Ctrl+C to stop.")
    print()

    server = HTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
