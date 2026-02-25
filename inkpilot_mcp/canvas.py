"""
Inkpilot MCP — SVG Canvas
Maintains an in-memory SVG document.
Notifies listeners on every change for live preview.
"""
from lxml import etree
import threading
import time
import os

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"
XLINK_NS = "http://www.w3.org/1999/xlink"

NSMAP = {
    None: SVG_NS,
    "inkscape": INKSCAPE_NS,
    "sodipodi": SODIPODI_NS,
    "xlink": XLINK_NS,
}

_counter = 0
_counter_lock = threading.Lock()


def _next_id(prefix="el"):
    global _counter
    with _counter_lock:
        _counter += 1
        return f"{prefix}_{_counter:04d}"


class SVGCanvas:
    """
    In-memory SVG canvas with change notifications.
    Every mutation triggers on_change callbacks for live preview.
    """

    def __init__(self, width=512, height=512):
        self.width = width
        self.height = height
        self.root = self._create_root(width, height)
        self.active_layer = None
        self._listeners = []
        self._lock = threading.Lock()

    def _create_root(self, w, h):
        root = etree.Element(f"{{{SVG_NS}}}svg", nsmap=NSMAP)
        root.set("width", str(w))
        root.set("height", str(h))
        root.set("viewBox", f"0 0 {w} {h}")
        root.set("version", "1.1")
        # Empty defs block (no background — Inkscape shows its own checkerboard)
        etree.SubElement(root, f"{{{SVG_NS}}}defs")
        return root

    def on_change(self, callback):
        """Register a listener called on every canvas mutation."""
        self._listeners.append(callback)

    def _notify(self):
        svg_str = self.to_svg()
        for cb in self._listeners:
            try:
                cb(svg_str)
            except Exception:
                pass

    def to_svg(self):
        """Return current SVG as string."""
        with self._lock:
            return etree.tostring(self.root, encoding="unicode", pretty_print=True)

    def save(self, path):
        """Save SVG to file."""
        with self._lock:
            tree = etree.ElementTree(self.root)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tree.write(path, xml_declaration=True, encoding="utf-8", pretty_print=True)
        return path

    def _get_parent(self):
        """Get current insertion point (active layer or root)."""
        if self.active_layer is not None:
            return self.active_layer
        return self.root

    def _find_layer(self, label):
        for g in self.root.iter(f"{{{SVG_NS}}}g"):
            if g.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer":
                if g.get(f"{{{INKSCAPE_NS}}}label") == label:
                    return g
        return None

    # ── Canvas Setup ─────────────────────────────────────────────

    def set_canvas(self, width, height):
        with self._lock:
            self.width = width
            self.height = height
            self.root.set("width", str(width))
            self.root.set("height", str(height))
            self.root.set("viewBox", f"0 0 {width} {height}")
        self._notify()
        return f"Canvas set to {width}x{height}"

    def reload_from_file(self, path):
        """Reload the canvas from an SVG file (after Inkscape modifies it)."""
        with self._lock:
            # Remember which layer was active
            old_layer_label = None
            if self.active_layer is not None:
                old_layer_label = self.active_layer.get(f"{{{INKSCAPE_NS}}}label")

            try:
                tree = etree.parse(path)
                new_root = tree.getroot()
                self.root = new_root
                # Update dimensions from the file
                w = new_root.get("width", str(self.width))
                h = new_root.get("height", str(self.height))
                try:
                    self.width = int(float(w.replace("px", "").replace("mm", "")))
                    self.height = int(float(h.replace("px", "").replace("mm", "")))
                except (ValueError, TypeError):
                    pass

                # Restore active layer by label (references are stale, re-find)
                self.active_layer = None
                if old_layer_label:
                    self.active_layer = self._find_layer(old_layer_label)

                # Sync ID counter to avoid collisions with Inkscape-generated IDs
                max_id = 0
                for elem in self.root.iter():
                    eid = elem.get("id", "")
                    # Parse numeric suffix from IDs like "path_0042" or "rect_0007"
                    parts = eid.rsplit("_", 1)
                    if len(parts) == 2:
                        try:
                            max_id = max(max_id, int(parts[1]))
                        except ValueError:
                            pass
                global _counter
                if max_id >= _counter:
                    _counter = max_id + 1

            except Exception as e:
                return f"Reload error: {e}"
        self._notify()
        layer_status = f" (layer: {old_layer_label})" if old_layer_label and self.active_layer else ""
        return f"Reloaded canvas{layer_status}"

    def clear(self):
        with self._lock:
            # Remove everything except defs
            to_remove = []
            for child in self.root:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "defs":
                    continue
                to_remove.append(child)
            for child in to_remove:
                self.root.remove(child)
            self.active_layer = None
        self._notify()
        return "Canvas cleared"

    # ── Layer Management ─────────────────────────────────────────

    def create_layer(self, label, visible=True, locked=False):
        with self._lock:
            existing = self._find_layer(label)
            if existing is not None:
                self.active_layer = existing
                return f"Layer '{label}' already exists, now active"

            layer_id = _next_id("layer")
            layer = etree.SubElement(self.root, f"{{{SVG_NS}}}g", id=layer_id)
            layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
            layer.set(f"{{{INKSCAPE_NS}}}label", label)
            if not visible:
                layer.set("style", "display:none")
            if locked:
                layer.set(f"{{{SODIPODI_NS}}}insensitive", "true")
            self.active_layer = layer
        self._notify()
        return f"Layer '{label}' created (id={layer_id})"

    def switch_layer(self, label):
        with self._lock:
            layer = self._find_layer(label)
            if layer is None:
                return f"Layer '{label}' not found"
            self.active_layer = layer
        return f"Switched to layer '{label}'"

    # ── Drawing Tools ────────────────────────────────────────────

    def draw_rect(self, x, y, width, height, fill="#ffffff", stroke=None,
                  stroke_width=None, rx=0, ry=0, opacity=None, id=None, label=None):
        with self._lock:
            eid = id or _next_id("rect")
            attrs = {"id": eid, "x": str(x), "y": str(y),
                     "width": str(width), "height": str(height)}
            if rx:
                attrs["rx"] = str(rx)
            if ry:
                attrs["ry"] = str(ry)

            style = f"fill:{fill}"
            if stroke:
                style += f";stroke:{stroke}"
            if stroke_width is not None:
                style += f";stroke-width:{stroke_width}"
            if opacity is not None:
                style += f";opacity:{opacity}"
            attrs["style"] = style

            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label

            elem = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}rect", **attrs)
        self._notify()
        return eid

    def draw_circle(self, cx, cy, r, fill="#ffffff", stroke=None,
                    stroke_width=None, opacity=None, id=None, label=None):
        with self._lock:
            eid = id or _next_id("circle")
            attrs = {"id": eid, "cx": str(cx), "cy": str(cy), "r": str(r)}
            style = f"fill:{fill}"
            if stroke:
                style += f";stroke:{stroke}"
            if stroke_width is not None:
                style += f";stroke-width:{stroke_width}"
            if opacity is not None:
                style += f";opacity:{opacity}"
            attrs["style"] = style
            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}circle", **attrs)
        self._notify()
        return eid

    def draw_ellipse(self, cx, cy, rx, ry, fill="#ffffff", stroke=None, id=None):
        with self._lock:
            eid = id or _next_id("ellipse")
            attrs = {"id": eid, "cx": str(cx), "cy": str(cy),
                     "rx": str(rx), "ry": str(ry)}
            style = f"fill:{fill}"
            if stroke:
                style += f";stroke:{stroke}"
            attrs["style"] = style
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}ellipse", **attrs)
        self._notify()
        return eid

    def draw_line(self, x1, y1, x2, y2, stroke="#ffffff", stroke_width=2, id=None):
        with self._lock:
            eid = id or _next_id("line")
            attrs = {"id": eid, "x1": str(x1), "y1": str(y1),
                     "x2": str(x2), "y2": str(y2),
                     "style": f"stroke:{stroke};stroke-width:{stroke_width}"}
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}line", **attrs)
        self._notify()
        return eid

    def draw_path(self, d, fill="none", stroke="#ffffff", stroke_width=1,
                  opacity=None, filter_id=None, clip_path_id=None,
                  id=None, label=None):
        with self._lock:
            eid = id or _next_id("path")
            style = f"fill:{fill};stroke:{stroke};stroke-width:{stroke_width}"
            if opacity is not None:
                style += f";opacity:{opacity}"
            if filter_id:
                style += f";filter:url(#{filter_id})"
            if clip_path_id:
                style += f";clip-path:url(#{clip_path_id})"
            attrs = {"id": eid, "d": d, "style": style}
            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}path", **attrs)
        self._notify()
        return eid

    def draw_text(self, x, y, content, font_size=16, fill="#ffffff",
                  font_family="sans-serif", id=None):
        with self._lock:
            eid = id or _next_id("text")
            attrs = {"id": eid, "x": str(x), "y": str(y),
                     "style": f"font-size:{font_size}px;fill:{fill};font-family:{font_family}"}
            elem = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}text", **attrs)
            elem.text = content
        self._notify()
        return eid

    def draw_polygon(self, points, fill="#ffffff", stroke=None, id=None):
        with self._lock:
            eid = id or _next_id("polygon")
            style = f"fill:{fill}"
            if stroke:
                style += f";stroke:{stroke}"
            attrs = {"id": eid, "points": points, "style": style}
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}polygon", **attrs)
        self._notify()
        return eid

    # ── Pixel Art ────────────────────────────────────────────────

    def draw_pixel(self, x, y, color, size=8):
        """Draw a single pixel. For live drawing effect."""
        with self._lock:
            eid = _next_id("px")
            attrs = {"id": eid,
                     "x": str(x * size), "y": str(y * size),
                     "width": str(size), "height": str(size),
                     "style": f"fill:{color}"}
            etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}rect", **attrs)
        self._notify()
        return eid

    def draw_pixel_row(self, y, colors, size=8, start_x=0):
        """
        Draw an entire row of pixels at once.
        colors: list of color strings (null/None = transparent/skip)
        Creates a nice 'scanning' effect when called row by row.
        """
        ids = []
        with self._lock:
            for x, color in enumerate(colors):
                if color is None or color == "null" or color == "":
                    continue
                eid = _next_id("px")
                attrs = {"id": eid,
                         "x": str((start_x + x) * size),
                         "y": str(y * size),
                         "width": str(size), "height": str(size),
                         "style": f"fill:{color}"}
                etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}rect", **attrs)
                ids.append(eid)
        self._notify()
        return ids

    def draw_pixel_region(self, pixels, size=8, offset_x=0, offset_y=0, label=None):
        """
        Draw a batch of pixels as a named group.
        pixels: list of [x, y, color] triples
        Great for drawing body parts: hilt, blade, etc.
        """
        ids = []
        with self._lock:
            group = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}g",
                                     id=_next_id("region"))
            if label:
                group.set(f"{{{INKSCAPE_NS}}}label", label)
            for px in pixels:
                x, y, color = px[0], px[1], px[2]
                if color is None or color == "null" or color == "":
                    continue
                eid = _next_id("px")
                attrs = {"id": eid,
                         "x": str((offset_x + x) * size),
                         "y": str((offset_y + y) * size),
                         "width": str(size), "height": str(size),
                         "style": f"fill:{color}"}
                etree.SubElement(group, f"{{{SVG_NS}}}rect", **attrs)
                ids.append(eid)
        self._notify()
        return f"Drew {len(ids)} pixels" + (f" ({label})" if label else "")

    # ── Image Embedding ───────────────────────────────────────────

    def embed_image(self, image_path, x=0, y=0, width=None, height=None, label=None):
        """Embed a raster image (PNG/JPG/etc) into the SVG as a linked <image> element.
        Uses absolute file path so Inkscape can find it for tracing.
        If width/height not given, uses the canvas dimensions."""
        from pathlib import Path
        with self._lock:
            eid = _next_id("img")
            attrs = {
                "id": eid,
                "x": str(x),
                "y": str(y),
                "width": str(width or self.width),
                "height": str(height or self.height),
            }
            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label

            elem = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}image", **attrs)
            # Convert to file URI for cross-platform SVG compatibility
            file_uri = Path(image_path).as_uri()  # file:///C:/path/to/img.png
            elem.set(f"{{{XLINK_NS}}}href", file_uri)
            elem.set("href", file_uri)
        self._notify()
        return eid

    def embed_image_base64(self, data_uri, x=0, y=0, width=None, height=None, label=None):
        """Embed a raster image from a base64 data URI into the SVG.
        data_uri should be like 'data:image/png;base64,iVBOR...' 
        This inlines the image so no external file needed."""
        with self._lock:
            eid = _next_id("img")
            attrs = {
                "id": eid,
                "x": str(x),
                "y": str(y),
                "width": str(width or self.width),
                "height": str(height or self.height),
            }
            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label

            elem = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}image", **attrs)
            elem.set(f"{{{XLINK_NS}}}href", data_uri)
            elem.set("href", data_uri)
        self._notify()
        return eid

    # ── Advanced SVG Features ────────────────────────────────────

    def add_gradient(self, gradient_id, colors, x1="0%", y1="0%", x2="0%", y2="100%", gradient_type="linear"):
        """
        Add a gradient to defs. Returns the gradient ID for use as fill="url(#id)".
        colors: list of (offset, color) tuples, e.g. [("0%", "#ff0000"), ("100%", "#0000ff")]
        gradient_type: 'linear' or 'radial'
        """
        with self._lock:
            defs = self.root.find(f"{{{SVG_NS}}}defs")
            if defs is None:
                defs = etree.SubElement(self.root, f"{{{SVG_NS}}}defs")
                self.root.insert(0, defs)

            if gradient_type == "radial":
                grad = etree.SubElement(defs, f"{{{SVG_NS}}}radialGradient", id=gradient_id)
                grad.set("cx", x1); grad.set("cy", y1)
                grad.set("r", x2)  # reuse x2 as radius
            else:
                grad = etree.SubElement(defs, f"{{{SVG_NS}}}linearGradient", id=gradient_id)
                grad.set("x1", x1); grad.set("y1", y1)
                grad.set("x2", x2); grad.set("y2", y2)

            for offset, color in colors:
                stop = etree.SubElement(grad, f"{{{SVG_NS}}}stop")
                stop.set("offset", str(offset))
                # Handle opacity in color
                if len(color) > 7:  # e.g. #ff000080
                    stop.set("style", f"stop-color:{color[:7]};stop-opacity:{int(color[7:9], 16)/255:.2f}")
                else:
                    stop.set("style", f"stop-color:{color};stop-opacity:1")

        self._notify()
        return gradient_id

    def add_filter(self, filter_id, blur_std=None, shadow_dx=None, shadow_dy=None,
                   shadow_blur=None, shadow_color=None):
        """
        Add a filter to defs. Returns filter ID for use as filter="url(#id)".
        Supports gaussian blur and drop shadow.
        """
        with self._lock:
            defs = self.root.find(f"{{{SVG_NS}}}defs")
            if defs is None:
                defs = etree.SubElement(self.root, f"{{{SVG_NS}}}defs")
                self.root.insert(0, defs)

            filt = etree.SubElement(defs, f"{{{SVG_NS}}}filter", id=filter_id)
            filt.set("x", "-20%"); filt.set("y", "-20%")
            filt.set("width", "140%"); filt.set("height", "140%")

            if blur_std is not None:
                blur = etree.SubElement(filt, f"{{{SVG_NS}}}feGaussianBlur")
                blur.set("in", "SourceGraphic")
                blur.set("stdDeviation", str(blur_std))
                if shadow_dx is None:
                    blur.set("result", "blur")

            if shadow_dx is not None:
                # Drop shadow: blur → offset → merge with original
                blur_s = etree.SubElement(filt, f"{{{SVG_NS}}}feGaussianBlur")
                blur_s.set("in", "SourceAlpha")
                blur_s.set("stdDeviation", str(shadow_blur or 3))
                blur_s.set("result", "shadow_blur")

                offset = etree.SubElement(filt, f"{{{SVG_NS}}}feOffset")
                offset.set("in", "shadow_blur")
                offset.set("dx", str(shadow_dx or 2))
                offset.set("dy", str(shadow_dy or 2))
                offset.set("result", "shadow_offset")

                if shadow_color:
                    flood = etree.SubElement(filt, f"{{{SVG_NS}}}feFlood")
                    flood.set("flood-color", shadow_color)
                    flood.set("flood-opacity", "0.5")
                    flood.set("result", "shadow_color")
                    comp = etree.SubElement(filt, f"{{{SVG_NS}}}feComposite")
                    comp.set("in", "shadow_color"); comp.set("in2", "shadow_offset")
                    comp.set("operator", "in"); comp.set("result", "colored_shadow")
                    merge = etree.SubElement(filt, f"{{{SVG_NS}}}feMerge")
                    etree.SubElement(merge, f"{{{SVG_NS}}}feMergeNode").set("in", "colored_shadow")
                    etree.SubElement(merge, f"{{{SVG_NS}}}feMergeNode").set("in", "SourceGraphic")
                else:
                    merge = etree.SubElement(filt, f"{{{SVG_NS}}}feMerge")
                    etree.SubElement(merge, f"{{{SVG_NS}}}feMergeNode").set("in", "shadow_offset")
                    etree.SubElement(merge, f"{{{SVG_NS}}}feMergeNode").set("in", "SourceGraphic")

        self._notify()
        return filter_id

    def add_clip_path(self, clip_id, shape_d):
        """Add a clip path to defs. shape_d is an SVG path 'd' attribute."""
        with self._lock:
            defs = self.root.find(f"{{{SVG_NS}}}defs")
            if defs is None:
                defs = etree.SubElement(self.root, f"{{{SVG_NS}}}defs")
                self.root.insert(0, defs)

            clip = etree.SubElement(defs, f"{{{SVG_NS}}}clipPath", id=clip_id)
            path = etree.SubElement(clip, f"{{{SVG_NS}}}path")
            path.set("d", shape_d)

        self._notify()
        return clip_id

    # ── Grouping & Transforms ────────────────────────────────────

    def create_group(self, label=None, id=None):
        with self._lock:
            gid = id or _next_id("group")
            attrs = {"id": gid}
            if label:
                attrs[f"{{{INKSCAPE_NS}}}label"] = label
            group = etree.SubElement(self._get_parent(), f"{{{SVG_NS}}}g", **attrs)
        self._notify()
        return gid

    def insert_svg(self, svg_fragment):
        """Insert raw SVG markup."""
        with self._lock:
            # Wrap in SVG root for parsing
            wrapped = f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INKSCAPE_NS}">{svg_fragment}</svg>'
            try:
                parsed = etree.fromstring(wrapped.encode("utf-8"))
                ids = []
                for child in parsed:
                    self._get_parent().append(child)
                    cid = child.get("id", "")
                    if cid:
                        ids.append(cid)
                self._notify()
                return f"Inserted {len(ids)} element(s)"
            except etree.XMLSyntaxError as e:
                return f"SVG parse error: {e}"

    def delete_element(self, element_id):
        with self._lock:
            for elem in self.root.iter():
                if elem.get("id") == element_id:
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
                        self._notify()
                        return f"Deleted {element_id}"
            return f"Element {element_id} not found"

    # ── State Query ──────────────────────────────────────────────

    def get_state(self):
        """Return a summary of the current canvas state."""
        layers = []
        elements = 0
        for g in self.root.iter(f"{{{SVG_NS}}}g"):
            if g.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer":
                label = g.get(f"{{{INKSCAPE_NS}}}label", "unnamed")
                children = len(list(g))
                layers.append(f"  - '{label}' ({children} elements)")
                elements += children

        for child in self.root:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            cid = child.get("id", "")
            if tag != "g" and tag != "defs":
                elements += 1

        active = None
        if self.active_layer is not None:
            active = self.active_layer.get(f"{{{INKSCAPE_NS}}}label", "unknown")

        state = f"Canvas: {self.width}x{self.height}\n"
        if layers:
            state += f"Layers ({len(layers)}):\n" + "\n".join(layers) + "\n"
        state += f"Active layer: {active or 'root'}\n"
        state += f"Total elements: {elements}"
        return state

    def get_elements_detail(self):
        """Return detailed info about every element on the canvas.
        Gives Claude visibility into positions, sizes, colors, and paths."""
        details = []
        for elem in self.root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            eid = elem.get("id", "")
            if not eid or tag in ("svg", "defs", "stop", "feMergeNode",
                                   "feGaussianBlur", "feOffset", "feFlood",
                                   "feComposite", "feMerge"):
                continue

            label = elem.get(f"{{{INKSCAPE_NS}}}label", "")
            style = elem.get("style", "")

            info = f"{tag} id={eid}"
            if label:
                info += f" label='{label}'"

            # Position/size info per element type
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
                if href.startswith("data:"):
                    info += f" x={elem.get('x')} y={elem.get('y')} w={elem.get('width')} h={elem.get('height')} [INLINE BASE64]"
                else:
                    info += f" x={elem.get('x')} y={elem.get('y')} w={elem.get('width')} h={elem.get('height')} src='{href}'"
            elif tag == "g":
                groupmode = elem.get(f"{{{INKSCAPE_NS}}}groupmode", "")
                if groupmode == "layer":
                    info += f" [LAYER] children={len(list(elem))}"
                else:
                    info += f" [GROUP] children={len(list(elem))}"

            if style:
                info += f" style='{style[:60]}{'...' if len(style) > 60 else ''}'"

            details.append(info)

        return "\n".join(details) if details else "Canvas is empty"
