"""
Inkpilot — SVG Composer (Claude's Artistic Brain)

This is where the actual ART happens. Instead of simulating mouse drags
to draw like a toddler, Claude generates precise SVG elements:
- Complex bezier paths for organic shapes
- Gradients and fills for depth/shading
- Layered composition for professional results

The generated SVG is written to the canvas file, and Inkscape renders it.
Inkscape's GUI is still used for operations like boolean ops, tracing, etc.

This is how professional vector artists actually work — paths + precision.
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

# Register SVG namespaces
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"


class SVGComposer:
    """Programmatic SVG element creation — Claude's artistic toolkit.
    
    Every method returns the element ID so it can be referenced later
    (for grouping, boolean ops, styling changes, etc.)
    """
    
    def __init__(self, svg_path: str):
        self.svg_path = svg_path
        self._id_counter = 0
    
    def _next_id(self, prefix="elem"):
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"
    
    def _load(self):
        """Load the SVG file."""
        tree = ET.parse(self.svg_path)
        return tree
    
    def _save(self, tree):
        """Save the SVG file."""
        tree.write(self.svg_path, encoding="unicode", xml_declaration=True)
    
    def _get_root(self, tree):
        """Get the root SVG element."""
        return tree.getroot()
    
    def _find_or_create_layer(self, tree, layer_name="artwork"):
        """Find or create a named Inkscape layer."""
        root = self._get_root(tree)
        # Look for existing layer
        for g in root.findall(f"{{{SVG_NS}}}g"):
            label = g.get(f"{{{INKSCAPE_NS}}}label", "")
            if label == layer_name:
                return g
        # Create new layer
        layer = ET.SubElement(root, f"{{{SVG_NS}}}g")
        layer.set(f"{{{INKSCAPE_NS}}}label", layer_name)
        layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
        layer.set("id", f"layer_{layer_name}")
        return layer
    
    # ══════════════════════════════════════════════════════════════
    # PRIMITIVE SHAPES
    # ══════════════════════════════════════════════════════════════
    
    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                fill: str = "#8B6914", stroke: str = "none",
                stroke_width: float = 0, opacity: float = 1.0,
                layer: str = "artwork", elem_id: str = None) -> str:
        """Draw an ellipse. Returns element ID."""
        eid = elem_id or self._next_id("ellipse")
        tree = self._load()
        parent = self._find_or_create_layer(tree, layer)
        
        el = ET.SubElement(parent, f"{{{SVG_NS}}}ellipse")
        el.set("id", eid)
        el.set("cx", str(cx))
        el.set("cy", str(cy))
        el.set("rx", str(rx))
        el.set("ry", str(ry))
        el.set("style", self._style(fill, stroke, stroke_width, opacity))
        
        self._save(tree)
        return eid
    
    def circle(self, cx: float, cy: float, r: float, **kwargs) -> str:
        """Draw a circle (convenience wrapper)."""
        return self.ellipse(cx, cy, r, r, **kwargs)
    
    def rect(self, x: float, y: float, w: float, h: float,
             rx: float = 0, ry: float = 0,
             fill: str = "#8B6914", stroke: str = "none",
             stroke_width: float = 0, opacity: float = 1.0,
             layer: str = "artwork", elem_id: str = None) -> str:
        """Draw a rectangle. rx/ry for rounded corners. Returns element ID."""
        eid = elem_id or self._next_id("rect")
        tree = self._load()
        parent = self._find_or_create_layer(tree, layer)
        
        el = ET.SubElement(parent, f"{{{SVG_NS}}}rect")
        el.set("id", eid)
        el.set("x", str(x))
        el.set("y", str(y))
        el.set("width", str(w))
        el.set("height", str(h))
        if rx: el.set("rx", str(rx))
        if ry: el.set("ry", str(ry))
        el.set("style", self._style(fill, stroke, stroke_width, opacity))
        
        self._save(tree)
        return eid
    
    # ══════════════════════════════════════════════════════════════
    # PATH — The real artistic power
    # ══════════════════════════════════════════════════════════════
    
    def path(self, d: str,
             fill: str = "#8B6914", stroke: str = "none",
             stroke_width: float = 0, opacity: float = 1.0,
             stroke_linecap: str = "round", stroke_linejoin: str = "round",
             layer: str = "artwork", elem_id: str = None) -> str:
        """Draw an SVG path using path data string.
        
        d: SVG path data (M, L, C, Q, A, Z commands)
        
        Examples:
          "M 100 200 L 300 200 L 200 400 Z"  — triangle
          "M 100 200 C 100 100, 250 100, 250 200 S 400 300, 400 200"  — S-curve
          "M 256 50 Q 400 150, 256 250 Q 112 150, 256 50 Z"  — leaf shape
        
        Returns element ID.
        """
        eid = elem_id or self._next_id("path")
        tree = self._load()
        parent = self._find_or_create_layer(tree, layer)
        
        el = ET.SubElement(parent, f"{{{SVG_NS}}}path")
        el.set("id", eid)
        el.set("d", d)
        style = self._style(fill, stroke, stroke_width, opacity)
        if stroke != "none":
            style += f";stroke-linecap:{stroke_linecap};stroke-linejoin:{stroke_linejoin}"
        el.set("style", style)
        
        self._save(tree)
        return eid
    
    def line(self, x1: float, y1: float, x2: float, y2: float,
             stroke: str = "#000000", stroke_width: float = 2,
             layer: str = "artwork", elem_id: str = None) -> str:
        """Draw a line segment."""
        d = f"M {x1} {y1} L {x2} {y2}"
        return self.path(d, fill="none", stroke=stroke,
                        stroke_width=stroke_width, layer=layer, elem_id=elem_id)
    
    def polyline(self, points: List[Tuple[float, float]],
                 closed: bool = False,
                 fill: str = "none", stroke: str = "#000000",
                 stroke_width: float = 2,
                 layer: str = "artwork", elem_id: str = None) -> str:
        """Draw a polyline or polygon from a list of points."""
        if not points:
            return ""
        d = f"M {points[0][0]} {points[0][1]}"
        for x, y in points[1:]:
            d += f" L {x} {y}"
        if closed:
            d += " Z"
        return self.path(d, fill=fill, stroke=stroke,
                        stroke_width=stroke_width, layer=layer, elem_id=elem_id)
    
    def bezier_shape(self, curves: List[dict],
                     fill: str = "#8B6914", stroke: str = "none",
                     stroke_width: float = 0, opacity: float = 1.0,
                     layer: str = "artwork", elem_id: str = None) -> str:
        """Draw a complex shape from cubic bezier curves.
        
        curves: list of dicts, each with:
          - 'to': (x, y) — end point
          - 'c1': (x, y) — first control point  
          - 'c2': (x, y) — second control point
          
        The first curve starts from 'start' key.
        Automatically closes the path.
        
        Example — teardrop shape:
          bezier_shape([
              {'to': (300, 256), 'c1': (200, 100), 'c2': (350, 100)},
              {'to': (256, 450), 'c1': (400, 350), 'c2': (300, 450)},
              {'to': (200, 256), 'c1': (212, 450), 'c2': (100, 350)},
          ], start=(256, 200))
        """
        if not curves:
            return ""
        
        # Find start point from first curve context or default
        start = curves[0].get('start', curves[-1]['to'])
        d = f"M {start[0]} {start[1]}"
        
        for c in curves:
            c1 = c['c1']
            c2 = c['c2']
            to = c['to']
            d += f" C {c1[0]} {c1[1]}, {c2[0]} {c2[1]}, {to[0]} {to[1]}"
        
        d += " Z"
        return self.path(d, fill=fill, stroke=stroke,
                        stroke_width=stroke_width, opacity=opacity,
                        layer=layer, elem_id=elem_id)
    
    # ══════════════════════════════════════════════════════════════
    # GRADIENTS & ADVANCED FILLS
    # ══════════════════════════════════════════════════════════════
    
    def add_linear_gradient(self, grad_id: str,
                            x1: str = "0%", y1: str = "0%",
                            x2: str = "0%", y2: str = "100%",
                            stops: list = None) -> str:
        """Add a linear gradient to defs. Returns gradient ID.
        
        stops: list of (offset%, color, opacity) tuples
          e.g. [(0, "#8B6914", 1.0), (100, "#5C4400", 1.0)]
        """
        tree = self._load()
        root = self._get_root(tree)
        
        # Find or create defs
        defs = root.find(f"{{{SVG_NS}}}defs")
        if defs is None:
            defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
            root.insert(0, defs)  # defs should be first
        
        grad = ET.SubElement(defs, f"{{{SVG_NS}}}linearGradient")
        grad.set("id", grad_id)
        grad.set("x1", x1)
        grad.set("y1", y1)
        grad.set("x2", x2)
        grad.set("y2", y2)
        
        if stops:
            for offset, color, opacity in stops:
                stop = ET.SubElement(grad, f"{{{SVG_NS}}}stop")
                stop.set("offset", f"{offset}%")
                stop.set("style", f"stop-color:{color};stop-opacity:{opacity}")
        
        self._save(tree)
        return grad_id
    
    def add_radial_gradient(self, grad_id: str,
                            cx: str = "50%", cy: str = "50%",
                            r: str = "50%",
                            fx: str = None, fy: str = None,
                            stops: list = None) -> str:
        """Add a radial gradient to defs. Returns gradient ID."""
        tree = self._load()
        root = self._get_root(tree)
        
        defs = root.find(f"{{{SVG_NS}}}defs")
        if defs is None:
            defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
            root.insert(0, defs)
        
        grad = ET.SubElement(defs, f"{{{SVG_NS}}}linearGradient")  # fix: radialGradient
        grad.tag = f"{{{SVG_NS}}}radialGradient"
        grad.set("id", grad_id)
        grad.set("cx", cx)
        grad.set("cy", cy)
        grad.set("r", r)
        if fx: grad.set("fx", fx)
        if fy: grad.set("fy", fy)
        
        if stops:
            for offset, color, opacity in stops:
                stop = ET.SubElement(grad, f"{{{SVG_NS}}}stop")
                stop.set("offset", f"{offset}%")
                stop.set("style", f"stop-color:{color};stop-opacity:{opacity}")
        
        self._save(tree)
        return grad_id
    
    # ══════════════════════════════════════════════════════════════
    # GROUPING & TRANSFORMS
    # ══════════════════════════════════════════════════════════════
    
    def group(self, element_ids: List[str], group_id: str = None,
              transform: str = None, layer: str = "artwork") -> str:
        """Group elements together. Returns group ID."""
        gid = group_id or self._next_id("group")
        tree = self._load()
        root = self._get_root(tree)
        parent = self._find_or_create_layer(tree, layer)
        
        g = ET.SubElement(parent, f"{{{SVG_NS}}}g")
        g.set("id", gid)
        if transform:
            g.set("transform", transform)
        
        # Move elements into group
        for eid in element_ids:
            el = root.find(f".//*[@id='{eid}']")
            if el is not None:
                # Remove from current parent
                for p in root.iter():
                    if el in list(p):
                        p.remove(el)
                        break
                g.append(el)
        
        self._save(tree)
        return gid
    
    def set_transform(self, elem_id: str, transform: str):
        """Apply a transform to an element."""
        tree = self._load()
        root = self._get_root(tree)
        el = root.find(f".//*[@id='{elem_id}']")
        if el is not None:
            el.set("transform", transform)
            self._save(tree)
    
    # ══════════════════════════════════════════════════════════════
    # STYLE & COLORS
    # ══════════════════════════════════════════════════════════════
    
    def set_style(self, elem_id: str, fill: str = None, stroke: str = None,
                  stroke_width: float = None, opacity: float = None):
        """Change the style of an existing element."""
        tree = self._load()
        root = self._get_root(tree)
        el = root.find(f".//*[@id='{elem_id}']")
        if el is None:
            return
        
        current = el.get("style", "")
        styles = {}
        if current:
            for part in current.split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    styles[k.strip()] = v.strip()
        
        if fill is not None: styles["fill"] = fill
        if stroke is not None: styles["stroke"] = stroke
        if stroke_width is not None: styles["stroke-width"] = str(stroke_width)
        if opacity is not None: styles["opacity"] = str(opacity)
        
        el.set("style", ";".join(f"{k}:{v}" for k, v in styles.items()))
        self._save(tree)
    
    # ══════════════════════════════════════════════════════════════
    # TEXT
    # ══════════════════════════════════════════════════════════════
    
    def text(self, x: float, y: float, content: str,
             font_size: float = 24, font_family: str = "sans-serif",
             fill: str = "#000000", anchor: str = "middle",
             layer: str = "artwork", elem_id: str = None) -> str:
        """Add text element."""
        eid = elem_id or self._next_id("text")
        tree = self._load()
        parent = self._find_or_create_layer(tree, layer)
        
        el = ET.SubElement(parent, f"{{{SVG_NS}}}text")
        el.set("id", eid)
        el.set("x", str(x))
        el.set("y", str(y))
        el.set("style", f"font-size:{font_size}px;font-family:{font_family};"
               f"fill:{fill};text-anchor:{anchor}")
        el.text = content
        
        self._save(tree)
        return eid
    
    # ══════════════════════════════════════════════════════════════
    # BATCH OPERATIONS
    # ══════════════════════════════════════════════════════════════
    
    def batch_elements(self, elements: List[dict]) -> List[str]:
        """Add multiple elements in one file write (much faster).
        
        elements: list of dicts, each with:
          - 'type': 'ellipse'|'rect'|'path'|'circle'
          - plus type-specific params (cx, cy, rx, ry, d, etc.)
          - 'fill', 'stroke', 'stroke_width', 'opacity' (optional)
          - 'layer' (optional, default 'artwork')
          - 'id' (optional)
        
        Returns list of element IDs.
        """
        tree = self._load()
        ids = []
        
        for elem in elements:
            etype = elem.get("type", "path")
            layer_name = elem.get("layer", "artwork")
            parent = self._find_or_create_layer(tree, layer_name)
            
            eid = elem.get("id") or self._next_id(etype)
            fill = elem.get("fill", "#8B6914")
            stroke = elem.get("stroke", "none")
            stroke_width = elem.get("stroke_width", 0)
            opacity = elem.get("opacity", 1.0)
            style = self._style(fill, stroke, stroke_width, opacity)
            
            if etype == "ellipse":
                el = ET.SubElement(parent, f"{{{SVG_NS}}}ellipse")
                el.set("cx", str(elem["cx"]))
                el.set("cy", str(elem["cy"]))
                el.set("rx", str(elem["rx"]))
                el.set("ry", str(elem["ry"]))
            
            elif etype == "circle":
                el = ET.SubElement(parent, f"{{{SVG_NS}}}ellipse")
                el.set("cx", str(elem["cx"]))
                el.set("cy", str(elem["cy"]))
                el.set("rx", str(elem["r"]))
                el.set("ry", str(elem["r"]))
            
            elif etype == "rect":
                el = ET.SubElement(parent, f"{{{SVG_NS}}}rect")
                el.set("x", str(elem["x"]))
                el.set("y", str(elem["y"]))
                el.set("width", str(elem["w"]))
                el.set("height", str(elem["h"]))
                if elem.get("rx"): el.set("rx", str(elem["rx"]))
                if elem.get("ry"): el.set("ry", str(elem["ry"]))
            
            elif etype == "path":
                el = ET.SubElement(parent, f"{{{SVG_NS}}}path")
                el.set("d", elem["d"])
                if stroke != "none":
                    style += ";stroke-linecap:round;stroke-linejoin:round"
            
            elif etype == "text":
                el = ET.SubElement(parent, f"{{{SVG_NS}}}text")
                el.set("x", str(elem.get("x", 0)))
                el.set("y", str(elem.get("y", 0)))
                el.text = elem.get("content", "")
                fs = elem.get("font_size", 24)
                ff = elem.get("font_family", "sans-serif")
                style += f";font-size:{fs}px;font-family:{ff};text-anchor:middle"
            
            else:
                continue
            
            el.set("id", eid)
            el.set("style", style)
            
            if elem.get("transform"):
                el.set("transform", elem["transform"])
            
            ids.append(eid)
        
        self._save(tree)
        return ids
    
    def clear(self, layer: str = None):
        """Remove all elements (or just from a specific layer)."""
        tree = self._load()
        root = self._get_root(tree)
        
        if layer:
            for g in root.findall(f"{{{SVG_NS}}}g"):
                if g.get(f"{{{INKSCAPE_NS}}}label", "") == layer:
                    root.remove(g)
        else:
            # Remove all g elements (layers) but keep defs
            for g in list(root.findall(f"{{{SVG_NS}}}g")):
                root.remove(g)
            # Also remove any direct children that aren't defs
            for child in list(root):
                if child.tag != f"{{{SVG_NS}}}defs":
                    root.remove(child)
        
        self._save(tree)
    
    # ── Internal Helpers ──
    
    def _style(self, fill, stroke, stroke_width, opacity):
        parts = [f"fill:{fill}", f"stroke:{stroke}"]
        if stroke != "none" and stroke_width:
            parts.append(f"stroke-width:{stroke_width}")
        if opacity < 1.0:
            parts.append(f"opacity:{opacity}")
        return ";".join(parts)
