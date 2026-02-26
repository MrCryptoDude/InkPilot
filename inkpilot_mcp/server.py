"""
Inkpilot MCP Server — v4.0 (CreativeBridge Architecture)

Claude controls Inkscape through pure code — no mouse simulation needed.
The SVG engine composes art in memory with mathematical precision.
Changes flush to disk automatically and Inkscape renders them.

Like VSCode Claude but for art: Claude writes, the app renders.
"""
import sys
import os
import time

from mcp.server.fastmcp import FastMCP

# Bridge architecture
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridge.engine import SVGDocument
from bridge.adapters.inkscape import InkscapeAdapter

# Legacy tools (remote control, SVG reader)
from .svg_reader import SVGReader
from . import remote

# ── Paths ────────────────────────────────────────────────────────

def _home():
    return os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or os.path.expanduser("~")

WORK_DIR = os.path.join(_home(), ".inkpilot")
WORK_FILE = os.path.join(WORK_DIR, "canvas.svg")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = os.path.join(_PROJECT_DIR, "screenshots")

os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ── Globals ──────────────────────────────────────────────────────

doc = SVGDocument(512, 512)
adapter = InkscapeAdapter(WORK_FILE, OUTPUT_DIR)
reader = SVGReader(WORK_FILE)
mcp = FastMCP("inkpilot")


def _auto_flush():
    """Write current document to disk so Inkscape can render it."""
    doc.flush(WORK_FILE)


# ══════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_setup_canvas(width: int = 512, height: int = 512) -> str:
    """Create a new SVG project and open it in Inkscape.
    
    This creates a blank SVG file and opens Inkscape.
    
    PRIMARY WORKFLOW (precision art):
    1. Use inkpilot_compose() to create elements with exact SVG paths
    2. Use inkpilot_add_gradient() for gradients and shading
    3. Use inkpilot_set_style() to adjust colors
    4. Use inkpilot_inkscape_action() for boolean ops, alignment
    5. Export with inkpilot_export_png() or inkpilot_save()
    
    SECONDARY WORKFLOW (manual drawing via remote control):
    - inkpilot_drag() to draw with mouse simulation
    - inkpilot_key() for keyboard shortcuts
    - inkpilot_screenshot() to visually verify
    
    KEYBOARD SHORTCUTS (press with inkpilot_key):
      r = rectangle tool    e = ellipse tool      p = pen/bezier tool
      b = pencil/freehand   t = text tool         n = node editor
      s = star tool          g = gradient tool     d = dropper tool
      f5 = fill & stroke dialog    ctrl+z = undo
      ctrl+s = save         ctrl+shift+e = export dialog
      + = zoom in           - = zoom out          5 = zoom to fit
    """
    global doc
    doc = SVGDocument(width, height)
    _auto_flush()
    
    ok, msg = adapter.launch(WORK_FILE)
    time.sleep(2)
    
    connected = adapter.is_connected
    
    result = [
        f"Canvas: {width}×{height}",
        f"File: {WORK_FILE}",
        f"Inkscape: {msg}",
        f"Connected: {connected}",
        f"",
        f"Ready. Use inkpilot_compose() to draw with precision.",
        f"All elements auto-flush to disk — Inkscape renders them.",
    ]
    return "\n".join(result)


# ══════════════════════════════════════════════════════════════════
# COMPOSE — Claude's artistic power (precision SVG generation)
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_compose(elements: list) -> str:
    """Draw precise SVG elements directly — Claude's artistic toolkit.
    
    This is how you create PROFESSIONAL artwork. Instead of dragging
    shapes with a mouse, you specify exact SVG elements with bezier
    curves, gradients, and pixel-perfect positioning.
    
    elements: list of element dicts. Each element has:
      - 'type': 'ellipse'|'circle'|'rect'|'path'|'text'
      - type-specific params (see below)
      - 'fill': color string (default '#8B6914')
      - 'stroke': color string (default 'none')
      - 'stroke_width': number (default 0)
      - 'opacity': 0.0–1.0 (default 1.0)
      - 'id': optional element ID for later reference
      - 'layer': layer name (default 'artwork')
      - 'transform': SVG transform string (optional)
    
    Type-specific params:
      ellipse: cx, cy, rx, ry
      circle:  cx, cy, r
      rect:    x, y, w, h, rx (optional corner radius)
      path:    d (SVG path data string)
      text:    x, y, content, font_size, font_family
    
    SVG Path commands (for 'path' type):
      M x y      — move to
      L x y      — line to  
      C x1 y1, x2 y2, x y — cubic bezier
      Q x1 y1, x y — quadratic bezier
      A rx ry rot large-arc sweep x y — arc
      Z          — close path
    
    Example — draw a beaver body with gradient:
    [
      {"type": "path", "fill": "#8B6914",
       "d": "M 200 300 C 150 200, 350 200, 300 300 C 350 400, 150 400, 200 300 Z"},
      {"type": "ellipse", "cx": 250, "cy": 180, "rx": 60, "ry": 50, "fill": "#A0772B"},
      {"type": "circle", "cx": 235, "cy": 170, "r": 8, "fill": "#000000"}
    ]
    
    Returns list of element IDs.
    """
    if not elements:
        return "No elements provided."
    
    ids = doc.batch(elements)
    _auto_flush()
    
    return f"Composed {len(ids)} elements: {', '.join(ids)}\nAuto-flushed to disk."


