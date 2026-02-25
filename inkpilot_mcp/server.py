"""
Inkpilot MCP Server
Bridge between Claude and Inkscape.

Live drawing: browser preview via SSE (instant updates)
Final result: open in Inkscape for editing
Config: ~/.inkpilot/config.json controls live_preview on/off
"""
import sys
import os
import json
import time
import threading
import webbrowser

from mcp.server.fastmcp import FastMCP

from .canvas import SVGCanvas
from .live_server import LiveServer
from .inkscape import open_in_inkscape, find_inkscape, run_inkscape_actions

# ── Paths ────────────────────────────────────────────────────────

def _home():
    return os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or os.path.expanduser("~")

WORK_DIR = os.path.join(_home(), ".inkpilot")
WORK_FILE = os.path.join(WORK_DIR, "canvas.svg")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
CONFIG_FILE = os.path.join(WORK_DIR, "config.json")

os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Config ───────────────────────────────────────────────────────

def _load_config():
    """Read config.json. Tray app writes this, we just read."""
    defaults = {"live_preview": True}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return {**defaults, **data}
    except Exception:
        pass
    return defaults

# ── State ────────────────────────────────────────────────────────

canvas = SVGCanvas(512, 512)

def _open_inkscape_callback():
    """Callback for live preview's 'Open in Inkscape' button."""
    from .inkscape import open_in_inkscape as _open
    _do_save()  # Ensure file is on disk
    return _open(WORK_FILE)

live = LiveServer(canvas, port=7878, open_inkscape_fn=_open_inkscape_callback)
mcp = FastMCP("inkpilot")
_live_started = False


def _ensure_live_server():
    """Start the SSE server (always runs for manual access).
    Only auto-opens the browser if live_preview is ON."""
    global _live_started
    if not _live_started:
        url = live.start()
        _live_started = True

        # Read config at the moment of first draw (fresh read each session)
        config = _load_config()
        if config.get("live_preview", True):
            webbrowser.open(url)
            return f"Live preview: {url}"
        else:
            return f"Live preview available at {url} (auto-open disabled)"
    return None


# ── Debounced Save ───────────────────────────────────────────────

_save_timer = None
_save_lock = threading.Lock()


def _save_to_disk():
    """Debounced save — batches rapid operations (0.15s delay).
    Live preview updates instantly via SSE; disk write is deferred."""
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.15, _do_save)
        _save_timer.daemon = True
        _save_timer.start()


def _save_to_disk_now():
    """Immediate save — use before Inkscape actions that read from disk."""
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None
    _do_save()


def _do_save():
    """Actual disk write."""
    canvas.save(WORK_FILE)


# ── Tools ────────────────────────────────────────────────────────

@mcp.tool()
def inkpilot_setup_canvas(width: int = 512, height: int = 512) -> str:
    """ALWAYS call this first. Sets up the canvas and opens Inkscape with the working file.
    For a 32x32 sprite at pixel size 8, use width=256, height=256.
    For a 16x16 sprite at pixel size 16, use width=256, height=256.
    
    WORKFLOW: Draw shapes (circles, rects, paths) → use inkpilot_inkscape_action for
    boolean ops (union, difference), smoothing, alignment, and 200+ filters.
    Use inkpilot_read_canvas frequently to inspect your work and make corrections."""
    canvas.clear()
    result = canvas.set_canvas(width, height)
    _save_to_disk_now()

    live_msg = _ensure_live_server()
    if live_msg:
        result += f"\n{live_msg}"
    
    # Auto-open Inkscape (singleton — won't open duplicates)
    ink_msg = open_in_inkscape(WORK_FILE)
    result += f"\n{ink_msg}"
    result += f"\nWorking file: {WORK_FILE}"
    return result


@mcp.tool()
def inkpilot_create_layer(label: str) -> str:
    """Create a named layer and make it active. Use layers for organization:
    Shadow, Background, Body, Weapons, Effects, UI, etc.
    All subsequent draws go into this layer."""
    result = canvas.create_layer(label)
    _save_to_disk()
    return result


