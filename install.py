#!/usr/bin/env python3
"""
Inkpilot Installer
Copies extension files to the Inkscape extensions directory.
"""
import os
import sys
import shutil
import platform
from pathlib import Path


def find_inkscape_extensions_dir() -> Path:
    """Find the Inkscape user extensions directory."""
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        paths = [
            Path(appdata) / "inkscape" / "extensions",
            Path.home() / "AppData" / "Roaming" / "inkscape" / "extensions",
        ]
    elif system == "Darwin":  # macOS
        paths = [
            Path.home() / ".config" / "inkscape" / "extensions",
            Path.home() / "Library" / "Application Support" / "org.inkscape.Inkscape" / "config" / "inkscape" / "extensions",
        ]
    else:  # Linux
        paths = [
            Path.home() / ".config" / "inkscape" / "extensions",
        ]

    # Try to find existing directory
    for p in paths:
        if p.exists():
            return p

    # Create the most likely one
    default = paths[0]
    default.mkdir(parents=True, exist_ok=True)
    return default


def install():
    """Install Inkpilot to Inkscape extensions directory."""
    src_dir = Path(__file__).parent
    ext_dir = find_inkscape_extensions_dir()

    print(f"✦ Inkpilot Installer")
    print(f"  Source:      {src_dir}")
    print(f"  Destination: {ext_dir}")
    print()

    # Files to copy
    files_to_copy = [
        "inkpilot.inx",
        "inkpilot_extension.py",
    ]

    # Directory to copy
    inkpilot_pkg_src = src_dir / "inkpilot"
    inkpilot_pkg_dst = ext_dir / "inkpilot"

    # Copy main files
    for fname in files_to_copy:
        src = src_dir / fname
        dst = ext_dir / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  ✓ Copied {fname}")
        else:
            print(f"  ⚠ Missing: {fname}")

    # Copy package directory
    if inkpilot_pkg_src.exists():
        if inkpilot_pkg_dst.exists():
            shutil.rmtree(inkpilot_pkg_dst)
        shutil.copytree(inkpilot_pkg_src, inkpilot_pkg_dst)
        print(f"  ✓ Copied inkpilot/ package")
    else:
        print(f"  ⚠ Missing: inkpilot/ directory")

    print()
    print("✦ Installation complete!")
    print()
    print("Next steps:")
    print("  1. Set your API key:")
    print('     Create ~/.inkpilot/config.json with: {"api_key": "sk-ant-..."}')
    print("     Or set ANTHROPIC_API_KEY environment variable")
    print()
    print("  2. Restart Inkscape")
    print()
    print("  3. Find Inkpilot in: Extensions → Inkpilot → Inkpilot - AI Copilot")
    print()


def uninstall():
    """Remove Inkpilot from Inkscape extensions directory."""
    ext_dir = find_inkscape_extensions_dir()

    files_to_remove = [
        ext_dir / "inkpilot.inx",
        ext_dir / "inkpilot_extension.py",
    ]
    dirs_to_remove = [
        ext_dir / "inkpilot",
    ]

    print("✦ Uninstalling Inkpilot...")

    for f in files_to_remove:
        if f.exists():
            f.unlink()
            print(f"  ✓ Removed {f.name}")

    for d in dirs_to_remove:
        if d.exists():
            shutil.rmtree(d)
            print(f"  ✓ Removed {d.name}/")

    print("✦ Uninstall complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall()
    else:
        install()