@mcp.tool()
def inkpilot_add_gradient(grad_id: str, grad_type: str = "linear",
                          stops: list = None,
                          x1: str = "0%", y1: str = "0%",
                          x2: str = "0%", y2: str = "100%",
                          cx: str = "50%", cy: str = "50%",
                          r: str = "50%") -> str:
    """Add a gradient definition for use in fills.
    
    grad_id: unique name (e.g. 'fur_gradient')
    grad_type: 'linear' or 'radial'
    stops: list of [offset%, color, opacity] arrays
      e.g. [[0, "#8B6914", 1.0], [100, "#5C4400", 1.0]]
    
    Use in fills as: "url(#fur_gradient)"
    """
    stop_tuples = [(s[0], s[1], s[2]) for s in (stops or [])]
    
    if grad_type == "radial":
        doc.radial_gradient(grad_id, stop_tuples, cx=cx, cy=cy, r=r)
    else:
        doc.linear_gradient(grad_id, stop_tuples, x1=x1, y1=y1, x2=x2, y2=y2)
    
    _auto_flush()
    return f"Gradient '{grad_id}' added. Use fill='url(#{grad_id})' in elements."


@mcp.tool()
def inkpilot_set_style(elem_id: str, fill: str = None, stroke: str = None,
                       stroke_width: float = None, opacity: float = None) -> str:
    """Change the style of an existing element by ID."""
    kwargs = {}
    if fill is not None: kwargs["fill"] = fill
    if stroke is not None: kwargs["stroke"] = stroke
    if stroke_width is not None: kwargs["stroke_width"] = stroke_width
    if opacity is not None: kwargs["opacity"] = opacity
    
    doc.set_style(elem_id, **kwargs)
    _auto_flush()
    return f"Style updated for '{elem_id}'."


@mcp.tool()
def inkpilot_clear_canvas(layer: str = None) -> str:
    """Clear all elements from the canvas (or a specific layer)."""
    doc.clear(layer)
    _auto_flush()
    return f"Canvas cleared{f' (layer: {layer})' if layer else ''}."


# ══════════════════════════════════════════════════════════════════
# EXPORT & SAVE
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_save(filename: str = None) -> str:
    """Save the finished SVG to the output folder for delivery.
    Returns the path so the file can be shared with the user."""
    if not filename:
        filename = f"inkpilot_{int(time.time())}.svg"
    if not filename.endswith(".svg"):
        filename += ".svg"
    out_path = os.path.join(OUTPUT_DIR, filename)
    
    _auto_flush()
    import shutil
    shutil.copy2(WORK_FILE, out_path)
    return f"Saved to {out_path}"


@mcp.tool()
def inkpilot_export_png(
    filename: str = None, dpi: int = 96,
    width: int = None, height: int = None,
) -> str:
    """Export the canvas as PNG for delivery.
    filename: saved to ~/.inkpilot/output/. dpi: 96=screen, 300=print."""
    _auto_flush()
    
    if not filename:
        filename = f"inkpilot_{int(time.time())}.png"
    if not filename.endswith(".png"):
        filename += ".png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    
    ok, result = adapter.export_png(out_path, dpi=dpi, width=width, height=height)
    if ok:
        return f"Exported PNG: {result}"
    return f"Export failed: {result}"