@mcp.tool()
def inkpilot_switch_layer(label: str) -> str:
    """Switch to an existing layer by name."""
    result = canvas.switch_layer(label)
    _save_to_disk()
    return result


@mcp.tool()
def inkpilot_draw_pixel_region(
    pixels: list,
    size: int = 8,
    offset_x: int = 0,
    offset_y: int = 0,
    label: str = None,
) -> str:
    """Draw a batch of pixels as a group. Best for pixel art style graphics.
    Each pixel: [x, y, "#hexcolor"]. Null color = transparent (skip).
    
    size = pixel size in SVG units. size=8 means each logical pixel is 8x8 SVG units.
    offset_x/offset_y = shift the entire region (in pixel coordinates).
    label = name for this group (e.g. "sword_blade", "helmet_outline").
    
    For live animation effect: draw parts separately — outline, then fill, 
    then highlights, then shadow. Each call updates Inkscape!
    
    Example: [[0,0,"#8B4513"], [1,0,"#A0522D"], [0,1,"#6B3410"]]"""
    result = canvas.draw_pixel_region(
        pixels=pixels, size=size,
        offset_x=offset_x, offset_y=offset_y, label=label,
    )
    _save_to_disk()
    return result


@mcp.tool()
def inkpilot_draw_pixel_row(y: int, colors: list, size: int = 8, start_x: int = 0) -> str:
    """Draw one row of pixels. Colors array: ["#ff0000", null, "#00ff00", ...].
    Null = transparent. Creates a scanline effect when called row by row."""
    ids = canvas.draw_pixel_row(y=y, colors=colors, size=size, start_x=start_x)
    _save_to_disk()
    return f"Drew {len(ids)} pixels on row {y}"


@mcp.tool()
def inkpilot_draw_rect(
    x: float, y: float, width: float, height: float,
    fill: str = "#ffffff", stroke: str = None,
    stroke_width: float = None, rx: float = 0,
    opacity: float = None, label: str = None,
) -> str:
    """Draw a rectangle. Great for health bars, UI panels, tile backgrounds."""
    kwargs = {"x": x, "y": y, "width": width, "height": height, "fill": fill, "rx": rx}
    if stroke: kwargs["stroke"] = stroke
    if stroke_width is not None: kwargs["stroke_width"] = stroke_width
    if opacity is not None: kwargs["opacity"] = opacity
    if label: kwargs["label"] = label
    eid = canvas.draw_rect(**kwargs)
    _save_to_disk()
    return f"Rectangle {eid}"


@mcp.tool()
def inkpilot_draw_circle(
    cx: float, cy: float, r: float,
    fill: str = "#ffffff", stroke: str = None,
    stroke_width: float = None, opacity: float = None, label: str = None,
) -> str:
    """Draw a circle."""
    kwargs = {"cx": cx, "cy": cy, "r": r, "fill": fill}
    if stroke: kwargs["stroke"] = stroke
    if stroke_width is not None: kwargs["stroke_width"] = stroke_width
    if opacity is not None: kwargs["opacity"] = opacity
    if label: kwargs["label"] = label
    eid = canvas.draw_circle(**kwargs)
    _save_to_disk()
    return f"Circle {eid}"


@mcp.tool()
def inkpilot_draw_ellipse(
    cx: float, cy: float, rx: float, ry: float,
    fill: str = "#ffffff", stroke: str = None,
    stroke_width: float = None, opacity: float = None, label: str = None,
) -> str:
    """Draw an ellipse (oval). rx/ry = horizontal/vertical radii."""
    kwargs = {"cx": cx, "cy": cy, "rx": rx, "ry": ry, "fill": fill}
    if stroke: kwargs["stroke"] = stroke
    if stroke_width is not None: kwargs["stroke_width"] = stroke_width
    # Note: canvas.draw_ellipse doesn't support all kwargs yet, use insert_svg for advanced
    eid = canvas.draw_ellipse(**{k: v for k, v in kwargs.items() if k in ['cx','cy','rx','ry','fill','stroke']})
    _save_to_disk()
    return f"Ellipse {eid}"


