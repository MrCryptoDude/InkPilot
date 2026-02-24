#!/usr/bin/env python3
"""
Inkpilot — One-click installer.
Configures Claude Desktop to talk to Inkscape via Inkpilot MCP bridge.
"""
import json
import os
import sys
import subprocess
from pathlib import Path


def get_claude_config_path():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "claude" / "claude_desktop_config.json"


def install():
    project_dir = Path(__file__).parent.resolve()
    python_exe = sys.executable

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     ✦ Inkpilot — Installer               ║")
    print("  ║     Claude ↔ Inkscape Bridge              ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    # 1. Install deps
    print("  [1/4] Installing dependencies...")
    subprocess.check_call([python_exe, "-m", "pip", "install", "mcp[cli]", "lxml", "--quiet"])
    print("        ✓ Done")

    # 2. Verify
    print("  [2/4] Verifying...")
    from inkpilot_mcp.canvas import SVGCanvas
    c = SVGCanvas(64, 64)
    c.draw_rect(0, 0, 32, 32, fill="#ff0000")
    assert "rect" in c.to_svg()
    print("        ✓ Canvas engine works")

    from inkpilot_mcp.inkscape import find_inkscape
    ink = find_inkscape()
    if ink:
        print(f"        ✓ Inkscape found: {ink}")
    else:
        print("        ⚠ Inkscape not found (install it first)")

    # 3. Configure Claude Desktop
    print("  [3/4] Configuring Claude Desktop...")
    config_path = get_claude_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["inkpilot"] = {
        "command": str(python_exe),
        "args": ["-m", "inkpilot_mcp"],
        "cwd": str(project_dir),
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"        ✓ Config written to: {config_path}")

    # 4. Done
    print("  [4/4] Ready!")
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║  ✅  INSTALLATION COMPLETE                ║")
    print("  ╚══════════════════════════════════════════╝")
    print()
    print("  What to do now:")
    print()
    print("  1. QUIT Claude Desktop completely (system tray → Quit)")
    print("  2. Reopen Claude Desktop")
    print("  3. You should see a 🔨 hammer icon — that's Inkpilot!")
    print("  4. Open Inkscape")
    print("  5. Tell Claude: 'Draw a pixel art sword using inkpilot'")
    print("  6. Watch it appear in Inkscape! ✨")
    print()
    print("  Files:")
    print(f"    Working SVG: {Path.home() / '.inkpilot' / 'canvas.svg'}")
    print(f"    Saved SVGs:  {Path.home() / '.inkpilot' / 'output'}")
    print(f"    Config:      {config_path}")
    print()


if __name__ == "__main__":
    install()
