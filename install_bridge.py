"""
Install the Inkpilot Bridge extension into Inkscape.

Copies inkpilot_bridge.py and inkpilot_bridge.inx to Inkscape's
extensions directory so it appears in Extensions → Inkpilot menu.

Usage:
  python install_bridge.py
"""
import os
import sys
import shutil
import platform


def get_inkscape_extensions_dir():
    """Find Inkscape's user extensions directory."""
    system = platform.system()
    
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return os.path.join(appdata, "inkscape", "extensions")
    
    elif system == "Darwin":  # macOS
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support",
                           "org.inkscape.Inkscape", "config", "inkscape", "extensions")
    
    else:  # Linux
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "inkscape", "extensions")
    
    return None


def install():
    """Install the bridge extension."""
    ext_dir = get_inkscape_extensions_dir()
    
    if not ext_dir:
        print("ERROR: Could not determine Inkscape extensions directory.")
        print("Please copy bridge/inkpilot_bridge.py and bridge/inkpilot_bridge.inx")
        print("to your Inkscape extensions folder manually.")
        return False
    
    os.makedirs(ext_dir, exist_ok=True)
    
    # Source files
    bridge_dir = os.path.dirname(os.path.abspath(__file__))
    src_py = os.path.join(bridge_dir, "bridge", "inkpilot_bridge.py")
    src_inx = os.path.join(bridge_dir, "bridge", "inkpilot_bridge.inx")
    
    # Check source exists
    if not os.path.isfile(src_py):
        # Try relative to this script
        src_py = os.path.join(os.path.dirname(bridge_dir), "bridge", "inkpilot_bridge.py")
        src_inx = os.path.join(os.path.dirname(bridge_dir), "bridge", "inkpilot_bridge.inx")
    
    if not os.path.isfile(src_py):
        print(f"ERROR: Cannot find inkpilot_bridge.py")
        return False
    
    # Copy files
    dst_py = os.path.join(ext_dir, "inkpilot_bridge.py")
    dst_inx = os.path.join(ext_dir, "inkpilot_bridge.inx")
    
    shutil.copy2(src_py, dst_py)
    print(f"Installed: {dst_py}")
    
    shutil.copy2(src_inx, dst_inx)
    print(f"Installed: {dst_inx}")
    
    print(f"\nBridge extension installed to: {ext_dir}")
    print(f"\nNext steps:")
    print(f"  1. Restart Inkscape")
    print(f"  2. Go to Extensions → Inkpilot → Inkpilot Bridge")
    print(f"  3. Click Apply — this starts the bridge server")
    print(f"  4. Claude can now control Inkscape natively!")
    
    return True


if __name__ == "__main__":
    install()