@mcp.tool()
def inkpilot_draw_path(
    d: str, fill: str = "none", stroke: str = "#ffffff",
    stroke_width: float = 1, opacity: float = None,
    filter_id: str = None, clip_path_id: str = None,
    label: str = None,
) -> str:
    """Draw an SVG path. For complex shapes, curves, outlines.
    d = SVG path data (M, L, C, Q, A, Z commands). Use C for smooth cubic bezier curves.
    fill can be a color (#hex) or a gradient reference 'url(#gradient_id)'.
    filter_id = ID of a filter added with add_filter (for blur/shadow).
    clip_path_id = ID of a clip path added with add_clip_path."""
    kwargs = {"d": d, "fill": fill, "stroke": stroke, "stroke_width": stroke_width}
    if opacity is not None: kwargs["opacity"] = opacity
    if filter_id: kwargs["filter_id"] = filter_id
    if clip_path_id: kwargs["clip_path_id"] = clip_path_id
    if label: kwargs["label"] = label
    eid = canvas.draw_path(**kwargs)
    _save_to_disk()
    return f"Path {eid}"


@mcp.tool()
def inkpilot_draw_text(
    x: float, y: float, content: str,
    font_size: float = 16, fill: str = "#ffffff", font_family: str = "sans-serif",
) -> str:
    """Add text to the canvas."""
    eid = canvas.draw_text(x=x, y=y, content=content, font_size=font_size,
                           fill=fill, font_family=font_family)
    _save_to_disk()
    return f"Text {eid}"


@mcp.tool()
def inkpilot_draw_polygon(points: str, fill: str = "#ffffff", stroke: str = None) -> str:
    """Draw a polygon. points = 'x1,y1 x2,y2 x3,y3 ...'"""
    kwargs = {"points": points, "fill": fill}
    if stroke: kwargs["stroke"] = stroke
    eid = canvas.draw_polygon(**kwargs)
    _save_to_disk()
    return f"Polygon {eid}"


@mcp.tool()
def inkpilot_add_gradient(
    gradient_id: str,
    colors: list,
    x1: str = "0%", y1: str = "0%",
    x2: str = "0%", y2: str = "100%",
    gradient_type: str = "linear",
) -> str:
    """Add a gradient to defs for use as fill='url(#gradient_id)'.
    colors = list of [offset, color] pairs, e.g. [["0%", "#8B5E3C"], ["100%", "#5C3D2E"]].
    gradient_type = 'linear' or 'radial'.
    For radial: x1=cx, y1=cy, x2=r (radius)."""
    tuples = [(c[0], c[1]) for c in colors]
    result = canvas.add_gradient(gradient_id, tuples, x1, y1, x2, y2, gradient_type)
    _save_to_disk()
    return f"Gradient '{result}' added. Use fill='url(#{result})'"


@mcp.tool()
def inkpilot_add_filter(
    filter_id: str,
    blur_std: float = None,
    shadow_dx: float = None,
    shadow_dy: float = None,
    shadow_blur: float = None,
    shadow_color: str = None,
) -> str:
    """Add a filter (blur, drop shadow) to defs for use as filter='url(#filter_id)'.
    For blur only: set blur_std (e.g. 2.0).
    For drop shadow: set shadow_dx, shadow_dy, shadow_blur, shadow_color.
    Can combine both."""
    result = canvas.add_filter(filter_id, blur_std, shadow_dx, shadow_dy, shadow_blur, shadow_color)
    _save_to_disk()
    return f"Filter '{result}' added. Apply with filter='url(#{result})'"


@mcp.tool()
def inkpilot_add_clip_path(clip_id: str, shape_d: str) -> str:
    """Add a clip path to defs. shape_d is an SVG path 'd' string.
    Apply to elements via clip-path='url(#clip_id)' in style."""
    result = canvas.add_clip_path(clip_id, shape_d)
    _save_to_disk()
    return f"Clip path '{result}' added"


