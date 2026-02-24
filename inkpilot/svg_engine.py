"""
Inkpilot — SVG Engine
Executes commands and inserts SVG into the Inkscape document.
This is the bridge between Claude's output and Inkscape's SVG DOM.
"""
import re
import copy
from lxml import etree
from typing import Optional

try:
    import inkex
    from inkex import NSS
    HAS_INKEX = True
except ImportError:
    HAS_INKEX = False
    NSS = {}

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
XLINK_NS = "http://www.w3.org/1999/xlink"

NSMAP = {
    None: SVG_NS,
    "inkscape": INKSCAPE_NS,
    "xlink": XLINK_NS,
}

# Counter for unique IDs
_id_counter = 0


def _next_id(prefix: str = "inkpilot") -> str:
    global _id_counter
    _id_counter += 1
    return f"{prefix}_{_id_counter:04d}"


class SVGEngine:
    """
    Executes Inkpilot commands on an SVG document.
    
    Can work with:
    - An inkex SVG object (when running inside Inkscape)
    - A standalone lxml etree (for testing / CLI usage)
    """

    def __init__(self, svg_root):
        self.root = svg_root
        self.created_ids: list[str] = []
        self._active_layer = None  # set by set_layer command

    def insert_svg_fragment(self, svg_str: str, parent=None) -> list[str]:
        """
        Parse and insert an SVG fragment into the document.
        Returns list of IDs of inserted top-level elements.
        """
        if parent is None:
            parent = self._get_current_layer()

        # Wrap to make it parseable
        wrapper = (
            f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INKSCAPE_NS}" '
            f'xmlns:xlink="{XLINK_NS}" '
            f'xmlns:inkpilot="http://inkpilot.dev/ns">{svg_str}</svg>'
        )

        try:
            parsed = etree.fromstring(wrapper.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Invalid SVG fragment: {e}")

        inserted_ids = []
        for child in parsed:
            # Ensure unique ID
            elem_id = child.get("id")
            if not elem_id or self._id_exists(elem_id):
                elem_id = _next_id()
                child.set("id", elem_id)

            # Recursively fix child IDs too
            self._ensure_unique_ids(child)

            parent.append(child)
            inserted_ids.append(elem_id)
            self.created_ids.append(elem_id)

        return inserted_ids

    def execute_command(self, cmd: dict) -> Optional[str]:
        """
        Execute a single Inkpilot command.
        Returns the ID of any created element, or None.
        """
        action = cmd.get("action", "")
        handler = getattr(self, f"_cmd_{action}", None)

        if handler is None:
            raise ValueError(f"Unknown command action: '{action}'")

        return handler(cmd)

    def execute_commands(self, commands: list[dict]) -> list[str]:
        """Execute a list of commands. Returns list of created element IDs."""
        results = []
        for cmd in commands:
            try:
                result = self.execute_command(cmd)
                if result:
                    results.append(result)
            except Exception as e:
                results.append(f"ERROR: {e}")
        return results

    # ── Shape Creation Commands ──────────────────────────────────

    def _cmd_rect(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("rect"))
        elem = self._make_element("rect", elem_id)
        for attr in ["x", "y", "width", "height", "rx", "ry"]:
            if attr in cmd:
                elem.set(attr, str(cmd[attr]))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_circle(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("circle"))
        elem = self._make_element("circle", elem_id)
        for attr in ["cx", "cy", "r"]:
            if attr in cmd:
                elem.set(attr, str(cmd[attr]))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_ellipse(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("ellipse"))
        elem = self._make_element("ellipse", elem_id)
        for attr in ["cx", "cy", "rx", "ry"]:
            if attr in cmd:
                elem.set(attr, str(cmd[attr]))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_line(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("line"))
        elem = self._make_element("line", elem_id)
        for attr in ["x1", "y1", "x2", "y2"]:
            if attr in cmd:
                elem.set(attr, str(cmd[attr]))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_path(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("path"))
        elem = self._make_element("path", elem_id)
        elem.set("d", cmd.get("d", ""))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_polygon(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("polygon"))
        elem = self._make_element("polygon", elem_id)
        elem.set("points", cmd.get("points", ""))
        self._apply_style_attrs(elem, cmd)
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    def _cmd_text(self, cmd: dict) -> str:
        elem_id = cmd.get("id", _next_id("text"))
        elem = self._make_element("text", elem_id)
        elem.set("x", str(cmd.get("x", 0)))
        elem.set("y", str(cmd.get("y", 0)))
        elem.text = cmd.get("content", "")

        style_parts = []
        if "font_size" in cmd:
            style_parts.append(f"font-size:{cmd['font_size']}px")
        if "font_family" in cmd:
            style_parts.append(f"font-family:{cmd['font_family']}")
        if "fill" in cmd:
            style_parts.append(f"fill:{cmd['fill']}")
        if style_parts:
            existing = elem.get("style", "")
            elem.set("style", ";".join(style_parts) + (";" + existing if existing else ""))

        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    # ── Pixel Art Commands ───────────────────────────────────────

    def _cmd_pixel_grid(self, cmd: dict) -> str:
        """Create pixel art from a 2D array of colors."""
        group_id = cmd.get("id", _next_id("pixels"))
        group = self._make_element("g", group_id)
        group.set(f"{{{INKSCAPE_NS}}}label", cmd.get("label", "pixel_art"))

        ox = cmd.get("x", 0)
        oy = cmd.get("y", 0)
        pixel_size = cmd.get("pixel_size", 4)
        pixels = cmd.get("pixels", [])

        for row_idx, row in enumerate(pixels):
            for col_idx, color in enumerate(row):
                if color is None or color == "" or color == "transparent":
                    continue
                rect = etree.SubElement(group, f"{{{SVG_NS}}}rect")
                rect.set("x", str(ox + col_idx * pixel_size))
                rect.set("y", str(oy + row_idx * pixel_size))
                rect.set("width", str(pixel_size))
                rect.set("height", str(pixel_size))
                rect.set("style", f"fill:{color};stroke:none")

        self._get_current_layer().append(group)
        self.created_ids.append(group_id)
        return group_id

    def _cmd_pixel_rect(self, cmd: dict) -> str:
        """Single colored pixel block."""
        elem_id = cmd.get("id", _next_id("pxrect"))
        pixel_size = cmd.get("pixel_size", 4)
        elem = self._make_element("rect", elem_id)
        elem.set("x", str(cmd.get("x", 0)))
        elem.set("y", str(cmd.get("y", 0)))
        elem.set("width", str(cmd.get("w", 1) * pixel_size))
        elem.set("height", str(cmd.get("h", 1) * pixel_size))
        elem.set("style", f"fill:{cmd.get('color', '#000')};stroke:none")
        self._get_current_layer().append(elem)
        self.created_ids.append(elem_id)
        return elem_id

    # ── Grouping & Layer Commands ────────────────────────────────

    def _cmd_group(self, cmd: dict) -> str:
        group_id = cmd.get("id", _next_id("group"))
        group = self._make_element("g", group_id)
        if "label" in cmd:
            group.set(f"{{{INKSCAPE_NS}}}label", cmd["label"])

        # Move children into group
        children_ids = cmd.get("children", [])
        for child_id in children_ids:
            child = self._find_by_id(child_id)
            if child is not None:
                group.append(child)  # moves from current parent

        self._get_current_layer().append(group)
        self.created_ids.append(group_id)
        return group_id

    def _cmd_layer(self, cmd: dict) -> str:
        layer_id = cmd.get("id", _next_id("layer"))
        label = cmd.get("label", "New Layer")

        # Check if layer already exists
        existing = self._find_layer_by_label(label)
        if existing is not None:
            return existing.get("id", layer_id)

        layer = self._make_element("g", layer_id)
        layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
        layer.set(f"{{{INKSCAPE_NS}}}label", label)

        if not cmd.get("visible", True):
            layer.set("style", "display:none")
        if cmd.get("locked", False):
            layer.set(
                "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd}insensitive",
                "true"
            )

        self.root.append(layer)
        self.created_ids.append(layer_id)
        return layer_id

    def _cmd_set_layer(self, cmd: dict) -> Optional[str]:
        """Switch active layer — subsequent elements go into this layer."""
        label = cmd.get("label", "")
        layer = self._find_layer_by_label(label)
        if layer is not None:
            self._active_layer = layer
            return layer.get("id")
        # If not found, create it
        return self._cmd_layer({"label": label})

    def _cmd_layer_visibility(self, cmd: dict) -> Optional[str]:
        """Toggle layer visibility."""
        label = cmd.get("label", "")
        layer = self._find_layer_by_label(label)
        if layer is None:
            return None
        visible = cmd.get("visible", True)
        style = layer.get("style", "")
        if visible:
            style = style.replace("display:none", "").strip(";")
        else:
            if "display:none" not in style:
                style = f"display:none;{style}" if style else "display:none"
        layer.set("style", style)
        return layer.get("id")

    def _cmd_layer_lock(self, cmd: dict) -> Optional[str]:
        """Toggle layer lock."""
        label = cmd.get("label", "")
        layer = self._find_layer_by_label(label)
        if layer is None:
            return None
        locked = cmd.get("locked", False)
        ns = "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd}insensitive"
        if locked:
            layer.set(ns, "true")
        else:
            if ns in layer.attrib:
                del layer.attrib[ns]
        return layer.get("id")

    def _cmd_layer_order(self, cmd: dict) -> Optional[str]:
        """Change layer stacking order."""
        label = cmd.get("label", "")
        layer = self._find_layer_by_label(label)
        if layer is None or layer.getparent() is None:
            return None
        parent = layer.getparent()
        siblings = list(parent)
        idx = siblings.index(layer)
        position = cmd.get("position", "top")

        parent.remove(layer)
        if position == "top":
            parent.append(layer)
        elif position == "bottom":
            parent.insert(0, layer)
        elif position == "up" and idx < len(siblings) - 1:
            parent.insert(idx + 1, layer)
        elif position == "down" and idx > 0:
            parent.insert(idx - 1, layer)
        else:
            parent.append(layer)
        return layer.get("id")

    # ── Transform Commands ───────────────────────────────────────

    def _cmd_translate(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is None:
            return None
        x, y = cmd.get("x", 0), cmd.get("y", 0)
        existing = target.get("transform", "")
        target.set("transform", f"{existing} translate({x},{y})".strip())
        return cmd["target"]

    def _cmd_rotate(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is None:
            return None
        angle = cmd.get("angle", 0)
        cx = cmd.get("cx", 0)
        cy = cmd.get("cy", 0)
        existing = target.get("transform", "")
        target.set("transform", f"{existing} rotate({angle},{cx},{cy})".strip())
        return cmd["target"]

    def _cmd_scale(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is None:
            return None
        sx = cmd.get("sx", 1)
        sy = cmd.get("sy", sx)
        existing = target.get("transform", "")
        target.set("transform", f"{existing} scale({sx},{sy})".strip())
        return cmd["target"]

    # ── Style Commands ───────────────────────────────────────────

    def _cmd_set_style(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is None:
            return None
        self._apply_style_attrs(target, cmd)
        return cmd["target"]

    def _cmd_gradient(self, cmd: dict) -> str:
        """Create a gradient definition."""
        grad_id = cmd.get("id", _next_id("gradient"))
        defs = self._ensure_defs()

        grad_type = cmd.get("type", "linear")
        if grad_type == "radial":
            grad = etree.SubElement(defs, f"{{{SVG_NS}}}radialGradient")
        else:
            grad = etree.SubElement(defs, f"{{{SVG_NS}}}linearGradient")

        grad.set("id", grad_id)

        for stop_data in cmd.get("stops", []):
            stop = etree.SubElement(grad, f"{{{SVG_NS}}}stop")
            stop.set("offset", str(stop_data.get("offset", "0%")))
            stop.set("style", f"stop-color:{stop_data.get('color', '#000')};stop-opacity:{stop_data.get('opacity', 1)}")

        return grad_id

    # ── Document Commands ────────────────────────────────────────

    def _cmd_set_canvas(self, cmd: dict) -> None:
        w = cmd.get("width", 1024)
        h = cmd.get("height", 1024)
        self.root.set("width", f"{w}")
        self.root.set("height", f"{h}")
        self.root.set("viewBox", f"0 0 {w} {h}")

    # ── Selection Modification Commands ──────────────────────────

    def _cmd_delete(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is not None and target.getparent() is not None:
            target.getparent().remove(target)
            return cmd["target"]
        return None

    def _cmd_duplicate(self, cmd: dict) -> Optional[str]:
        target = self._find_by_id(cmd["target"])
        if target is None:
            return None
        dup = copy.deepcopy(target)
        new_id = cmd.get("new_id", _next_id("dup"))
        dup.set("id", new_id)
        target.getparent().append(dup)
        self.created_ids.append(new_id)
        return new_id

    # ── Sprite Sheet Commands ────────────────────────────────────

    def _cmd_sprite_sheet_grid(self, cmd: dict) -> str:
        """Create a grid of sprite frame boundaries (as rects with no fill)."""
        group_id = _next_id("spritesheet")
        group = self._make_element("g", group_id)
        group.set(f"{{{INKSCAPE_NS}}}label", "sprite_sheet_grid")

        cols = cmd.get("columns", 4)
        rows = cmd.get("rows", 2)
        cw = cmd.get("cell_width", 64)
        ch = cmd.get("cell_height", 64)
        pad = cmd.get("padding", 2)

        for r in range(rows):
            for c in range(cols):
                frame = etree.SubElement(group, f"{{{SVG_NS}}}rect")
                frame_id = f"frame_{r}_{c}"
                frame.set("id", frame_id)
                frame.set("x", str(c * (cw + pad)))
                frame.set("y", str(r * (ch + pad)))
                frame.set("width", str(cw))
                frame.set("height", str(ch))
                frame.set("style", "fill:none;stroke:#666;stroke-width:0.5;stroke-dasharray:2,2")
                frame.set(f"{{{INKSCAPE_NS}}}label", f"frame_{r * cols + c}")

        self._get_current_layer().append(group)
        self.created_ids.append(group_id)
        return group_id

    # ── Helper Methods ───────────────────────────────────────────

    def _make_element(self, tag: str, elem_id: str):
        elem = etree.Element(f"{{{SVG_NS}}}{tag}")
        elem.set("id", elem_id)
        return elem

    def _find_by_id(self, element_id: str):
        results = self.root.xpath(f'//*[@id="{element_id}"]')
        return results[0] if results else None

    def _id_exists(self, element_id: str) -> bool:
        return self._find_by_id(element_id) is not None

    def _ensure_unique_ids(self, elem):
        """Recursively ensure all IDs in a subtree are unique."""
        for child in elem.iter():
            cid = child.get("id")
            if cid and self._id_exists(cid):
                new_id = _next_id()
                child.set("id", new_id)

    def _get_current_layer(self):
        """Get the current/active layer, or root if none."""
        # If a layer was explicitly set via set_layer, use it
        if self._active_layer is not None:
            return self._active_layer

        # Otherwise find the first visible unlocked layer, or root
        layers = self.root.findall(
            f".//{{{SVG_NS}}}g[@{{{INKSCAPE_NS}}}groupmode='layer']"
        )
        for layer in layers:
            style = layer.get("style", "")
            if "display:none" not in style:
                locked = layer.get(
                    "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd}insensitive",
                    "false"
                )
                if locked != "true":
                    return layer
        return self.root

    def _find_layer_by_label(self, label: str):
        """Find a layer by its inkscape:label."""
        layers = self.root.findall(
            f".//{{{SVG_NS}}}g[@{{{INKSCAPE_NS}}}groupmode='layer']"
        )
        for layer in layers:
            layer_label = layer.get(f"{{{INKSCAPE_NS}}}label", "")
            if layer_label == label:
                return layer
        return None

    def _apply_style_attrs(self, elem, cmd: dict):
        """Apply common style attributes from a command dict."""
        style_parts = []
        if "fill" in cmd:
            style_parts.append(f"fill:{cmd['fill']}")
        if "stroke" in cmd:
            style_parts.append(f"stroke:{cmd['stroke']}")
        if "stroke_width" in cmd:
            style_parts.append(f"stroke-width:{cmd['stroke_width']}")
        if "opacity" in cmd:
            style_parts.append(f"opacity:{cmd['opacity']}")
        if style_parts:
            existing = elem.get("style", "")
            new_style = ";".join(style_parts)
            if existing:
                elem.set("style", f"{existing};{new_style}")
            else:
                elem.set("style", new_style)

    def _ensure_defs(self):
        """Get or create the <defs> element."""
        defs = self.root.find(f"{{{SVG_NS}}}defs")
        if defs is None:
            defs = etree.SubElement(self.root, f"{{{SVG_NS}}}defs")
        return defs