# ══════════════════════════════════════════════════════════════════
# INKSCAPE CLI — For app-native operations
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_inkscape_action(actions: str, select_ids: list = None) -> str:
    """Run Inkscape CLI actions on the SVG file.
    
    Use this for operations that are faster via CLI than mouse:
    - object-trace (bitmap vectorization)
    - path-union, path-difference (boolean operations)
    - path-simplify (smooth paths)
    - transform-rotate:45, transform-scale:1.5
    - object-align:hcenter vcenter page
    
    IMPORTANT: Save the file first (ctrl+s via inkpilot_key) before
    running CLI actions, as CLI reads from disk.
    
    select_ids: list of element IDs to pre-select.
    actions: semicolon-separated Inkscape action commands.
    """
    _auto_flush()
    ok, msg = adapter.execute(actions, select_ids)
    return msg


@mcp.tool()
def inkpilot_import_image(file_path: str) -> str:
    """Import a raster image into the current Inkscape document.
    file_path: absolute path to image on disk.
    
    Uses Inkscape CLI's file-import action.
    After import, use inkpilot_screenshot() to see the result.
    """
    if not file_path or not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"
    
    _auto_flush()
    abs_path = os.path.abspath(file_path)
    ok, msg = adapter.execute(f"file-import:{abs_path}")
    return msg


# ══════════════════════════════════════════════════════════════════
# REMOTE CONTROL — Secondary workflow (mouse/keyboard simulation)
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_screenshot(save_path: str = None) -> str:
    """Capture what Inkscape looks like right now.
    
    This is your EYES — screenshot the Inkscape window to see:
    - The canvas and what you've drawn
    - Which tool is selected
    - The toolbox, menus, and panels
    - Dialog windows
    
    Returns the path to the screenshot PNG.
    Use this FREQUENTLY to verify your work and find click targets.
    
    The screenshot is saved to the project's assets folder so you can view it.
    """
    if not save_path:
        save_path = os.path.join(SCREENSHOT_DIR, f"screen_{int(time.time())}.png")
    
    ok, msg, path = remote.screenshot(save_path)
    if ok:
        return f"Screenshot saved: {path}\nUse Filesystem tools to view it."
    return f"Screenshot failed: {msg}"


@mcp.tool()
def inkpilot_click(x: int, y: int, button: str = "left") -> str:
    """Click at position (x, y) in the Inkscape window.
    
    Coordinates are relative to the Inkscape window's top-left corner.
    Use inkpilot_screenshot() first to see where things are.
    
    button: 'left' (default), 'right' (context menu), 'double' (double-click).
    
    Common click targets (approximate — verify with screenshot):
    - Toolbox is on the left edge
    - Canvas is the large center area
    - Properties/panels are on the right
    - Color palette is at the bottom
    """
    ok, msg = remote.click(x, y, button)
    return msg


@mcp.tool()
def inkpilot_drag(x1: int, y1: int, x2: int, y2: int,
                  duration: float = 0.5, button: str = "left",
                  deselect: bool = True) -> str:
    """Drag from (x1,y1) to (x2,y2) in the Inkscape window.
    
    This is your main DRAWING tool. Use it to:
    - Draw rectangles (select rect tool, then drag)
    - Draw ellipses (select ellipse tool, then drag)
    - Draw freehand lines (select pencil tool, then drag)
    - Move objects (click and drag with deselect=False)
    - Select multiple objects (drag selection rectangle with deselect=False)
    - Resize objects (drag handles with deselect=False)
    
    duration: seconds for the drag motion (slower = more precise).
    Coordinates are relative to the Inkscape window.
    
    deselect: if True (default), presses Escape after drawing to deselect
    the shape. This prevents the NEXT drag from modifying/moving the shape
    you just drew. Set to False when you intentionally want to move or
    resize an existing selection.
    """
    ok, msg = remote.drag(x1, y1, x2, y2, duration, button)
    if ok and deselect:
        time.sleep(0.3)
        remote.key("f1")
        time.sleep(0.2)
        remote.click(200, 400)
        time.sleep(0.15)
    return msg


@mcp.tool()
def inkpilot_drag_path(points: list, duration_per_segment: float = 0.2,
                      deselect: bool = True) -> str:
    """Drag along a series of points for complex strokes.
    
    points: [[x1,y1], [x2,y2], [x3,y3], ...]
    
    Use with the pencil/freehand tool (key 'b') to draw curved lines,
    or with the pen/bezier tool (key 'p') for precise paths.
    
    duration_per_segment: seconds per segment (slower = smoother).
    deselect: if True (default), deselects after drawing so next stroke is new.
    """
    pts = [(p[0], p[1]) for p in points]
    ok, msg = remote.drag_path(pts, duration_per_segment)
    if ok and deselect:
        time.sleep(0.3)
        remote.key("f1")
        time.sleep(0.2)
        remote.click(200, 400)
        time.sleep(0.15)
    return msg


