"""
Inkpilot Bridge — Inkscape Extension Server

This extension runs INSIDE Inkscape's process. It:
1. Starts a local TCP server in a background thread
2. Listens for JSON commands from the Inkpilot MCP server
3. Executes them through Inkscape's native inkex API
4. Returns results (element IDs, document state, etc.)

Claude controls Inkscape the same way Claude Code controls VSCode —
not by writing files next to it, but by working THROUGH its runtime.

Installation:
  Copy this file + inkpilot_bridge.inx to Inkscape's extensions folder:
    Windows: %APPDATA%\inkscape\extensions\
    Linux: ~/.config/inkscape/extensions/
    Mac: ~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/

Usage:
  1. Open Inkscape
  2. Extensions → Inkpilot → Start Bridge Server
  3. The bridge listens on localhost:9147
  4. Inkpilot MCP server connects and sends drawing commands
"""
import inkex
from inkex import (
    Layer, Group, PathElement, Circle, Ellipse, Rectangle,
    TextElement, Use, Image, Line, Polyline, Polygon,
    LinearGradient, RadialGradient, Stop, ClipPath, Filter,
    Style, Transform
)
from lxml import etree
import threading
import socketserver
import json
import sys
import os
import traceback


# ── Constants ────────────────────────────────────────────────────

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9147
SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"


# ══════════════════════════════════════════════════════════════════
# COMMAND EXECUTOR — Runs drawing commands on the live document
# ══════════════════════════════════════════════════════════════════

