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
import webbrowser

from mcp.server.fastmcp import FastMCP

from .canvas import SVGCanvas
from .live_server import LiveServer
from .inkscape import open_in_inkscape, find_inkscape

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
live = LiveServer(canvas, port=7878)
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


def _save_to_disk():
    """Save canvas to disk. Live preview updates via canvas → SSE automatically."""
    canvas.save(WORK_FILE)


# ── Tools ────────────────────────────────────────────────────────

@mcp.tool()
def inkpilot_setup_canvas(width: int = 512, height: int = 512) -> str:
    """ALWAYS call this first. Sets up the canvas and opens Inkscape with the working file.
    For a 32x32 sprite at pixel size 8, use width=256, height=256.
    For a 16x16 sprite at pixel size 16, use width=256, height=256."""
    canvas.clear()
    result = canvas.set_canvas(width, height)
    _save_to_disk()

    live_msg = _ensure_live_server()
    if live_msg:
        result += f"\n{live_msg}"
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
    """PRIMARY pixel art tool. Draw a batch of pixels as a group.
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
def inkpilot_draw_path(
    d: str, fill: str = "none", stroke: str = "#ffffff",
    stroke_width: float = 1, label: str = None,
) -> str:
    """Draw an SVG path. For complex shapes, curves, outlines.
    d = SVG path data (M, L, C, A, Z commands)."""
    kwargs = {"d": d, "fill": fill, "stroke": stroke, "stroke_width": stroke_width}
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
def inkpilot_refresh_inkscape() -> str:
    """Reopen the current canvas in Inkscape to see latest changes.
    Call this after a batch of drawing operations so the user sees the update."""
    _save_to_disk()
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
