"""
Inkpilot — Setup
Installs dependencies, configures Claude Desktop, creates Start Menu shortcut.
"""
import sys
import os
import subprocess
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"


def main():
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║     ✦ Inkpilot Setup                         ║")
    print("  ║     Claude ↔ Inkscape Bridge                  ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    # 1. Install deps
    print("  [1/4] Installing packages...")
    subprocess.check_call([python, "-m", "pip", "install",
                           "mcp[cli]", "lxml", "pystray", "Pillow", "--quiet"])
    print("        ✓ Done")

    # 2. Verify
    print("  [2/4] Verifying...")
    sys.path.insert(0, str(PROJECT_DIR))
    from inkpilot_mcp.canvas import SVGCanvas
    c = SVGCanvas(64, 64)
    c.draw_rect(0, 0, 32, 32, fill="#f00")
    assert "rect" in c.to_svg()
    print("        ✓ Canvas engine works")

    from inkpilot_mcp.inkscape import find_inkscape
    ink = find_inkscape()
    print(f"        ✓ Inkscape: {'found' if ink else 'NOT FOUND (install it)'}")

    # 3. Configure Claude Desktop
    print("  [3/4] Configuring Claude Desktop...")
    if sys.platform == "win32":
        config_path = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        config_path = Path.home() / ".config" / "claude" / "claude_desktop_config.json"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            pass

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["inkpilot"] = {
        "command": python,
        "args": [str(PROJECT_DIR / "run_mcp.py")],
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"        ✓ Config: {config_path}")

    # 4. Create Start Menu shortcut (Windows)
    print("  [4/4] Creating shortcut...")
    if sys.platform == "win32":
        try:
            _create_windows_shortcut(python)
            print("        ✓ Start Menu shortcut created")
        except Exception as e:
            print(f"        ⚠ Shortcut failed: {e}")
            print(f"        You can run Inkpilot.bat instead")
    else:
        print("        ⚠ Shortcuts not supported on this OS yet")
        print(f"        Run: python {PROJECT_DIR / 'inkpilot_tray.py'}")

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  ✅ Setup complete!                           ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print("  How to use:")
    print("  1. Launch 'Inkpilot' from Start Menu (or run Inkpilot.bat)")
    print("  2. Look for the ✦ icon in your system tray")
    print("  3. Restart Claude Desktop so it picks up the connection")
    print("  4. Tell Claude: 'Draw a pixel art character using inkpilot'")
    print("  5. Watch it appear in Inkscape!")
    print()


def _create_windows_shortcut(python_exe):
    """Create a Start Menu shortcut on Windows."""
    import ctypes.wintypes

    # Get Start Menu path
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    shortcut_path = start_menu / "Inkpilot.lnk"

    # Use PowerShell to create shortcut (most reliable)
    bat_path = str(PROJECT_DIR / "Inkpilot.bat")
    icon_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{bat_path}"
$Shortcut.WorkingDirectory = "{PROJECT_DIR}"
$Shortcut.Description = "Inkpilot - Claude to Inkscape Bridge"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
'''
    subprocess.run(["powershell", "-Command", icon_script],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

    # Also create desktop shortcut
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    desktop_shortcut = desktop / "Inkpilot.lnk"
    desktop_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{desktop_shortcut}")
$Shortcut.TargetPath = "{bat_path}"
$Shortcut.WorkingDirectory = "{PROJECT_DIR}"
$Shortcut.Description = "Inkpilot - Claude to Inkscape Bridge"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
'''
    subprocess.run(["powershell", "-Command", desktop_script],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    main()