class CommandExecutor:
    """Executes drawing commands on the live Inkscape document.
    
    This runs INSIDE Inkscape's process with full access to:
    - The live SVG document (self.svg)
    - All inkex element types
    - Inkscape's layer system
    - Transform, style, gradient, filter APIs
    - The undo system
    """
    
    def __init__(self, svg_element):
        self.svg = svg_element
        self._id_counter = 0
    
    def _next_id(self, prefix="ip"):
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"
    
    def _ensure_id(self, given_id, prefix):
        return given_id or self._next_id(prefix)
    
    def _get_or_create_layer(self, name="artwork"):
        """Find or create a named Inkscape layer."""
        for child in self.svg:
            if (child.tag == f"{{{SVG_NS}}}g" and
                child.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer" and
                child.get(f"{{{INKSCAPE_NS}}}label") == name):
                return child
        
        # Create new layer
        layer = etree.SubElement(self.svg, f"{{{SVG_NS}}}g")
        layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
        layer.set(f"{{{INKSCAPE_NS}}}label", name)
        layer.set("id", f"layer_{name}")
        return layer
    
    def _apply_style(self, element, params):
        """Apply style from command params to element."""
        style_parts = []
        style_parts.append(f"fill:{params.get('fill', '#000000')}")
        style_parts.append(f"stroke:{params.get('stroke', 'none')}")
        
        sw = params.get("stroke_width", 0)
        if sw and params.get("stroke", "none") != "none":
            style_parts.append(f"stroke-width:{sw}")
            style_parts.append(f"stroke-linecap:{params.get('stroke_linecap', 'round')}")
            style_parts.append(f"stroke-linejoin:{params.get('stroke_linejoin', 'round')}")
        
        opacity = params.get("opacity", 1.0)
        if opacity < 1.0:
            style_parts.append(f"opacity:{opacity}")
        
        fill_opacity = params.get("fill_opacity", 1.0)
        if fill_opacity < 1.0:
            style_parts.append(f"fill-opacity:{fill_opacity}")
        
        element.set("style", ";".join(style_parts))
    
    def _apply_transform(self, element, params):
        """Apply transform if present."""
        t = params.get("transform")
        if t:
            element.set("transform", t)
    
    # ── Drawing Commands ──
    
    def execute(self, command: dict) -> dict:
        """Execute a single command. Returns result dict."""
        cmd = command.get("cmd", "")
        params = command.get("params", {})
        
        try:
            handler = getattr(self, f"cmd_{cmd}", None)
            if handler:
                result = handler(params)
                return {"ok": True, "result": result}
            else:
                return {"ok": False, "error": f"Unknown command: {cmd}"}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}
    
    def cmd_ellipse(self, p) -> dict:
        """Draw an ellipse."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        eid = self._ensure_id(p.get("id"), "ellipse")
        
        el = etree.SubElement(layer, f"{{{SVG_NS}}}ellipse")
        el.set("id", eid)
        el.set("cx", str(p["cx"]))
        el.set("cy", str(p["cy"]))
        el.set("rx", str(p["rx"]))
        el.set("ry", str(p.get("ry", p["rx"])))
        self._apply_style(el, p)
        self._apply_transform(el, p)
        
        return {"id": eid}
    
    def cmd_circle(self, p) -> dict:
        """Draw a circle."""
        p["rx"] = p["r"]
        p["ry"] = p["r"]
        return self.cmd_ellipse(p)
    
    def cmd_rect(self, p) -> dict:
        """Draw a rectangle."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        eid = self._ensure_id(p.get("id"), "rect")
        
        el = etree.SubElement(layer, f"{{{SVG_NS}}}rect")
        el.set("id", eid)
        el.set("x", str(p["x"]))
        el.set("y", str(p["y"]))
        el.set("width", str(p["w"]))
        el.set("height", str(p["h"]))
        if p.get("rx"): el.set("rx", str(p["rx"]))
        if p.get("ry"): el.set("ry", str(p.get("ry", p.get("rx", 0))))
        self._apply_style(el, p)
        self._apply_transform(el, p)
        
        return {"id": eid}
    
    def cmd_path(self, p) -> dict:
        """Draw an SVG path."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        eid = self._ensure_id(p.get("id"), "path")
        
        el = etree.SubElement(layer, f"{{{SVG_NS}}}path")
        el.set("id", eid)
        el.set("d", p["d"])
        self._apply_style(el, p)
        self._apply_transform(el, p)
        
        return {"id": eid}
    
    def cmd_text(self, p) -> dict:
        """Add a text element."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        eid = self._ensure_id(p.get("id"), "text")
        
        el = etree.SubElement(layer, f"{{{SVG_NS}}}text")
        el.set("id", eid)
        el.set("x", str(p.get("x", 0)))
        el.set("y", str(p.get("y", 0)))
        el.text = p.get("content", "")
        
        fs = p.get("font_size", 24)
        ff = p.get("font_family", "sans-serif")
        ta = p.get("text_anchor", "middle")
        fill = p.get("fill", "#000000")
        el.set("style", f"font-size:{fs}px;font-family:{ff};text-anchor:{ta};fill:{fill}")
        self._apply_transform(el, p)
        
        return {"id": eid}
    
    def cmd_image(self, p) -> dict:
        """Embed a raster image."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        eid = self._ensure_id(p.get("id"), "image")
        
        el = etree.SubElement(layer, f"{{{SVG_NS}}}image")
        el.set("id", eid)
        el.set("x", str(p.get("x", 0)))
        el.set("y", str(p.get("y", 0)))
        el.set("width", str(p.get("w", 100)))
        el.set("height", str(p.get("h", 100)))
        el.set(f"{{{INKSCAPE_NS}}}href", p.get("href", ""))
        self._apply_transform(el, p)
        
        return {"id": eid}
    
    # ── Gradient Commands ──
    
    def cmd_linear_gradient(self, p) -> dict:
        """Add a linear gradient to defs."""
        defs = self.svg.find(f"{{{SVG_NS}}}defs")
        if defs is None:
            defs = etree.SubElement(self.svg, f"{{{SVG_NS}}}defs")
            self.svg.insert(0, defs)
        
        gid = p.get("id", self._next_id("lg"))
        grad = etree.SubElement(defs, f"{{{SVG_NS}}}linearGradient")
        grad.set("id", gid)
        grad.set("x1", str(p.get("x1", "0%")))
        grad.set("y1", str(p.get("y1", "0%")))
        grad.set("x2", str(p.get("x2", "0%")))
        grad.set("y2", str(p.get("y2", "100%")))
        
        for stop in p.get("stops", []):
            s = etree.SubElement(grad, f"{{{SVG_NS}}}stop")
            s.set("offset", f"{stop[0]}%")
            s.set("style", f"stop-color:{stop[1]};stop-opacity:{stop[2] if len(stop) > 2 else 1.0}")
        
        return {"id": gid}
    
    def cmd_radial_gradient(self, p) -> dict:
        """Add a radial gradient to defs."""
        defs = self.svg.find(f"{{{SVG_NS}}}defs")
        if defs is None:
            defs = etree.SubElement(self.svg, f"{{{SVG_NS}}}defs")
            self.svg.insert(0, defs)
        
        gid = p.get("id", self._next_id("rg"))
        grad = etree.SubElement(defs, f"{{{SVG_NS}}}radialGradient")
        grad.set("id", gid)
        grad.set("cx", str(p.get("cx", "50%")))
        grad.set("cy", str(p.get("cy", "50%")))
        grad.set("r", str(p.get("r", "50%")))
        if p.get("fx"): grad.set("fx", str(p["fx"]))
        if p.get("fy"): grad.set("fy", str(p["fy"]))
        
        for stop in p.get("stops", []):
            s = etree.SubElement(grad, f"{{{SVG_NS}}}stop")
            s.set("offset", f"{stop[0]}%")
            s.set("style", f"stop-color:{stop[1]};stop-opacity:{stop[2] if len(stop) > 2 else 1.0}")
        
        return {"id": gid}
    
    # ── Layer Commands ──
    
    def cmd_create_layer(self, p) -> dict:
        """Create a new Inkscape layer."""
        name = p.get("name", "New Layer")
        layer = self._get_or_create_layer(name)
        
        # Set visibility
        if p.get("hidden"):
            layer.set("style", "display:none")
        
        # Set opacity
        opacity = p.get("opacity")
        if opacity is not None and opacity < 1.0:
            layer.set("opacity", str(opacity))
        
        return {"id": layer.get("id"), "name": name}
    
    def cmd_list_layers(self, p) -> dict:
        """List all layers in the document."""
        layers = []
        for child in self.svg:
            if (child.tag == f"{{{SVG_NS}}}g" and
                child.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer"):
                layers.append({
                    "id": child.get("id"),
                    "name": child.get(f"{{{INKSCAPE_NS}}}label", "unnamed"),
                    "visible": child.get("style", "") != "display:none",
                })
        return {"layers": layers}
    
    # ── Manipulation Commands ──
    
    def cmd_set_style(self, p) -> dict:
        """Change style of an existing element."""
        eid = p.get("id")
        el = self.svg.xpath(f"//*[@id='{eid}']")
        if not el:
            return {"error": f"Element '{eid}' not found"}
        el = el[0]
        
        # Parse existing style
        current = el.get("style", "")
        styles = {}
        if current:
            for part in current.split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    styles[k.strip()] = v.strip()
        
        # Update
        if "fill" in p: styles["fill"] = p["fill"]
        if "stroke" in p: styles["stroke"] = p["stroke"]
        if "stroke_width" in p: styles["stroke-width"] = str(p["stroke_width"])
        if "opacity" in p: styles["opacity"] = str(p["opacity"])
        
        el.set("style", ";".join(f"{k}:{v}" for k, v in styles.items()))
        return {"id": eid}
    
    def cmd_set_transform(self, p) -> dict:
        """Set transform on an element."""
        eid = p.get("id")
        el = self.svg.xpath(f"//*[@id='{eid}']")
        if not el:
            return {"error": f"Element '{eid}' not found"}
        el[0].set("transform", p.get("transform", ""))
        return {"id": eid}
    
    def cmd_delete(self, p) -> dict:
        """Delete an element by ID."""
        eid = p.get("id")
        el = self.svg.xpath(f"//*[@id='{eid}']")
        if not el:
            return {"error": f"Element '{eid}' not found"}
        el[0].getparent().remove(el[0])
        return {"deleted": eid}
    
    def cmd_group(self, p) -> dict:
        """Group elements together."""
        layer = self._get_or_create_layer(p.get("layer", "artwork"))
        gid = self._ensure_id(p.get("id"), "group")
        
        g = etree.SubElement(layer, f"{{{SVG_NS}}}g")
        g.set("id", gid)
        if p.get("transform"):
            g.set("transform", p["transform"])
        
        for eid in p.get("element_ids", []):
            el = self.svg.xpath(f"//*[@id='{eid}']")
            if el:
                el[0].getparent().remove(el[0])
                g.append(el[0])
        
        return {"id": gid}
    
    def cmd_duplicate(self, p) -> dict:
        """Duplicate an element."""
        eid = p.get("id")
        el = self.svg.xpath(f"//*[@id='{eid}']")
        if not el:
            return {"error": f"Element '{eid}' not found"}
        
        import copy
        new_el = copy.deepcopy(el[0])
        new_id = self._next_id("dup")
        new_el.set("id", new_id)
        el[0].getparent().append(new_el)
        
        if p.get("transform"):
            new_el.set("transform", p["transform"])
        
        return {"id": new_id}
    
    def cmd_move_to_layer(self, p) -> dict:
        """Move an element to a different layer."""
        eid = p.get("id")
        target_layer = p.get("layer", "artwork")
        
        el = self.svg.xpath(f"//*[@id='{eid}']")
        if not el:
            return {"error": f"Element '{eid}' not found"}
        
        layer = self._get_or_create_layer(target_layer)
        el[0].getparent().remove(el[0])
        layer.append(el[0])
        
        return {"id": eid, "layer": target_layer}
    
    # ── Batch Command ──
    
    def cmd_batch(self, p) -> dict:
        """Execute multiple commands in one call. Maximum efficiency."""
        commands = p.get("commands", [])
        results = []
        for cmd in commands:
            result = self.execute(cmd)
            results.append(result)
        return {"count": len(results), "results": results}
    
    # ── Document Commands ──
    
    def cmd_clear(self, p) -> dict:
        """Clear all elements (optionally just one layer)."""
        target_layer = p.get("layer")
        
        if target_layer:
            for child in list(self.svg):
                if (child.tag == f"{{{SVG_NS}}}g" and
                    child.get(f"{{{INKSCAPE_NS}}}label") == target_layer):
                    for el in list(child):
                        child.remove(el)
        else:
            for child in list(self.svg):
                if child.tag != f"{{{SVG_NS}}}defs":
                    self.svg.remove(child)
        
        return {"cleared": target_layer or "all"}
    
    def cmd_get_document_info(self, p) -> dict:
        """Get document dimensions, layers, element count."""
        w = self.svg.get("width", "0")
        h = self.svg.get("height", "0")
        
        layers = []
        element_count = 0
        for child in self.svg:
            if (child.tag == f"{{{SVG_NS}}}g" and
                child.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer"):
                name = child.get(f"{{{INKSCAPE_NS}}}label", "unnamed")
                count = len(list(child))
                layers.append({"name": name, "elements": count})
                element_count += count
        
        return {
            "width": w, "height": h,
            "layers": layers,
            "total_elements": element_count,
        }
    
    def cmd_save(self, p) -> dict:
        """Save document to a file path."""
        path = p.get("path")
        if not path:
            return {"error": "No path specified"}
        
        tree = self.svg.getroottree()
        tree.write(path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        return {"saved": path}
    
    def cmd_export_png(self, p) -> dict:
        """Export as PNG (triggers Inkscape's native export)."""
        # This needs to be handled differently — through Inkscape's
        # export action system rather than inkex directly.
        # For now, return instructions for the MCP server to use CLI.
        return {"error": "Use Inkscape CLI export (not available via inkex bridge)"}


# ══════════════════════════════════════════════════════════════════
# TCP SERVER — Receives commands from Inkpilot MCP server
# ══════════════════════════════════════════════════════════════════

class BridgeHandler(socketserver.StreamRequestHandler):
    """Handles JSON commands over TCP from the MCP server."""
    
    def handle(self):
        """Read newline-delimited JSON commands, execute, return results."""
        self.server.executor  # Reference to CommandExecutor
        
        while True:
            try:
                line = self.rfile.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                command = json.loads(line.decode("utf-8"))
                result = self.server.executor.execute(command)
                
                response = json.dumps(result) + "\n"
                self.wfile.write(response.encode("utf-8"))
                self.wfile.flush()
                
            except json.JSONDecodeError as e:
                error = json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}) + "\n"
                self.wfile.write(error.encode("utf-8"))
                self.wfile.flush()
            except ConnectionResetError:
                break
            except Exception as e:
                error = json.dumps({"ok": False, "error": str(e)}) + "\n"
                try:
                    self.wfile.write(error.encode("utf-8"))
                    self.wfile.flush()
                except:
                    break


