"""
Canvas — The central drawing surface.

This is Claude's art studio. A Canvas manages layers, elements,
gradients, and writes everything as clean SVG.

Usage:
    c = Canvas(512, 512)
    
    # Set up gradients
    c.define_gradient(Gradient.radial("fur", "#C49A3C", "#5C4400"))
    
    # Draw with mathematical precision
    body = Path()
    body.move(256, 180).cubic(...)  # complex bezier shape
    c.draw(body, fill="url(#fur)", layer="body")
    
    # Simple shapes
    c.circle(230, 160, 8, fill="#000")  # left eye
    c.circle(282, 160, 8, fill="#000")  # right eye
    
    # Export
    c.write_svg("output.svg")
"""
import xml.etree.ElementTree as ET
from typing import Optional, List, Union
from .path import Path, PathBuilder
from .color import Color, Gradient
from .transform import Transform


# Register namespaces so output is clean
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://www.inkscape.org/namespaces/inkscape"


class Canvas:
    """SVG drawing canvas — Claude's art surface.
    
    All drawing operations add elements to an internal tree.
    Call write_svg() to flush to disk, or to_svg() for the string.
    """
    
    def __init__(self, width: int = 512, height: int = 512):
        self.width = width
        self.height = height
        self._id_counter = 0
        self._layers = {}       # name -> ET.Element
        self._gradients = {}    # id -> Gradient
        self._current_layer = "default"
        self._build_tree()
    
    def _build_tree(self):
        """Create the base SVG structure."""
        self._root = ET.Element(f"{{{SVG_NS}}}svg")
        self._root.set("xmlns", "http://www.w3.org/2000/svg")
        self._root.set("xmlns:inkscape", INK_NS)
        self._root.set("width", str(self.width))
        self._root.set("height", str(self.height))
        self._root.set("viewBox", f"0 0 {self.width} {self.height}")
        self._root.set("version", "1.1")
        
        self._defs = ET.SubElement(self._root, f"{{{SVG_NS}}}defs")
        self._tree = ET.ElementTree(self._root)
    
    def _next_id(self, prefix: str = "e") -> str:
        self._id_counter += 1
        return f"{prefix}{self._id_counter}"
    
    # ── Layer Management ──
    
    def layer(self, name: str) -> 'Canvas':
        """Set the active layer. Creates it if needed.
        Elements are drawn on the active layer.
        Layers render in creation order (first = bottom)."""
        if name not in self._layers:
            g = ET.SubElement(self._root, f"{{{SVG_NS}}}g")
            g.set("id", f"layer_{name}")
            g.set(f"{{{INK_NS}}}label", name)
            g.set(f"{{{INK_NS}}}groupmode", "layer")
            self._layers[name] = g
        self._current_layer = name
        return self
    
    def _get_layer(self) -> ET.Element:
        """Get the current layer element."""
        if self._current_layer not in self._layers:
            self.layer(self._current_layer)
        return self._layers[self._current_layer]
    
    # ── Gradient Definitions ──
    
    def define_gradient(self, gradient: Gradient) -> 'Canvas':
        """Register a gradient for use in fills/strokes."""
        self._gradients[gradient.id] = gradient
        
        if gradient.type == "radial":
            el = ET.SubElement(self._defs, f"{{{SVG_NS}}}radialGradient")
            el.set("cx", gradient.cx)
            el.set("cy", gradient.cy)
            el.set("r", gradient.r)
            if gradient.fx: el.set("fx", gradient.fx)
            if gradient.fy: el.set("fy", gradient.fy)
        else:
            el = ET.SubElement(self._defs, f"{{{SVG_NS}}}linearGradient")
            el.set("x1", gradient.x1)
            el.set("y1", gradient.y1)
            el.set("x2", gradient.x2)
            el.set("y2", gradient.y2)
        
        el.set("id", gradient.id)
        
        for offset, color, opacity in gradient.stops:
            stop = ET.SubElement(el, f"{{{SVG_NS}}}stop")
            stop.set("offset", f"{offset}%")
            stop.set("style", f"stop-color:{color};stop-opacity:{opacity}")
        
        return self
    
    # ── Style Helper ──
    
    def _style(self, fill="none", stroke="none", stroke_width=0,
               opacity=1.0, extra=None) -> str:
        parts = [f"fill:{fill}", f"stroke:{stroke}"]
        if stroke != "none" and stroke_width:
            parts.append(f"stroke-width:{stroke_width}")
        if opacity < 1.0:
            parts.append(f"opacity:{opacity}")
        if extra:
            parts.extend(extra)
        return ";".join(parts)
    
    # ══════════════════════════════════════════════════════════════
    # DRAWING OPERATIONS
    # ══════════════════════════════════════════════════════════════
    
    def draw(self, path: Union[Path, str], fill="#000000", stroke="none",
             stroke_width: float = 0, opacity: float = 1.0,
             stroke_linecap: str = "round", stroke_linejoin: str = "round",
             transform: Union[Transform, str, None] = None,
             elem_id: str = None) -> str:
        """Draw a path — the core drawing operation.
        
        path: Path object or SVG path data string
        fill: color hex, 'none', or gradient url
        Returns: element ID
        """
        eid = elem_id or self._next_id("path")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}path")
        el.set("id", eid)
        el.set("d", path.d if isinstance(path, Path) else path)
        
        extra = []
        if stroke != "none":
            extra.append(f"stroke-linecap:{stroke_linecap}")
            extra.append(f"stroke-linejoin:{stroke_linejoin}")
        
        el.set("style", self._style(fill, stroke, stroke_width, opacity, extra))
        
        if transform:
            el.set("transform", str(transform))
        
        return eid
    
    def circle(self, cx: float, cy: float, r: float,
               fill="#000000", stroke="none", stroke_width=0,
               opacity=1.0, transform=None, elem_id=None) -> str:
        """Draw a circle."""
        eid = elem_id or self._next_id("circle")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}circle")
        el.set("id", eid)
        el.set("cx", f"{cx:.1f}")
        el.set("cy", f"{cy:.1f}")
        el.set("r", f"{r:.1f}")
        el.set("style", self._style(fill, stroke, stroke_width, opacity))
        if transform: el.set("transform", str(transform))
        return eid
    
    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                fill="#000000", stroke="none", stroke_width=0,
                opacity=1.0, transform=None, elem_id=None) -> str:
        """Draw an ellipse."""
        eid = elem_id or self._next_id("ellipse")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}ellipse")
        el.set("id", eid)
        el.set("cx", f"{cx:.1f}")
        el.set("cy", f"{cy:.1f}")
        el.set("rx", f"{rx:.1f}")
        el.set("ry", f"{ry:.1f}")
        el.set("style", self._style(fill, stroke, stroke_width, opacity))
        if transform: el.set("transform", str(transform))
        return eid
    
    def rect(self, x: float, y: float, w: float, h: float,
             rx: float = 0, fill="#000000", stroke="none",
             stroke_width=0, opacity=1.0, transform=None, elem_id=None) -> str:
        """Draw a rectangle."""
        eid = elem_id or self._next_id("rect")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}rect")
        el.set("id", eid)
        el.set("x", f"{x:.1f}")
        el.set("y", f"{y:.1f}")
        el.set("width", f"{w:.1f}")
        el.set("height", f"{h:.1f}")
        if rx > 0: el.set("rx", f"{rx:.1f}")
        el.set("style", self._style(fill, stroke, stroke_width, opacity))
        if transform: el.set("transform", str(transform))
        return eid
    
    def text(self, x: float, y: float, content: str,
             font_size: float = 24, font_family: str = "sans-serif",
             fill="#000000", anchor: str = "middle",
             transform=None, elem_id=None) -> str:
        """Add text."""
        eid = elem_id or self._next_id("text")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}text")
        el.set("id", eid)
        el.set("x", f"{x:.1f}")
        el.set("y", f"{y:.1f}")
        el.set("style", f"font-size:{font_size}px;font-family:{font_family};"
               f"fill:{fill};text-anchor:{anchor}")
        el.text = content
        if transform: el.set("transform", str(transform))
        return eid
    
    def line(self, x1: float, y1: float, x2: float, y2: float,
             stroke="#000000", stroke_width=2, opacity=1.0,
             stroke_linecap="round", elem_id=None) -> str:
        """Draw a line."""
        eid = elem_id or self._next_id("line")
        el = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}line")
        el.set("id", eid)
        el.set("x1", f"{x1:.1f}"); el.set("y1", f"{y1:.1f}")
        el.set("x2", f"{x2:.1f}"); el.set("y2", f"{y2:.1f}")
        el.set("style", self._style("none", stroke, stroke_width, opacity,
                                     [f"stroke-linecap:{stroke_linecap}"]))
        return eid
    
    # ── Convenience Methods ──
    
    def fill_rect(self, x: float, y: float, w: float, h: float,
                  color: str = "#FFFFFF") -> str:
        """Fill a rectangle with solid color (like a background)."""
        return self.rect(x, y, w, h, fill=color)
    
    def polygon(self, cx, cy, r, sides, fill="#000000", stroke="none",
                stroke_width=0, rotation=-90, elem_id=None) -> str:
        """Regular polygon."""
        p = PathBuilder.polygon(cx, cy, r, sides, rotation)
        return self.draw(p, fill=fill, stroke=stroke, stroke_width=stroke_width,
                        elem_id=elem_id)
    
    def star(self, cx, cy, outer_r, inner_r, points=5,
             fill="#FFD700", stroke="none", elem_id=None) -> str:
        """Star shape."""
        p = PathBuilder.star(cx, cy, outer_r, inner_r, points)
        return self.draw(p, fill=fill, stroke=stroke, elem_id=elem_id)
    
    # ── Grouping ──
    
    def begin_group(self, group_id: str = None,
                    transform: Union[Transform, str, None] = None) -> str:
        """Start a group. All subsequent draws go into this group
        until end_group() is called."""
        gid = group_id or self._next_id("g")
        g = ET.SubElement(self._get_layer(), f"{{{SVG_NS}}}g")
        g.set("id", gid)
        if transform:
            g.set("transform", str(transform))
        # Push group as current container
        self._group_stack = getattr(self, '_group_stack', [])
        self._group_stack.append((self._current_layer, self._layers.get(self._current_layer)))
        self._layers[self._current_layer] = g
        return gid
    
    def end_group(self):
        """End the current group, return to parent container."""
        if hasattr(self, '_group_stack') and self._group_stack:
            layer_name, old_container = self._group_stack.pop()
            if old_container is not None:
                self._layers[layer_name] = old_container
    
    # ══════════════════════════════════════════════════════════════
    # OUTPUT
    # ══════════════════════════════════════════════════════════════
    
    def to_svg(self) -> str:
        """Generate SVG string."""
        return ET.tostring(self._root, encoding="unicode", xml_declaration=True)
    
    def write_svg(self, path: str):
        """Write SVG to file."""
        svg_str = self.to_svg()
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg_str)
    
    def clear(self):
        """Clear everything and start fresh."""
        self._layers.clear()
        self._gradients.clear()
        self._id_counter = 0
        self._current_layer = "default"
        self._build_tree()
    
    def __repr__(self):
        n_layers = len(self._layers)
        n_elements = sum(len(list(layer)) for layer in self._layers.values())
        return f"Canvas({self.width}x{self.height}, {n_layers} layers, {n_elements} elements)"
