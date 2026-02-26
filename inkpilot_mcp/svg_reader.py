"""
Inkpilot MCP — SVG File Reader
ONLY reads and inspects SVG files. Never writes.
All modifications go through Inkscape's engine.
"""
from lxml import etree
import os

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"
XLINK_NS = "http://www.w3.org/1999/xlink"


class SVGReader:
    """
    Read-only SVG file inspector.
    All modifications go through Inkscape's CLI engine — never through Python.
    """

    def __init__(self, path):
        self.path = path
        self._listeners = []

    def on_change(self, callback):
        """Register listener for live preview updates."""
        self._listeners.append(callback)

    def notify_change(self):
        """Called after Inkscape modifies the file. Pushes update to live preview."""
        try:
            svg_str = self.read_string()
            for cb in self._listeners:
                try:
                    cb(svg_str)
                except Exception:
                    pass
        except Exception:
            pass

    def exists(self):
        return os.path.isfile(self.path)

    def read_string(self):
        """Read file as raw SVG string."""
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def read_tree(self):
        """Parse SVG from disk. Returns (root, tree)."""
        tree = etree.parse(self.path)
        return tree.getroot(), tree

    def get_dimensions(self):
        """Get canvas width/height."""
        root, _ = self.read_tree()
        w = root.get("width", "512")
        h = root.get("height", "512")
        try:
            w = int(float(w.replace("px", "").replace("mm", "")))
            h = int(float(h.replace("px", "").replace("mm", "")))
        except (ValueError, TypeError):
            w, h = 512, 512
        return w, h

    def get_state(self):
        """Return summary of current SVG file."""
        if not self.exists():
            return "No file loaded"
        root, _ = self.read_tree()
        w, h = self.get_dimensions()
        layers = []
        elements = 0
        for g in root.iter(f"{{{SVG_NS}}}g"):
            if g.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer":
                label = g.get(f"{{{INKSCAPE_NS}}}label", "unnamed")
                children = len(list(g))
                layers.append(f"  - '{label}' ({children} elements)")
                elements += children
        for child in root:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag not in ("g", "defs"):
                elements += 1

        state = f"Canvas: {w}x{h}\nFile: {self.path}\n"
        if layers:
            state += f"Layers ({len(layers)}):\n" + "\n".join(layers) + "\n"
        state += f"Total elements: {elements}"
        return state

    def get_elements_detail(self):
        """Return detailed info about every element in the SVG file."""
        if not self.exists():
            return "No file loaded"
        root, _ = self.read_tree()
        details = []
        skip_tags = {"svg", "defs", "stop", "feMergeNode", "feGaussianBlur",
                     "feOffset", "feFlood", "feComposite", "feMerge",
                     "linearGradient", "radialGradient", "clipPath", "filter",
                     "namedview"}
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            eid = elem.get("id", "")
            if not eid or tag in skip_tags:
                continue
            label = elem.get(f"{{{INKSCAPE_NS}}}label", "")
            style = elem.get("style", "")
            info = f"{tag} id={eid}"
            if label:
                info += f" label='{label}'"
            if tag == "rect":
                info += f" x={elem.get('x')} y={elem.get('y')} w={elem.get('width')} h={elem.get('height')}"
            elif tag == "circle":
                info += f" cx={elem.get('cx')} cy={elem.get('cy')} r={elem.get('r')}"
            elif tag == "ellipse":
                info += f" cx={elem.get('cx')} cy={elem.get('cy')} rx={elem.get('rx')} ry={elem.get('ry')}"
            elif tag == "path":
                d = elem.get("d", "")
                info += f" d='{d[:80]}{'...' if len(d) > 80 else ''}'"
            elif tag == "text":
                info += f" x={elem.get('x')} y={elem.get('y')} text='{(elem.text or '')[:40]}'"
            elif tag == "polygon":
                pts = elem.get("points", "")
                info += f" points='{pts[:60]}{'...' if len(pts) > 60 else ''}'"
            elif tag == "image":
                href = elem.get(f"{{{XLINK_NS}}}href", elem.get("href", ""))
                src = "[INLINE BASE64]" if href.startswith("data:") else f"src='{href}'"
                info += f" x={elem.get('x')} y={elem.get('y')} w={elem.get('width')} h={elem.get('height')} {src}"
            elif tag == "g":
                groupmode = elem.get(f"{{{INKSCAPE_NS}}}groupmode", "")
                if groupmode == "layer":
                    info += f" [LAYER] children={len(list(elem))}"
                else:
                    info += f" [GROUP] children={len(list(elem))}"
            if style:
                info += f" style='{style[:60]}{'...' if len(style) > 60 else ''}'"
            details.append(info)
        return "\n".join(details) if details else "File is empty"

    def find_element_id(self, tag_hint=None):
        """Find the last element ID, optionally filtered by tag. Useful after object-add."""
        root, _ = self.read_tree()
        last_id = None
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            eid = elem.get("id", "")
            if not eid:
                continue
            if tag_hint and tag != tag_hint:
                continue
            last_id = eid
        return last_id