@mcp.tool()
def inkpilot_key(keys: str) -> str:
    """Press keyboard key(s) in Inkscape.
    
    INKSCAPE TOOL SHORTCUTS:
      r = Rectangle tool       e = Ellipse/circle tool
      p = Pen/bezier tool      b = Pencil/freehand tool
      t = Text tool            n = Node editor
      s = Star/polygon tool    g = Gradient tool
      d = Color dropper        i = Color dropper (alt)
      space = Select/move tool (pointer)
      
    COMMON SHORTCUTS:
      ctrl+z = Undo            ctrl+y = Redo
      ctrl+s = Save            ctrl+shift+s = Save As
      ctrl+c = Copy            ctrl+v = Paste
      ctrl+d = Duplicate       delete = Delete selected
      ctrl+g = Group           ctrl+shift+g = Ungroup
      ctrl+shift+e = Export PNG dialog
      
    VIEW:
      + or = = Zoom in         - = Zoom out
      5 = Zoom to fit page     1 = Zoom 1:1
      3 = Zoom to selection
      
    OBJECT:
      ctrl+shift+f = Fill & Stroke dialog
      page_up = Raise           page_down = Lower
      home = Raise to top       end = Lower to bottom
      
    Examples: 'r', 'ctrl+z', 'ctrl+shift+e', 'delete'
    """
    ok, msg = remote.key(keys)
    return msg


@mcp.tool()
def inkpilot_type(text: str) -> str:
    """Type text into Inkscape (for text tool, dialogs, rename fields, etc.).
    Make sure the text tool is active and cursor is placed first."""
    ok, msg = remote.type_text(text)
    return msg


@mcp.tool()
def inkpilot_scroll(x: int, y: int, clicks: int = 3,
                    direction: str = "down") -> str:
    """Scroll in the Inkscape window at position (x, y).
    direction: 'up' or 'down'. Use ctrl+scroll for zoom.
    For zoom: use inkpilot_key('+') or inkpilot_key('-') instead."""
    ok, msg = remote.scroll(x, y, clicks, direction)
    return msg


@mcp.tool()
def inkpilot_window_info() -> str:
    """Get info about the Inkscape window: position, size, title.
    Also returns the current canvas coordinate mapping so you know
    exactly where to draw without needing a screenshot."""
    ok, info = remote.get_window_info()
    if ok:
        return (f"Title: {info['title']}\n"
                f"Position: ({info['left']}, {info['top']})\n"
                f"Size: {info['width']}x{info['height']}\n"
                f"Active: {info['is_active']}")
    return f"Error: {info.get('error', 'Unknown')}"


# ══════════════════════════════════════════════════════════════════
# INTROSPECTION — Know what's on the canvas
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def inkpilot_read_canvas() -> str:
    """Read the SVG file to inspect element IDs, positions, and styles.
    
    This reads the file on disk — make sure Inkscape has saved first
    (use inkpilot_key('ctrl+s') before calling this).
    
    Returns element details for use with inkpilot_inkscape_action's select_ids."""
    state = reader.get_state()
    details = reader.get_elements_detail()
    return f"{state}\n\nElements:\n{details}"


@mcp.tool()
def inkpilot_get_state() -> str:
    """Quick summary of the SVG file: dimensions, layers, element count."""
    return doc.summary()


# ══════════════════════════════════════════════════════════════════
# BLENDER — 3D modeling, rendering, Grease Pencil 2D
# ══════════════════════════════════════════════════════════════════

from bridge.adapters.blender import BlenderConnection
blender = BlenderConnection()


def _fmt(resp):
    """Format a Blender response into readable text."""
    if resp.get("status") == "ok":
        import json as _json
        return _json.dumps(resp["result"], indent=2)
    return f"Error: {resp.get('message', 'Unknown error')}"


@mcp.tool()
def blender_ping() -> str:
    """Check if Blender is connected and get scene summary.
    Returns Blender version, scene name, and object count.
    Make sure Blender is open with the Inkpilot addon enabled."""
    return _fmt(blender.send("ping"))


@mcp.tool()
def blender_get_scene() -> str:
    """Get full info about the current Blender scene.
    Returns all objects with names, types, locations, materials, and render settings.
    Call this first to understand what's in the scene."""
    return _fmt(blender.send("get_scene_info"))


