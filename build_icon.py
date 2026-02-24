"""
Convert Inkpilot SVG icon to ICO using Inkscape CLI.
"""
import subprocess
import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
    from PIL import Image

PROJECT_DIR = Path(__file__).parent.resolve()
HOME = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
ICON_SVG = HOME / ".inkpilot" / "output" / "inkpilot_icon.svg"
ASSETS_DIR = PROJECT_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

SIZES = [16, 32, 48, 64, 128, 256]

# Reuse the same detection from our MCP module
sys.path.insert(0, str(PROJECT_DIR))
from inkpilot_mcp.inkscape import find_inkscape


def main():
    if not ICON_SVG.exists():
        print(f"  ✗ Icon SVG not found: {ICON_SVG}")
        print("    Ask Claude to draw the icon first using Inkpilot.")
        sys.exit(1)

    ink = find_inkscape()
    if not ink:
        print("  ✗ Inkscape not found. Cannot export PNGs.")
        print("    Make sure Inkscape is installed (Store or regular).")
        sys.exit(1)

    print(f"  Using Inkscape: {ink}")
    print(f"  Source: {ICON_SVG}")
    print()

    images = []
    for size in SIZES:
        png_path = ASSETS_DIR / f"icon_{size}.png"
        cmd = [
            ink,
            str(ICON_SVG),
            "--export-type=png",
            f"--export-filename={png_path}",
            f"--export-width={size}",
            f"--export-height={size}",
            "--export-background-opacity=0",
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

        if png_path.exists():
            img = Image.open(str(png_path)).convert("RGBA")
            images.append(img)
            print(f"  ✓ {size}x{size}")
        else:
            print(f"  ✗ Failed: {size}x{size}")

    if not images:
        print("\n  ✗ No images generated!")
        sys.exit(1)

    # Save ICO
    ico_path = ASSETS_DIR / "inkpilot.ico"
    images[0].save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in SIZES[:len(images)]],
        append_images=images[1:],
    )
    print(f"\n  ✅ ICO saved: {ico_path}")

    # Also keep the 256px PNG
    png256 = ASSETS_DIR / "inkpilot_256.png"
    images[-1].save(str(png256))
    print(f"  ✅ PNG saved: {png256}")


if __name__ == "__main__":
    main()
