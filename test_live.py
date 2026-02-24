"""Quick test — run the canvas + live server without MCP to verify everything works."""
import sys
import os
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inkpilot_mcp.canvas import SVGCanvas
from inkpilot_mcp.live_server import LiveServer

print("✦ Inkpilot MCP — Live Preview Test")
print("=" * 40)

# Create canvas
canvas = SVGCanvas(256, 256)

# Start live server
live = LiveServer(canvas, port=7878)
url = live.start()
print(f"🌐 Live preview: {url}")
webbrowser.open(url)

# Simulate Claude drawing a pixel art sword
print("\n🎨 Drawing a pixel art sword (watch your browser!)...\n")
time.sleep(1)

# Layer: Shadow
canvas.create_layer("Shadow")
canvas.draw_pixel_region([
    [8, 30, "#1a1a2e"], [9, 30, "#1a1a2e"], [10, 30, "#1a1a2e"],
    [7, 31, "#1a1a2e"], [8, 31, "#1a1a2e"], [9, 31, "#1a1a2e"],
    [10, 31, "#1a1a2e"], [11, 31, "#1a1a2e"],
], size=8, label="shadow")
print("  ✓ Shadow layer")
time.sleep(0.5)

# Layer: Blade
canvas.create_layer("Blade")
blade_pixels = []
for y in range(4, 22):
    w = 2 if y < 8 else (3 if y < 16 else 4)
    cx = 9
    for x in range(cx - w//2, cx + (w+1)//2):
        shade = "#e8e8e8" if x == cx else "#c0c0c0"
        if y < 6:
            shade = "#f0f0f0"  # tip highlight
        blade_pixels.append([x, y, shade])
    # Edge highlight
    blade_pixels.append([cx - w//2, y, "#d4d4d4"])
canvas.draw_pixel_region(blade_pixels, size=8, label="blade_fill")
print("  ✓ Blade drawn")
time.sleep(0.5)

# Blade outline
outline = []
for y in range(4, 22):
    w = 2 if y < 8 else (3 if y < 16 else 4)
    cx = 9
    outline.append([cx - w//2 - 1, y, "#555555"])
    outline.append([cx + (w+1)//2, y, "#555555"])
outline.append([9, 3, "#555555"])  # tip
canvas.draw_pixel_region(outline, size=8, label="blade_outline")
print("  ✓ Blade outline")
time.sleep(0.5)

# Layer: Guard
canvas.create_layer("Guard")
guard_pixels = []
for x in range(6, 14):
    guard_pixels.append([x, 22, "#8B6914"])
    guard_pixels.append([x, 23, "#704214"])
canvas.draw_pixel_region(guard_pixels, size=8, label="guard")
print("  ✓ Guard drawn")
time.sleep(0.5)

# Layer: Hilt
canvas.create_layer("Hilt")
hilt_pixels = []
for y in range(24, 29):
    for x in range(8, 12):
        color = "#8B4513" if (x + y) % 2 == 0 else "#A0522D"
        hilt_pixels.append([x, y, color])
canvas.draw_pixel_region(hilt_pixels, size=8, label="hilt_wrap")
print("  ✓ Hilt drawn")
time.sleep(0.5)

# Pommel
canvas.create_layer("Pommel")
pommel = [
    [8, 29, "#DAA520"], [9, 29, "#FFD700"], [10, 29, "#DAA520"], [11, 29, "#B8860B"],
    [9, 30, "#B8860B"], [10, 30, "#B8860B"],
]
canvas.draw_pixel_region(pommel, size=8, label="pommel")
print("  ✓ Pommel drawn")

# Save
output_dir = os.path.join(os.path.expanduser("~"), ".inkpilot", "output")
os.makedirs(output_dir, exist_ok=True)
path = canvas.save(os.path.join(output_dir, "test_sword.svg"))
print(f"\n📄 Saved to: {path}")
print(f"📊 State:\n{canvas.get_state()}")
print(f"\n✅ Test complete! Check the browser window.")
print("   Press Ctrl+C to stop the server.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopped.")
    live.stop()