class BridgeServer(socketserver.ThreadingTCPServer):
    """TCP server that holds reference to the CommandExecutor."""
    allow_reuse_address = True
    daemon_threads = True
    
    def __init__(self, address, handler, executor):
        self.executor = executor
        super().__init__(address, handler)


# ══════════════════════════════════════════════════════════════════
# INKSCAPE EXTENSION — Entry point when launched from Inkscape UI
# ══════════════════════════════════════════════════════════════════

class InkpilotBridgeExtension(inkex.EffectExtension):
    """Inkscape extension that starts the bridge server.
    
    When activated via Extensions → Inkpilot → Start Bridge,
    this starts a TCP server inside Inkscape's process.
    The MCP server connects to it and sends drawing commands.
    """
    
    def add_arguments(self, pars):
        pars.add_argument("--port", type=int, default=BRIDGE_PORT,
                         help="Port for the bridge server")
    
    def effect(self):
        """Called by Inkscape when the extension is activated."""
        port = self.options.port
        
        # Create executor with access to the live document
        executor = CommandExecutor(self.svg)
        
        # Start TCP server in background thread
        server = BridgeServer((BRIDGE_HOST, port), BridgeHandler, executor)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        inkex.errormsg(f"[Inkpilot] Bridge server started on {BRIDGE_HOST}:{port}")
        inkex.errormsg("[Inkpilot] Claude can now control this Inkscape document.")
        
        # The extension returns — Inkscape continues normally.
        # The server thread runs in the background handling commands.
        # When Inkscape closes, daemon thread is killed automatically.


# ── Standalone mode (for testing) ────────────────────────────────

if __name__ == "__main__":
    InkpilotBridgeExtension().run()