@mcp.tool()
def blender_get_object(name: str) -> str:
    """Get detailed info about one object: vertices, faces, materials, transforms."""
    return _fmt(blender.send("get_object_info", {"name": name}))


@mcp.tool()
def blender_create_object(
    object_type: str = "cube",
    name: str = None,
    location: list = None,
    rotation: list = None,
    scale: list = None,
    size: float = None,
    radius: float = None,
    depth: float = None,
    material_color: str = None,
    text: str = None,
    light_type: str = None,
    energy: float = None,
) -> str:
    """Create a 3D object in Blender.
    
    object_type: cube, sphere, cylinder, cone, plane, torus, monkey,
                 text, camera, light, empty
    name: optional name for the object
    location: [x, y, z] position (default [0,0,0])
    rotation: [rx, ry, rz] in degrees
    scale: [sx, sy, sz] scale factors
    size: size for cube/plane/monkey (default 2)
    radius: radius for sphere/cylinder/cone (default 1)
    depth: depth for cylinder/cone (default 2)
    material_color: hex color like '#ff3333' to auto-apply
    text: text content (for text objects)
    light_type: POINT, SUN, SPOT, AREA (for light objects)
    energy: light intensity (for light objects)
    """
    params = {"object_type": object_type}
    if name: params["name"] = name
    if location: params["location"] = location
    if rotation: params["rotation"] = rotation
    if scale: params["scale"] = scale
    if size is not None: params["size"] = size
    if radius is not None: params["radius"] = radius
    if depth is not None: params["depth"] = depth
    if material_color: params["material_color"] = material_color
    if text: params["text"] = text
    if light_type: params["light_type"] = light_type
    if energy is not None: params["energy"] = energy
    return _fmt(blender.send("create_object", params))


@mcp.tool()
def blender_delete_object(name: str) -> str:
    """Delete an object by name."""
    return _fmt(blender.send("delete_object", {"name": name}))


@mcp.tool()
def blender_modify_object(
    name: str,
    location: list = None,
    rotation: list = None,
    scale: list = None,
    visible: bool = None,
    new_name: str = None,
) -> str:
    """Move, rotate, scale, rename, or hide an object.
    
    name: object to modify
    location: [x, y, z]
    rotation: [rx, ry, rz] in degrees
    scale: [sx, sy, sz]
    visible: show/hide
    new_name: rename the object
    """
    params = {"name": name}
    if location: params["location"] = location
    if rotation: params["rotation"] = rotation
    if scale: params["scale"] = scale
    if visible is not None: params["visible"] = visible
    if new_name: params["new_name"] = new_name
    return _fmt(blender.send("modify_object", params))


@mcp.tool()
def blender_duplicate_object(name: str, new_name: str = None, offset: list = None) -> str:
    """Duplicate an object. Optional new_name and offset [x,y,z]."""
    params = {"name": name}
    if new_name: params["new_name"] = new_name
    if offset: params["offset"] = offset
    return _fmt(blender.send("duplicate_object", params))


@mcp.tool()
def blender_set_material(
    name: str,
    color: str = None,
    metallic: float = None,
    roughness: float = None,
    emission_color: str = None,
    emission_strength: float = None,
) -> str:
    """Set material on an object. Supports PBR properties.
    
    name: object name
    color: hex color '#rrggbb' or [r,g,b] 0-1
    metallic: 0.0 (plastic) to 1.0 (metal)
    roughness: 0.0 (mirror) to 1.0 (matte)
    emission_color: hex color for glow
    emission_strength: glow intensity
    """
    params = {"name": name}
    if color: params["color"] = color
    if metallic is not None: params["metallic"] = metallic
    if roughness is not None: params["roughness"] = roughness
    if emission_color: params["emission_color"] = emission_color
    if emission_strength is not None: params["emission_strength"] = emission_strength
    return _fmt(blender.send("set_material", params))


@mcp.tool()
def blender_set_camera(
    location: list = None,
    rotation: list = None,
    look_at: list = None,
    focal_length: float = None,
) -> str:
    """Set up the camera. Use look_at=[x,y,z] to point at a target."""
    params = {}
    if location: params["location"] = location
    if rotation: params["rotation"] = rotation
    if look_at: params["look_at"] = look_at
    if focal_length: params["focal_length"] = focal_length
    return _fmt(blender.send("set_camera", params))