@mcp.tool()
def inkpilot_inkscape_action(actions: str, select_ids: list = None) -> str:
    """Run Inkscape's native engine on the canvas. This is POWERFUL.
    
    Workflow: select elements by ID, then apply operations.
    
    actions: semicolon-separated Inkscape action commands.
    select_ids: optional list of element IDs to pre-select (convenience shortcut).
    
    BOOLEAN OPERATIONS (select 2+ paths first):
      path-union          - Merge selected paths into one
      path-difference     - Bottom minus top
      path-intersection   - Keep only overlapping area
      path-exclusion      - XOR (parts belonging to only one path)
      path-combine        - Combine into compound path
      path-break-apart    - Break compound path into subpaths
      path-flatten        - Flatten overlapping objects into visible parts
      path-fracture       - Fracture into all possible segments
      path-simplify       - Remove extra nodes (smooth/simplify)
      path-cut            - Cut bottom path's stroke into pieces
      path-division       - Cut bottom path into pieces
    
    OBJECT OPERATIONS:
      object-to-path                - Convert shapes to paths
      object-stroke-to-path         - Convert strokes to filled paths
      object-align:left page        - Align (left|hcenter|right|top|vcenter|bottom) (page|drawing|selection)
      object-distribute:hgap        - Distribute (hgap|vgap|left|right|top|bottom)
      object-flip-horizontal        - Flip horizontally
      object-flip-vertical          - Flip vertically
      object-set-attribute:attr,val - Set SVG attribute
      object-set-clip               - Use topmost as clipping path
      object-set-mask               - Use topmost as mask
      object-trace                  - Bitmap trace
    
    TRANSFORMS:
      transform-rotate:45           - Rotate by degrees
      transform-scale:1.5           - Scale by factor
      transform-translate:10,20     - Move by dx,dy
    
    SELECTION:
      select-by-id:id1,id2          - Select specific elements
      select-all                    - Select everything
      select-clear                  - Deselect all
    
    STACKING:
      selection-group               - Group selected
      selection-ungroup             - Ungroup selected
      selection-top                 - Raise to top
      selection-bottom              - Lower to bottom
    
    FILTERS (200+ artistic effects, e.g.):
      org.inkscape.effect.filter.Blur          - Blur
      org.inkscape.effect.filter.f038          - Neon light
      org.inkscape.effect.filter.f020          - Oil painting
      org.inkscape.effect.filter.f223          - Bright chrome
      org.inkscape.effect.filter.f114          - 3D marble texture
      org.inkscape.effect.filter.crosssmooth   - Smooth edges
    
    EXPORT (usually auto-appended):
      export-filename:path  - Set output path
      export-type:svg       - Set format (svg, png, pdf)
      export-dpi:300        - Set resolution
      export-do             - Execute export
    
    Example: Merge two circles into one shape:
      select_ids=["circle_001", "circle_002"], actions="path-union"
    
    Example: Simplify a complex path:
      select_ids=["path_005"], actions="path-simplify"
    
    Example: Align all objects to center of page:
      actions="select-all;object-align:hcenter vcenter page"
    """
    # Flush to disk immediately (Inkscape reads from file)
    _save_to_disk_now()
    
    # Build the full action string
    action_parts = []
    
    # Pre-select elements if IDs provided
    if select_ids:
        ids_str = ",".join(select_ids)
        action_parts.append(f"select-by-id:{ids_str}")
    
    # Add the user's actions
    action_parts.append(actions.strip(";"))
    
    full_actions = ";".join(action_parts)
    
    # Run Inkscape CLI
    success, message = run_inkscape_actions(WORK_FILE, full_actions)
    
    if success:
        # Reload the modified SVG back into canvas
        reload_msg = canvas.reload_from_file(WORK_FILE)
        return f"Inkscape action completed.\n{message}\n{reload_msg}"
    else:
        return f"Inkscape action failed: {message}"


