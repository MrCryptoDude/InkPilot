"""
Inkpilot — Context Builder
Extracts relevant SVG document state to send as context to Claude.
Keeps context concise to stay within token limits.
"""
import re
from typing import Optional
from lxml import etree

# Inkscape / SVG namespaces
NSMAP = {
    "svg": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}


def build_context(svg_root, selected_ids: list[str] = None, max_chars: int = 12000) -> str:
    """
    Build a concise context string describing the current document state.
    
    Args:
        svg_root: The root SVG element (lxml etree or inkex SVG)
        selected_ids: List of currently selected element IDs
        max_chars: Maximum characters for context string
    
    Returns:
        A structured context string for Claude
    """
    parts = []

    # --- Document Info ---
    width = svg_root.get("width", "unknown")
    height = svg_root.get("height", "unknown")
    viewbox = svg_root.get("viewBox", "not set")

    parts.append(f"[Document] size={width}x{height}, viewBox={viewbox}")

    # --- Layers ---
    layers = svg_root.findall(
        ".//svg:g[@inkscape:groupmode='layer']", namespaces=NSMAP
    )
    if layers:
        layer_info = []
        for layer in layers:
            label = layer.get(f"{{{NSMAP['inkscape']}}}label", "unnamed")
            style = layer.get("style", "")
            visible = "hidden" not in style
            locked = layer.get(f"{{{NSMAP['sodipodi']}}}insensitive", "false") == "true"
            child_count = len(list(layer))
            layer_info.append(
                f"  - '{label}' ({'visible' if visible else 'hidden'}"
                f"{', locked' if locked else ''}, {child_count} children)"
            )
        parts.append("[Layers]\n" + "\n".join(layer_info))

    # --- Selected Elements ---
    if selected_ids:
        parts.append(f"[Selected] {len(selected_ids)} element(s)")
        for sel_id in selected_ids[:5]:  # limit to 5
            elem = _find_by_id(svg_root, sel_id)
            if elem is not None:
                summary = _summarize_element(elem, include_svg=True)
                parts.append(f"  #{sel_id}: {summary}")
    else:
        parts.append("[Selected] nothing selected")

    # --- Element Summary (top-level non-layer groups and shapes) ---
    top_elements = _get_top_level_elements(svg_root)
    if top_elements:
        elem_lines = []
        for elem in top_elements[:20]:  # limit
            eid = elem.get("id", "no-id")
            elem_lines.append(f"  #{eid}: {_summarize_element(elem, include_svg=False)}")
        parts.append(f"[Elements] {len(top_elements)} top-level items\n" + "\n".join(elem_lines))

    # --- Defs (gradients, patterns, filters) ---
    defs = svg_root.find("svg:defs", namespaces=NSMAP)
    if defs is not None and len(defs):
        def_types = {}
        for child in defs:
            tag = _local_tag(child)
            def_types[tag] = def_types.get(tag, 0) + 1
        defs_str = ", ".join(f"{k}: {v}" for k, v in def_types.items())
        parts.append(f"[Defs] {defs_str}")

    context = "\n\n".join(parts)

    # Truncate if too long
    if len(context) > max_chars:
        context = context[:max_chars - 50] + "\n\n... [context truncated]"

    return context


def get_selected_svg(svg_root, selected_ids: list[str]) -> str:
    """Get the raw SVG of selected elements (for detailed operations)."""
    parts = []
    for sel_id in selected_ids[:5]:
        elem = _find_by_id(svg_root, sel_id)
        if elem is not None:
            svg_str = etree.tostring(elem, pretty_print=True).decode("utf-8")
            parts.append(f"<!-- #{sel_id} -->\n{svg_str}")
    return "\n".join(parts)


def _find_by_id(root, element_id: str):
    """Find element by ID in the SVG tree."""
    result = root.xpath(f'//*[@id="{element_id}"]')
    if result:
        return result[0]
    return None


def _get_top_level_elements(svg_root) -> list:
    """Get top-level visible elements (skip defs, metadata, etc.)."""
    skip_tags = {"defs", "metadata", "namedview", "title", "desc"}
    elements = []
    for child in svg_root:
        tag = _local_tag(child)
        if tag not in skip_tags:
            elements.append(child)
    return elements


def _summarize_element(elem, include_svg: bool = False) -> str:
    """Create a short summary of an SVG element."""
    tag = _local_tag(elem)
    attrs = {}

    # Common attributes
    for attr in ["x", "y", "width", "height", "cx", "cy", "r", "rx", "ry",
                 "d", "transform", "fill", "stroke"]:
        val = elem.get(attr)
        if val:
            # Truncate long path data
            if attr == "d" and len(val) > 80:
                val = val[:80] + "..."
            attrs[attr] = val

    # Inkscape label
    label = elem.get(f"{{{NSMAP['inkscape']}}}label")
    if label:
        attrs["label"] = label

    style = elem.get("style", "")
    if style:
        # Extract key style props
        fill_match = re.search(r"fill:\s*([^;]+)", style)
        stroke_match = re.search(r"stroke:\s*([^;]+)", style)
        if fill_match:
            attrs["fill"] = fill_match.group(1).strip()
        if stroke_match:
            attrs["stroke"] = stroke_match.group(1).strip()

    summary = f"<{tag}>"
    if attrs:
        attr_str = ", ".join(f"{k}={v}" for k, v in list(attrs.items())[:8])
        summary += f" [{attr_str}]"

    child_count = len(list(elem))
    if child_count > 0:
        summary += f" ({child_count} children)"

    if include_svg:
        try:
            svg_text = etree.tostring(elem, pretty_print=True).decode("utf-8")
            if len(svg_text) > 500:
                svg_text = svg_text[:500] + "\n... [truncated]"
            summary += f"\n    SVG:\n{svg_text}"
        except Exception:
            pass

    return summary


def _local_tag(elem) -> str:
    """Get the local tag name without namespace."""
    tag = elem.tag
    if "}" in tag:
        tag = tag.split("}")[1]
    return tag