@mcp.tool()
def blender_add_light(
    light_type: str = "POINT",
    location: list = None,
    energy: float = 1000,
    color: list = None,
    name: str = None,
) -> str:
    """Add a light. Types: POINT, SUN, SPOT, AREA."""
    params = {"light_type": light_type, "energy": energy}
    if location: params["location"] = location
    if color: params["color"] = color
    if name: params["name"] = name
    return _fmt(blender.send("add_light", params))


@mcp.tool()
def blender_set_world(color: str = None, strength: float = None) -> str:
    """Set world/environment background color and strength."""
    params = {}
    if color: params["color"] = color
    if strength is not None: params["strength"] = strength
    return _fmt(blender.send("set_world", params))


@mcp.tool()
def blender_clear_scene(object_type: str = None) -> str:
    """Clear the scene. Optional type filter: MESH, LIGHT, CAMERA, etc."""
    params = {}
    if object_type: params["type"] = object_type
    return _fmt(blender.send("clear_scene", params))


@mcp.tool()
def blender_render(
    output_path: str = None,
    format: str = "PNG",
) -> str:
    """Render the scene to an image file.
    output_path: where to save (default: temp folder)
    format: PNG, JPEG, BMP, TIFF
    """
    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, f"render_{int(time.time())}.png")
    params = {"output_path": output_path, "format": format}
    return _fmt(blender.send("render", params))


@mcp.tool()
def blender_set_render_settings(
    engine: str = None,
    resolution_x: int = None,
    resolution_y: int = None,
    samples: int = None,
    film_transparent: bool = None,
) -> str:
    """Configure render settings.
    engine: CYCLES (realistic) or BLENDER_EEVEE_NEXT (fast)
    samples: quality (higher = better but slower). 128 is good for preview, 512+ for final.
    film_transparent: transparent background (for sprites/assets).
    """
    params = {}
    if engine: params["engine"] = engine
    if resolution_x: params["resolution_x"] = resolution_x
    if resolution_y: params["resolution_y"] = resolution_y
    if samples: params["samples"] = samples
    if film_transparent is not None: params["film_transparent"] = film_transparent
    return _fmt(blender.send("set_render_settings", params))


@mcp.tool()
def blender_screenshot_viewport(output_path: str = None) -> str:
    """Capture a quick viewport screenshot (faster than full render)."""
    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, f"viewport_{int(time.time())}.png")
    return _fmt(blender.send("screenshot_viewport", {"output_path": output_path}))


@mcp.tool()
def blender_execute_code(code: str) -> str:
    """Execute arbitrary Python code in Blender (bpy API).
    
    Use this for anything the other tools don't cover.
    You have access to: bpy, mathutils, math, bmesh, os, json.
    
    ALWAYS save your work first. This is powerful but can break things.
    
    Examples:
      'bpy.ops.mesh.primitive_ico_sphere_add(radius=2)'
      'bpy.context.scene.render.engine = "CYCLES"'
      'print([o.name for o in bpy.data.objects])'
    """
    return _fmt(blender.send("execute_code", {"code": code}))


@mcp.tool()
def blender_grease_pencil_create(name: str = "Drawing", layer_name: str = "Lines") -> str:
    """Create a Grease Pencil object for 2D drawing in 3D space."""
    return _fmt(blender.send("create_grease_pencil", {"name": name, "layer_name": layer_name}))


@mcp.tool()
def blender_grease_pencil_stroke(
    points: list,
    gp_name: str = "Drawing",
    layer_name: str = "Lines",
    color: str = "#000000",
    line_width: int = 10,
) -> str:
    """Draw a stroke on a Grease Pencil object.
    
    points: [[x,y,z], [x,y,z], ...] — 3D coordinates for the stroke
    color: hex color
    line_width: stroke thickness
    """
    return _fmt(blender.send("draw_grease_pencil_stroke", {
        "gp_name": gp_name, "layer_name": layer_name,
        "points": points, "color": color, "line_width": line_width,
    }))


# ── Entry Point ──────────────────────────────────────────────────

def run():
    print("[Inkpilot] MCP server starting (v5.0 — Blender + Inkscape)...", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Working file: {WORK_FILE}", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Output dir: {OUTPUT_DIR}", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Inkscape: {adapter._inkscape_path or 'NOT FOUND'}", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Blender: checking port 9876...", file=sys.stderr, flush=True)
    print(f"[Inkpilot] Blender connected: {blender.is_alive()}", file=sys.stderr, flush=True)
    
    mcp.run(transport="stdio")