@mcp.tool()
def inkpilot_export_png(
    filename: str = None,
    dpi: int = 96,
    width: int = None,
    height: int = None,
    element_id: str = None,
) -> str:
    """Export the canvas (or a specific element) as PNG.
    
    filename: output name (saved to ~/.inkpilot/output/). Defaults to timestamped name.
    dpi: resolution (96 for screen, 300 for print).
    width/height: pixel dimensions (overrides dpi if set).
    element_id: export only this element (None = full page).
    """
    _save_to_disk_now()
    
    if not filename:
        filename = f"inkpilot_{int(time.time())}.png"
    if not filename.endswith(".png"):
        filename += ".png"
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    
    action_parts = []
    if element_id:
        action_parts.append(f"export-id:{element_id}")
        action_parts.append("export-id-only")
    else:
        action_parts.append("export-area-page")
    
    action_parts.append(f"export-filename:{out_path}")
    action_parts.append(f"export-dpi:{dpi}")
    if width:
        action_parts.append(f"export-width:{width}")
    if height:
        action_parts.append(f"export-height:{height}")
    action_parts.append("export-do")
    
    actions_str = ";".join(action_parts)
    success, message = run_inkscape_actions(WORK_FILE, actions_str)
    
    if success:
        return f"Exported PNG: {out_path}\n{message}"
    else:
        return f"PNG export failed: {message}"


@mcp.tool()
def inkpilot_insert_svg(svg: str) -> str:
    """Insert raw SVG markup. No outer <svg> tags — just inner elements.
    For complex elements not covered by other tools."""
    result = canvas.insert_svg(svg)
    _save_to_disk()
    return result


@mcp.tool()
def inkpilot_delete(element_id: str) -> str:
    """Delete an element by ID."""
    result = canvas.delete_element(element_id)
    _save_to_disk()
    return result


@mcp.tool()
def inkpilot_get_state() -> str:
    """Get canvas state: size, layers, element count. Call this to see what exists."""
    return canvas.get_state() + f"\nFile: {WORK_FILE}"


@mcp.tool()
def inkpilot_read_canvas() -> str:
    """Read detailed info about every element on the canvas.
    Returns positions, sizes, colors, path data, and styles for ALL elements.
    
    USE THIS to inspect your work after drawing. Essential for:
    - Checking if shapes are positioned correctly
    - Verifying colors and styles
    - Finding element IDs for Inkscape actions
    - Comparing your output to a reference
    - Debugging layout issues
    
    Call this FREQUENTLY to see what you've drawn and make corrections."""
    state = canvas.get_state()
    details = canvas.get_elements_detail()
    return f"{state}\n\nElements:\n{details}"


@mcp.tool()
def inkpilot_refresh_inkscape() -> str:
    """Reopen the current canvas in Inkscape to see latest changes.
    Call this after a batch of drawing operations so the user sees the update."""
    _save_to_disk_now()
    return open_in_inkscape(WORK_FILE)


@mcp.tool()
def inkpilot_save(filename: str = None, open_in_inkscape: bool = False) -> str:
    """Save a copy of the canvas to the output folder.
    The working file is always at ~/.inkpilot/canvas.svg.
    This saves an additional named copy to ~/.inkpilot/output/."""
    if not filename:
        filename = f"inkpilot_{int(time.time())}.svg"
    path = os.path.join(OUTPUT_DIR, filename)
    canvas.save(path)
    result = f"Saved to {path}"
    if open_in_inkscape:
        from .inkscape import open_in_inkscape as _open
        result += "\n" + _open(path)
    return result


# ── Entry Point ──────────────────────────────────────────────────

def run():
    ink = find_inkscape()
    config = _load_config()
    print("[Inkpilot] MCP server starting...", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Working file: {WORK_FILE}", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Output dir: {OUTPUT_DIR}", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Live preview: http://localhost:7878 ({'auto-open' if config.get('live_preview') else 'manual'})", file=sys.stderr, flush=True)
    if ink:
        print(f"[Inkpilot] Inkscape: {ink}", file=sys.stderr, flush=True)
    else:
        print("[Inkpilot] WARNING: Inkscape not found!", file=sys.stderr, flush=True)
    mcp.run(transport="stdio")
