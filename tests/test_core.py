#!/usr/bin/env python3
"""
Inkpilot — Core Engine Tests
Tests the SVG engine, context builder, and response parser
without needing Inkscape, GTK, or the Claude API.

Run: python tests/test_core.py
"""
import sys
import os
from pathlib import Path
from lxml import etree

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inkpilot.svg_engine import SVGEngine
from inkpilot.context_builder import build_context
from inkpilot.response_parser import parse_response, validate_svg_fragment

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"


def create_test_svg():
    """Create a minimal SVG for testing."""
    nsmap = {None: SVG_NS, "inkscape": INKSCAPE_NS}
    root = etree.Element(f"{{{SVG_NS}}}svg", nsmap=nsmap)
    root.set("width", "512")
    root.set("height", "512")
    root.set("viewBox", "0 0 512 512")

    layer = etree.SubElement(root, f"{{{SVG_NS}}}g")
    layer.set("id", "layer1")
    layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
    layer.set(f"{{{INKSCAPE_NS}}}label", "Layer 1")

    return root


def test_shape_commands():
    """Test basic shape creation commands."""
    print("── Test: Shape Commands ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Rectangle
    rect_id = engine.execute_command({
        "action": "rect", "x": 10, "y": 10, "width": 100, "height": 50,
        "fill": "#ff0000", "stroke": "#000000"
    })
    assert rect_id, "rect should return an ID"
    print(f"  ✓ rect created: {rect_id}")

    # Circle
    circle_id = engine.execute_command({
        "action": "circle", "cx": 200, "cy": 200, "r": 50, "fill": "#0000ff"
    })
    assert circle_id, "circle should return an ID"
    print(f"  ✓ circle created: {circle_id}")

    # Path
    path_id = engine.execute_command({
        "action": "path",
        "d": "M10,80 Q95,10 180,80 T350,80",
        "fill": "none", "stroke": "#00ff00", "stroke_width": 3
    })
    assert path_id, "path should return an ID"
    print(f"  ✓ path created: {path_id}")

    # Text
    text_id = engine.execute_command({
        "action": "text", "x": 50, "y": 300,
        "content": "Hello Inkpilot!", "font_size": 24, "fill": "#333"
    })
    assert text_id, "text should return an ID"
    print(f"  ✓ text created: {text_id}")

    print(f"  Total created: {len(engine.created_ids)} elements\n")
    return svg


def test_pixel_art():
    """Test pixel art generation."""
    print("── Test: Pixel Art ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Simple 4x4 smiley face
    pixels = [
        [None,    "#000", "#000",  None],
        ["#000",  "#ff0", "#ff0",  "#000"],
        ["#000",  "#ff0", "#ff0",  "#000"],
        [None,    "#000", "#000",  None],
    ]

    group_id = engine.execute_command({
        "action": "pixel_grid",
        "x": 100, "y": 100,
        "grid_w": 4, "grid_h": 4,
        "pixel_size": 16,
        "pixels": pixels,
        "label": "test_smiley"
    })
    assert group_id, "pixel_grid should return a group ID"
    print(f"  ✓ pixel art created: {group_id}")

    # Verify the group has the right number of filled pixels
    group = svg.xpath(f'//*[@id="{group_id}"]')[0]
    rects = group.findall(f"{{{SVG_NS}}}rect")
    assert len(rects) == 12, f"Expected 12 filled pixels, got {len(rects)}"
    print(f"  ✓ correct pixel count: {len(rects)}\n")
    return svg


def test_transforms():
    """Test transform commands."""
    print("── Test: Transforms ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Create a rect to transform
    rect_id = engine.execute_command({
        "action": "rect", "id": "transform_target",
        "x": 50, "y": 50, "width": 100, "height": 100, "fill": "#f00"
    })

    # Translate
    engine.execute_command({"action": "translate", "target": rect_id, "x": 20, "y": 30})
    elem = svg.xpath(f'//*[@id="{rect_id}"]')[0]
    assert "translate" in elem.get("transform", ""), "Should have translate transform"
    print(f"  ✓ translate applied")

    # Rotate
    engine.execute_command({"action": "rotate", "target": rect_id, "angle": 45, "cx": 100, "cy": 100})
    assert "rotate" in elem.get("transform", ""), "Should have rotate transform"
    print(f"  ✓ rotate applied")

    # Scale
    engine.execute_command({"action": "scale", "target": rect_id, "sx": 1.5, "sy": 1.5})
    assert "scale" in elem.get("transform", ""), "Should have scale transform"
    print(f"  ✓ scale applied\n")


def test_context_builder():
    """Test context extraction."""
    print("── Test: Context Builder ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Add some elements
    engine.execute_command({"action": "rect", "id": "bg", "x": 0, "y": 0, "width": 512, "height": 512, "fill": "#eee"})
    engine.execute_command({"action": "circle", "id": "sun", "cx": 400, "cy": 100, "r": 40, "fill": "#ffcc00"})

    context = build_context(svg, selected_ids=["sun"])

    assert "[Document]" in context, "Should contain document info"
    assert "[Layers]" in context, "Should contain layer info"
    assert "[Selected]" in context, "Should contain selection info"
    assert "sun" in context, "Should reference selected element"

    print(f"  ✓ context generated ({len(context)} chars)")
    print(f"  Preview:\n{context[:300]}...\n")


def test_response_parser():
    """Test parsing Claude responses."""
    print("── Test: Response Parser ──")

    # Test SVG response
    response1 = """Here's a red square for you:

```svg
<rect id="square1" x="10" y="10" width="100" height="100" fill="#ff0000" />
```

I've created a simple red square at position (10, 10)."""

    parsed = parse_response(response1)
    assert len(parsed.svg_fragments) == 1, "Should find 1 SVG fragment"
    assert "rect" in parsed.svg_fragments[0], "SVG should contain rect"
    assert "red square" in parsed.plain_text.lower(), "Plain text should contain explanation"
    print(f"  ✓ SVG response parsed: {len(parsed.svg_fragments)} fragment(s)")

    # Test command response
    response2 = """I'll create a sprite sheet grid for you:

```inkpilot-commands
{
  "description": "Create a 4x3 sprite sheet",
  "actions": [
    {"action": "set_canvas", "width": 264, "height": 198},
    {"action": "sprite_sheet_grid", "columns": 4, "rows": 3, "cell_width": 64, "cell_height": 64, "padding": 2}
  ]
}
```

The grid is set up with 2px padding between frames."""

    parsed2 = parse_response(response2)
    assert len(parsed2.commands) == 2, f"Should find 2 commands, got {len(parsed2.commands)}"
    assert parsed2.commands[0]["action"] == "set_canvas"
    assert parsed2.commands[1]["action"] == "sprite_sheet_grid"
    print(f"  ✓ Command response parsed: {len(parsed2.commands)} command(s)")

    # Test mixed response
    response3 = """Let me create both SVG and run some commands:

```svg
<circle id="dot" cx="50" cy="50" r="10" fill="#00ff00" />
```

```inkpilot-commands
{"description": "Group it", "actions": [{"action": "group", "label": "dots", "children": ["dot"]}]}
```

Done!"""

    parsed3 = parse_response(response3)
    assert len(parsed3.svg_fragments) == 1
    assert len(parsed3.commands) == 1
    print(f"  ✓ Mixed response parsed: {len(parsed3.svg_fragments)} SVG + {len(parsed3.commands)} cmd\n")


def test_svg_insertion():
    """Test inserting SVG fragments from parsed responses."""
    print("── Test: SVG Fragment Insertion ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    fragment = '<g id="test_group"><rect x="0" y="0" width="50" height="50" fill="#f00"/><circle cx="25" cy="25" r="10" fill="#fff"/></g>'

    is_valid, cleaned = validate_svg_fragment(fragment)
    assert is_valid, f"Fragment should be valid: {cleaned}"
    print(f"  ✓ fragment validated")

    ids = engine.insert_svg_fragment(cleaned)
    assert len(ids) >= 1, "Should insert at least 1 element"
    print(f"  ✓ inserted {len(ids)} element(s): {ids}\n")


def test_sprite_sheet():
    """Test sprite sheet grid creation."""
    print("── Test: Sprite Sheet Grid ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    grid_id = engine.execute_command({
        "action": "sprite_sheet_grid",
        "columns": 4, "rows": 2,
        "cell_width": 64, "cell_height": 64,
        "padding": 2,
    })

    group = svg.xpath(f'//*[@id="{grid_id}"]')[0]
    frames = group.findall(f"{{{SVG_NS}}}rect")
    assert len(frames) == 8, f"Expected 8 frames (4x2), got {len(frames)}"
    print(f"  ✓ sprite grid created: {len(frames)} frames")

    # Check positioning
    first = frames[0]
    second = frames[1]
    x1 = float(first.get("x"))
    x2 = float(second.get("x"))
    assert x2 == x1 + 64 + 2, "Frames should be spaced with padding"
    print(f"  ✓ frame spacing correct: {x1} → {x2}\n")


def test_layer_management():
    """Test layer creation and switching."""
    print("── Test: Layer Management ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Create layers
    bg_id = engine.execute_command({"action": "layer", "label": "Background"})
    char_id = engine.execute_command({"action": "layer", "label": "Characters"})
    fx_id = engine.execute_command({"action": "layer", "label": "Effects"})
    print(f"  ✓ created layers: {bg_id}, {char_id}, {fx_id}")

    # Switch to Background and draw
    engine.execute_command({"action": "set_layer", "label": "Background"})
    engine.execute_command({"action": "rect", "id": "sky", "x": 0, "y": 0, "width": 512, "height": 256, "fill": "#87CEEB"})
    
    # Verify sky is inside Background layer
    bg_layer = engine._find_layer_by_label("Background")
    sky = svg.xpath('//*[@id="sky"]')[0]
    assert sky.getparent() == bg_layer, "Sky should be in Background layer"
    print(f"  ✓ element placed in correct layer")

    # Switch to Characters and draw
    engine.execute_command({"action": "set_layer", "label": "Characters"})
    engine.execute_command({"action": "circle", "id": "hero", "cx": 100, "cy": 200, "r": 20, "fill": "#ff0000"})
    
    char_layer = engine._find_layer_by_label("Characters")
    hero = svg.xpath('//*[@id="hero"]')[0]
    assert hero.getparent() == char_layer, "Hero should be in Characters layer"
    print(f"  ✓ layer switching works")

    # Test duplicate layer prevention
    bg_id2 = engine.execute_command({"action": "layer", "label": "Background"})
    assert bg_id == bg_id2, "Should return existing layer, not create duplicate"
    print(f"  ✓ duplicate layer prevention works")

    # Test visibility toggle
    engine.execute_command({"action": "layer_visibility", "label": "Effects", "visible": False})
    fx_layer = engine._find_layer_by_label("Effects")
    assert "display:none" in fx_layer.get("style", ""), "Effects layer should be hidden"
    print(f"  ✓ layer visibility toggle works")

    # Test lock
    engine.execute_command({"action": "layer_lock", "label": "Background", "locked": True})
    ns = "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd}insensitive"
    assert bg_layer.get(ns) == "true", "Background should be locked"
    print(f"  ✓ layer locking works\n")


def test_save_output():
    """Test saving the generated SVG."""
    print("── Test: SVG Output ──")
    svg = create_test_svg()
    engine = SVGEngine(svg)

    # Build a little scene
    engine.execute_command({"action": "rect", "x": 0, "y": 400, "width": 512, "height": 112, "fill": "#4a7c3f"})
    engine.execute_command({"action": "rect", "x": 0, "y": 0, "width": 512, "height": 400, "fill": "#87CEEB"})
    engine.execute_command({"action": "circle", "cx": 400, "cy": 80, "r": 50, "fill": "#FFD700"})
    engine.execute_command({
        "action": "path",
        "d": "M200,400 L220,300 L240,400 Z",
        "fill": "#2d5a1e"
    })

    # Save
    output_path = Path(__file__).parent / "test_output.svg"
    tree = etree.ElementTree(svg)
    tree.write(str(output_path), pretty_print=True, xml_declaration=True, encoding="utf-8")
    print(f"  ✓ saved to {output_path}")
    print(f"  Open this file in Inkscape to verify!\n")


def main():
    print("=" * 50)
    print("  ✦ Inkpilot Core Engine Tests")
    print("=" * 50)
    print()

    tests = [
        test_shape_commands,
        test_pixel_art,
        test_transforms,
        test_layer_management,
        test_context_builder,
        test_response_parser,
        test_svg_insertion,
        test_sprite_sheet,
        test_save_output,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
            failed += 1

    print("=" * 50)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
