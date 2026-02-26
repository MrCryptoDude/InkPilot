"""
CreativeBridge — SVG Document Engine

In-memory SVG document manipulation. Zero file I/O during composition.
Build entire illustrations, then flush once to disk.

This is Claude's artistic brain — every shape, gradient, curve, and
layer lives here in memory until flushed to the target application.

Design principles:
- FAST: All operations in memory, single flush to disk
- PRECISE: Mathematical coordinate system, not pixel guessing
- COMPOSABLE: Elements reference each other, gradients, clip paths
- REVERSIBLE: Full undo/redo stack
- EXTENSIBLE: Foundation for any SVG-based creative workflow
"""
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
import copy
import time


# ── SVG Namespace Registration ────────────────────────────────
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("inkscape", "http://www.inkscape.org/namespaces/inkscape")
ET.register_namespace("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

NS = {
    "svg": "http://www.w3.org/2000/svg",
    "ink": "http://www.inkscape.org/namespaces/inkscape",
    "sodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}

SVG = NS["svg"]
INK = NS["ink"]


# ══════════════════════════════════════════════════════════════════
# DATA MODEL — Lightweight descriptors for all SVG elements
# ══════════════════════════════════════════════════════════════════

@dataclass
class Style:
    """CSS-like style for SVG elements."""
    fill: str = "#000000"
    stroke: str = "none"
    stroke_width: float = 0
    opacity: float = 1.0
    fill_opacity: float = 1.0
    stroke_opacity: float = 1.0
    stroke_linecap: str = "round"
    stroke_linejoin: str = "round"
    
    def to_str(self) -> str:
        parts = [f"fill:{self.fill}", f"stroke:{self.stroke}"]
        if self.stroke != "none" and self.stroke_width > 0:
            parts.append(f"stroke-width:{self.stroke_width}")
            parts.append(f"stroke-linecap:{self.stroke_linecap}")
            parts.append(f"stroke-linejoin:{self.stroke_linejoin}")
            if self.stroke_opacity < 1.0:
                parts.append(f"stroke-opacity:{self.stroke_opacity}")
        if self.opacity < 1.0:
            parts.append(f"opacity:{self.opacity}")
        if self.fill_opacity < 1.0:
            parts.append(f"fill-opacity:{self.fill_opacity}")
        return ";".join(parts)
    
    @staticmethod
    def from_dict(d: dict) -> 'Style':
        s = Style()
        if "fill" in d: s.fill = d["fill"]
        if "stroke" in d: s.stroke = d["stroke"]
        if "stroke_width" in d: s.stroke_width = d["stroke_width"]
        if "opacity" in d: s.opacity = d["opacity"]
        if "fill_opacity" in d: s.fill_opacity = d["fill_opacity"]
        if "stroke_opacity" in d: s.stroke_opacity = d["stroke_opacity"]
        if "stroke_linecap" in d: s.stroke_linecap = d["stroke_linecap"]
        if "stroke_linejoin" in d: s.stroke_linejoin = d["stroke_linejoin"]
        return s


@dataclass
class Element:
    """Base element in the document."""
    id: str
    tag: str
    attrs: Dict[str, str] = field(default_factory=dict)
    style: Style = field(default_factory=Style)
    transform: Optional[str] = None
    children: List['Element'] = field(default_factory=list)
    text: Optional[str] = None  # For text elements
    layer: str = "artwork"
    
    def to_xml(self, parent: ET.Element):
        """Serialize this element to XML under parent."""
        el = ET.SubElement(parent, f"{{{SVG}}}{self.tag}")
        el.set("id", self.id)
        
        for k, v in self.attrs.items():
            el.set(k, str(v))
        
        el.set("style", self.style.to_str())
        
        if self.transform:
            el.set("transform", self.transform)
        
        if self.text:
            el.text = self.text
        
        for child in self.children:
            child.to_xml(el)
        
        return el


@dataclass
class GradientStop:
    offset: float  # 0-100
    color: str
    opacity: float = 1.0


@dataclass
class Gradient:
    id: str
    type: str  # "linear" or "radial"
    stops: List[GradientStop] = field(default_factory=list)
    # Linear: x1,y1 → x2,y2
    x1: str = "0%"
    y1: str = "0%"
    x2: str = "0%"
    y2: str = "100%"
    # Radial: cx,cy,r,fx,fy
    cx: str = "50%"
    cy: str = "50%"
    r: str = "50%"
    fx: Optional[str] = None
    fy: Optional[str] = None
    # Transform
    transform: Optional[str] = None
    
    def to_xml(self, defs: ET.Element):
        tag = "linearGradient" if self.type == "linear" else "radialGradient"
        el = ET.SubElement(defs, f"{{{SVG}}}{tag}")
        el.set("id", self.id)
        
        if self.type == "linear":
            el.set("x1", self.x1)
            el.set("y1", self.y1)
            el.set("x2", self.x2)
            el.set("y2", self.y2)
        else:
            el.set("cx", self.cx)
            el.set("cy", self.cy)
            el.set("r", self.r)
            if self.fx: el.set("fx", self.fx)
            if self.fy: el.set("fy", self.fy)
        
        if self.transform:
            el.set("gradientTransform", self.transform)
        
        for stop in self.stops:
            s = ET.SubElement(el, f"{{{SVG}}}stop")
            s.set("offset", f"{stop.offset}%")
            s.set("style", f"stop-color:{stop.color};stop-opacity:{stop.opacity}")
        
        return el


@dataclass
class Filter:
    """SVG filter definition."""
    id: str
    primitives: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_xml(self, defs: ET.Element):
        el = ET.SubElement(defs, f"{{{SVG}}}filter")
        el.set("id", self.id)
        
        for prim in self.primitives:
            ptype = prim.get("type", "feGaussianBlur")
            p = ET.SubElement(el, f"{{{SVG}}}{ptype}")
            for k, v in prim.items():
                if k != "type":
                    p.set(k, str(v))
        
        return el


@dataclass
class ClipPath:
    """SVG clip path definition."""
    id: str
    elements: List[Element] = field(default_factory=list)
    
    def to_xml(self, defs: ET.Element):
        el = ET.SubElement(defs, f"{{{SVG}}}clipPath")
        el.set("id", self.id)
        for elem in self.elements:
            elem.to_xml(el)
        return el


# ══════════════════════════════════════════════════════════════════
# SVG DOCUMENT — The complete in-memory document
# ══════════════════════════════════════════════════════════════════

class SVGDocument:
    """In-memory SVG document with full creative capabilities.
    
    Usage:
        doc = SVGDocument(512, 512)
        doc.ellipse("body", cx=256, cy=300, rx=80, ry=120, fill="#8B6914")
        doc.path("outline", d="M 100 200 C ...", stroke="#000", stroke_width=2)
        doc.flush("/path/to/file.svg")
    """
    
    def __init__(self, width: int = 512, height: int = 512):
        self.width = width
        self.height = height
        
        # Document contents
        self.gradients: Dict[str, Gradient] = {}
        self.filters: Dict[str, Filter] = {}
        self.clip_paths: Dict[str, ClipPath] = {}
        self.layers: Dict[str, List[Element]] = {"artwork": []}
        self.layer_order: List[str] = ["artwork"]
        
        # ID tracking
        self._id_counter = 0
        self._ids: set = set()
        
        # Undo stack
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        self._dirty = False
    
    # ── ID Management ──
    
    def _next_id(self, prefix: str = "e") -> str:
        self._id_counter += 1
        eid = f"{prefix}_{self._id_counter}"
        while eid in self._ids:
            self._id_counter += 1
            eid = f"{prefix}_{self._id_counter}"
        self._ids.add(eid)
        return eid
    
    def _ensure_id(self, elem_id: Optional[str], prefix: str) -> str:
        if elem_id:
            self._ids.add(elem_id)
            return elem_id
        return self._next_id(prefix)
    
    # ── Layer Management ──
    
    def add_layer(self, name: str, position: int = -1) -> str:
        """Create a new layer. Returns layer name."""
        if name not in self.layers:
            self.layers[name] = []
            if position < 0:
                self.layer_order.append(name)
            else:
                self.layer_order.insert(position, name)
        return name
    
    def _get_layer(self, name: str) -> List[Element]:
        if name not in self.layers:
            self.add_layer(name)
        return self.layers[name]
    
    # ── State Management ──
    
    def _snapshot(self) -> dict:
        """Capture current state for undo."""
        return {
            "gradients": copy.deepcopy(self.gradients),
            "filters": copy.deepcopy(self.filters),
            "clip_paths": copy.deepcopy(self.clip_paths),
            "layers": copy.deepcopy(self.layers),
            "layer_order": list(self.layer_order),
            "id_counter": self._id_counter,
            "ids": set(self._ids),
        }
    
    def _restore(self, snap: dict):
        """Restore state from snapshot."""
        self.gradients = snap["gradients"]
        self.filters = snap["filters"]
        self.clip_paths = snap["clip_paths"]
        self.layers = snap["layers"]
        self.layer_order = snap["layer_order"]
        self._id_counter = snap["id_counter"]
        self._ids = snap["ids"]
        self._dirty = True
    
    def _push_undo(self):
        """Save current state to undo stack."""
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()  # New action clears redo
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)  # Limit stack size
    
    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        return True
    
    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        return True
    
    def clear(self, layer: str = None):
        """Clear all elements or a specific layer."""
        self._push_undo()
        if layer:
            if layer in self.layers:
                self.layers[layer] = []
        else:
            for k in self.layers:
                self.layers[k] = []
            self.gradients.clear()
            self.filters.clear()
            self.clip_paths.clear()
        self._dirty = True
    
    # ══════════════════════════════════════════════════════════════
    # SHAPES — The building blocks
    # ══════════════════════════════════════════════════════════════
    
    def _make_style(self, **kwargs) -> Style:
        return Style.from_dict(kwargs)
    
    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                layer: str = "artwork", id: str = None, **style_kwargs) -> str:
        """Add an ellipse. Returns element ID."""
        self._push_undo()
        eid = self._ensure_id(id, "ellipse")
        elem = Element(
            id=eid, tag="ellipse",
            attrs={"cx": str(cx), "cy": str(cy), "rx": str(rx), "ry": str(ry)},
            style=self._make_style(**style_kwargs),
            layer=layer,
        )
        self._get_layer(layer).append(elem)
        self._dirty = True
        return eid
    
    def circle(self, cx: float, cy: float, r: float, **kwargs) -> str:
        """Add a circle. Returns element ID."""
        return self.ellipse(cx, cy, r, r, **kwargs)
    
    def rect(self, x: float, y: float, w: float, h: float,
             rx: float = 0, ry: float = 0,
             layer: str = "artwork", id: str = None, **style_kwargs) -> str:
        """Add a rectangle. Returns element ID."""
        self._push_undo()
        eid = self._ensure_id(id, "rect")
        attrs = {"x": str(x), "y": str(y), "width": str(w), "height": str(h)}
        if rx: attrs["rx"] = str(rx)
        if ry: attrs["ry"] = str(ry)
        elem = Element(
            id=eid, tag="rect", attrs=attrs,
            style=self._make_style(**style_kwargs),
            layer=layer,
        )
        self._get_layer(layer).append(elem)
        self._dirty = True
        return eid
    
    def path(self, d: str,
             layer: str = "artwork", id: str = None, **style_kwargs) -> str:
        """Add an SVG path. The most powerful drawing primitive.
        
        d: SVG path data string
            M x y       — move to
            L x y       — line to
            H x         — horizontal line
            V y         — vertical line
            C x1 y1 x2 y2 x y — cubic bezier
            S x2 y2 x y — smooth cubic bezier
            Q x1 y1 x y — quadratic bezier
            T x y       — smooth quadratic
            A rx ry rot large sweep x y — arc
            Z           — close path
        
        Returns element ID.
        """
        self._push_undo()
        eid = self._ensure_id(id, "path")
        elem = Element(
            id=eid, tag="path",
            attrs={"d": d},
            style=self._make_style(**style_kwargs),
            layer=layer,
        )
        self._get_layer(layer).append(elem)
        self._dirty = True
        return eid
    
    def text(self, x: float, y: float, content: str,
             font_size: float = 24, font_family: str = "sans-serif",
             text_anchor: str = "middle",
             layer: str = "artwork", id: str = None, **style_kwargs) -> str:
        """Add a text element. Returns element ID."""
        self._push_undo()
        eid = self._ensure_id(id, "text")
        style = self._make_style(**style_kwargs)
        # Override style string to include font properties
        font_style = (f"font-size:{font_size}px;font-family:{font_family};"
                     f"text-anchor:{text_anchor};{style.to_str()}")
        elem = Element(
            id=eid, tag="text",
            attrs={"x": str(x), "y": str(y)},
            style=style,
            text=content,
            layer=layer,
        )
        # Store font info in attrs for serialization
        elem.attrs["__font_size"] = str(font_size)
        elem.attrs["__font_family"] = font_family
        elem.attrs["__text_anchor"] = text_anchor
        self._get_layer(layer).append(elem)
        self._dirty = True
        return eid
    
    def line(self, x1: float, y1: float, x2: float, y2: float, **kwargs) -> str:
        """Convenience: draw a line segment."""
        if "fill" not in kwargs: kwargs["fill"] = "none"
        if "stroke" not in kwargs: kwargs["stroke"] = "#000000"
        if "stroke_width" not in kwargs: kwargs["stroke_width"] = 2
        return self.path(f"M {x1} {y1} L {x2} {y2}", **kwargs)
    
    def polygon(self, points: List[Tuple[float, float]], **kwargs) -> str:
        """Draw a closed polygon from points."""
        if not points: return ""
        d = f"M {points[0][0]} {points[0][1]}"
        for x, y in points[1:]:
            d += f" L {x} {y}"
        d += " Z"
        return self.path(d, **kwargs)
    
    # ══════════════════════════════════════════════════════════════
    # GRADIENTS & DEFINITIONS
    # ══════════════════════════════════════════════════════════════
    
    def linear_gradient(self, grad_id: str,
                        stops: List[Tuple[float, str, float]],
                        x1="0%", y1="0%", x2="0%", y2="100%",
                        transform: str = None) -> str:
        """Define a linear gradient. Returns gradient ID.
        
        stops: [(offset%, color, opacity), ...]
        Use as fill="url(#grad_id)"
        """
        g = Gradient(
            id=grad_id, type="linear",
            stops=[GradientStop(s[0], s[1], s[2]) for s in stops],
            x1=x1, y1=y1, x2=x2, y2=y2, transform=transform,
        )
        self.gradients[grad_id] = g
        self._dirty = True
        return grad_id
    
    def radial_gradient(self, grad_id: str,
                        stops: List[Tuple[float, str, float]],
                        cx="50%", cy="50%", r="50%",
                        fx=None, fy=None,
                        transform: str = None) -> str:
        """Define a radial gradient. Returns gradient ID."""
        g = Gradient(
            id=grad_id, type="radial",
            stops=[GradientStop(s[0], s[1], s[2]) for s in stops],
            cx=cx, cy=cy, r=r, fx=fx, fy=fy, transform=transform,
        )
        self.gradients[grad_id] = g
        self._dirty = True
        return grad_id
    
    def filter(self, filter_id: str,
               primitives: List[Dict[str, Any]]) -> str:
        """Define an SVG filter. Returns filter ID.
        
        primitives: list of dicts with 'type' and filter-specific attrs.
        
        Examples:
          [{"type": "feGaussianBlur", "stdDeviation": "3"}]
          [{"type": "feDropShadow", "dx": "2", "dy": "2", "stdDeviation": "3"}]
        
        Use as filter="url(#filter_id)"
        """
        f = Filter(id=filter_id, primitives=primitives)
        self.filters[filter_id] = f
        self._dirty = True
        return filter_id
    
    def clip_path(self, clip_id: str, shape_d: str) -> str:
        """Define a clip path from path data. Returns clip ID.
        
        Use as clip-path="url(#clip_id)"
        """
        elem = Element(id=f"{clip_id}_shape", tag="path",
                       attrs={"d": shape_d}, style=Style(fill="#000000"))
        cp = ClipPath(id=clip_id, elements=[elem])
        self.clip_paths[clip_id] = cp
        self._dirty = True
        return clip_id
    
    # ══════════════════════════════════════════════════════════════
    # GROUPING & TRANSFORMS
    # ══════════════════════════════════════════════════════════════
    
    def group(self, element_ids: List[str], group_id: str = None,
              transform: str = None, layer: str = "artwork") -> str:
        """Group elements. Moves them into a <g> container."""
        self._push_undo()
        gid = self._ensure_id(group_id, "group")
        
        # Find and remove elements from their layers
        children = []
        for eid in element_ids:
            for lname, elems in self.layers.items():
                for i, e in enumerate(elems):
                    if e.id == eid:
                        children.append(elems.pop(i))
                        break
        
        group_elem = Element(
            id=gid, tag="g", style=Style(),
            transform=transform, children=children, layer=layer,
        )
        self._get_layer(layer).append(group_elem)
        self._dirty = True
        return gid
    
    def set_transform(self, elem_id: str, transform: str):
        """Set transform on an element."""
        elem = self._find_element(elem_id)
        if elem:
            elem.transform = transform
            self._dirty = True
    
    def set_style(self, elem_id: str, **style_kwargs):
        """Update style properties of an element."""
        elem = self._find_element(elem_id)
        if elem:
            for k, v in style_kwargs.items():
                if hasattr(elem.style, k):
                    setattr(elem.style, k, v)
            self._dirty = True
    
    def remove(self, elem_id: str) -> bool:
        """Remove an element by ID."""
        self._push_undo()
        for lname, elems in self.layers.items():
            for i, e in enumerate(elems):
                if e.id == elem_id:
                    elems.pop(i)
                    self._ids.discard(elem_id)
                    self._dirty = True
                    return True
                # Check in groups
                if e.tag == "g":
                    for j, child in enumerate(e.children):
                        if child.id == elem_id:
                            e.children.pop(j)
                            self._ids.discard(elem_id)
                            self._dirty = True
                            return True
        return False
    
    def _find_element(self, elem_id: str) -> Optional[Element]:
        """Find an element by ID across all layers."""
        for lname, elems in self.layers.items():
            for e in elems:
                if e.id == elem_id:
                    return e
                if e.tag == "g":
                    for child in e.children:
                        if child.id == elem_id:
                            return child
        return None
    
    # ══════════════════════════════════════════════════════════════
    # BATCH OPERATIONS — For maximum efficiency
    # ══════════════════════════════════════════════════════════════
    
    def batch(self, elements: List[dict]) -> List[str]:
        """Add multiple elements in one operation (single undo point).
        
        elements: list of dicts, each with:
          - 'type': 'ellipse'|'circle'|'rect'|'path'|'text'
          - type-specific params
          - style params (fill, stroke, etc.)
          - 'layer', 'id', 'transform' (optional)
        
        Returns list of element IDs.
        """
        self._push_undo()
        ids = []
        
        for elem in elements:
            etype = elem.get("type", "path")
            layer = elem.get("layer", "artwork")
            eid = self._ensure_id(elem.get("id"), etype)
            transform = elem.get("transform")
            
            # Build style from dict
            style = self._make_style(
                fill=elem.get("fill", "#8B6914"),
                stroke=elem.get("stroke", "none"),
                stroke_width=elem.get("stroke_width", 0),
                opacity=elem.get("opacity", 1.0),
                fill_opacity=elem.get("fill_opacity", 1.0),
                stroke_opacity=elem.get("stroke_opacity", 1.0),
            )
            
            if etype == "ellipse":
                el = Element(id=eid, tag="ellipse", style=style, layer=layer,
                            transform=transform,
                            attrs={"cx": str(elem["cx"]), "cy": str(elem["cy"]),
                                   "rx": str(elem["rx"]), "ry": str(elem["ry"])})
            
            elif etype == "circle":
                r = str(elem["r"])
                el = Element(id=eid, tag="ellipse", style=style, layer=layer,
                            transform=transform,
                            attrs={"cx": str(elem["cx"]), "cy": str(elem["cy"]),
                                   "rx": r, "ry": r})
            
            elif etype == "rect":
                attrs = {"x": str(elem["x"]), "y": str(elem["y"]),
                        "width": str(elem["w"]), "height": str(elem["h"])}
                if elem.get("rx"): attrs["rx"] = str(elem["rx"])
                if elem.get("ry"): attrs["ry"] = str(elem.get("ry", elem.get("rx", 0)))
                el = Element(id=eid, tag="rect", style=style, layer=layer,
                            transform=transform, attrs=attrs)
            
            elif etype == "path":
                el = Element(id=eid, tag="path", style=style, layer=layer,
                            transform=transform, attrs={"d": elem["d"]})
            
            elif etype == "text":
                el = Element(id=eid, tag="text", style=style, layer=layer,
                            transform=transform, text=elem.get("content", ""),
                            attrs={"x": str(elem.get("x", 0)),
                                   "y": str(elem.get("y", 0)),
                                   "__font_size": str(elem.get("font_size", 24)),
                                   "__font_family": elem.get("font_family", "sans-serif"),
                                   "__text_anchor": elem.get("text_anchor", "middle")})
            else:
                continue
            
            self._get_layer(layer).append(el)
            ids.append(eid)
        
        self._dirty = True
        return ids
    
    # ══════════════════════════════════════════════════════════════
    # SERIALIZATION — Build the SVG XML tree
    # ══════════════════════════════════════════════════════════════
    
    def to_xml(self) -> ET.Element:
        """Build complete SVG XML tree from in-memory model."""
        # Use {namespace}tag format — ET.register_namespace handles xmlns declarations.
        # Do NOT manually set xmlns attributes, as that causes duplicates.
        root = ET.Element(f"{{{SVG}}}svg")
        root.set("width", str(self.width))
        root.set("height", str(self.height))
        root.set("viewBox", f"0 0 {self.width} {self.height}")
        root.set("version", "1.1")
        
        # Defs (gradients, filters, clip paths)
        defs = ET.SubElement(root, f"{{{SVG}}}defs")
        for g in self.gradients.values():
            g.to_xml(defs)
        for f in self.filters.values():
            f.to_xml(defs)
        for cp in self.clip_paths.values():
            cp.to_xml(defs)
        
        # Layers (in order)
        for lname in self.layer_order:
            if lname not in self.layers:
                continue
            elems = self.layers[lname]
            if not elems and lname == "artwork":
                # Always include artwork layer even if empty
                layer_g = ET.SubElement(root, f"{{{SVG}}}g")
                layer_g.set(f"{{{INK}}}label", lname)
                layer_g.set(f"{{{INK}}}groupmode", "layer")
                layer_g.set("id", f"layer_{lname}")
                continue
            
            layer_g = ET.SubElement(root, f"{{{SVG}}}g")
            layer_g.set(f"{{{INK}}}label", lname)
            layer_g.set(f"{{{INK}}}groupmode", "layer")
            layer_g.set("id", f"layer_{lname}")
            
            for elem in elems:
                self._serialize_element(elem, layer_g)
        
        return root
    
    def _serialize_element(self, elem: Element, parent: ET.Element):
        """Serialize a single element to XML."""
        el = ET.SubElement(parent, f"{{{SVG}}}{elem.tag}")
        el.set("id", elem.id)
        
        # Handle text elements specially
        if elem.tag == "text":
            fs = elem.attrs.pop("__font_size", "24")
            ff = elem.attrs.pop("__font_family", "sans-serif")
            ta = elem.attrs.pop("__text_anchor", "middle")
            style_str = (f"font-size:{fs}px;font-family:{ff};"
                        f"text-anchor:{ta};{elem.style.to_str()}")
            el.set("style", style_str)
            # Restore hidden attrs for future serializations
            elem.attrs["__font_size"] = fs
            elem.attrs["__font_family"] = ff
            elem.attrs["__text_anchor"] = ta
        else:
            el.set("style", elem.style.to_str())
        
        for k, v in elem.attrs.items():
            if not k.startswith("__"):  # Skip internal attrs
                el.set(k, str(v))
        
        if elem.transform:
            el.set("transform", elem.transform)
        
        if elem.text:
            el.text = elem.text
        
        for child in elem.children:
            self._serialize_element(child, el)
    
    def to_string(self) -> str:
        """Generate SVG string."""
        root = self.to_xml()
        # Minimal XML declaration
        ET.indent(root, space="  ")
        return ('<?xml version="1.0" encoding="UTF-8"?>\n' +
                ET.tostring(root, encoding="unicode"))
    
    def flush(self, path: str):
        """Write SVG to disk. Single I/O operation."""
        svg_str = self.to_string()
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg_str)
        self._dirty = False
    
    # ══════════════════════════════════════════════════════════════
    # INTROSPECTION — Know what's on the canvas
    # ══════════════════════════════════════════════════════════════
    
    def element_count(self) -> int:
        return sum(len(elems) for elems in self.layers.values())
    
    def list_elements(self) -> List[dict]:
        """List all elements with their basic info."""
        result = []
        for lname in self.layer_order:
            for elem in self.layers.get(lname, []):
                result.append({
                    "id": elem.id,
                    "type": elem.tag,
                    "layer": lname,
                    "fill": elem.style.fill,
                    "transform": elem.transform,
                })
        return result
    
    def summary(self) -> str:
        """Human-readable document summary."""
        lines = [f"SVG {self.width}×{self.height}"]
        lines.append(f"Gradients: {len(self.gradients)}")
        lines.append(f"Filters: {len(self.filters)}")
        for lname in self.layer_order:
            elems = self.layers.get(lname, [])
            lines.append(f"Layer '{lname}': {len(elems)} elements")
            for e in elems:
                lines.append(f"  {e.id} ({e.tag}) fill={e.style.fill}")
        return "\n".join(lines)
