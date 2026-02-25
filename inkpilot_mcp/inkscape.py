"""
Inkpilot MCP — Inkscape Connector
Opens Inkscape for the final result. Live preview uses browser (SSE).
"""
import os
import sys
import subprocess
import shutil

# Flags to prevent black console windows on Windows
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def find_inkscape():
    """Find the Inkscape executable on any platform."""
    for name in ["inkscape", "inkscape.com", "inkscape.exe"]:
        ink = shutil.which(name)
        if ink:
            return ink

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["where", "inkscape.exe"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0:
                path = result.stdout.strip().split("\n")[0].strip()
                if os.path.isfile(path):
                    return path
        except Exception:
            pass

        candidates = []
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", "")
        local = os.environ.get("LOCALAPPDATA", "")

        for base in [pf, pf86]:
            if base:
                candidates.append(os.path.join(base, "Inkscape", "bin", "inkscape.exe"))
        if local:
            candidates.append(os.path.join(local, "Programs", "Inkscape", "bin", "inkscape.exe"))

        for winapps_base in [
            os.path.join(pf, "WindowsApps"),
            os.path.join(local, "Microsoft", "WindowsApps") if local else "",
        ]:
            if winapps_base and os.path.isdir(winapps_base):
                try:
                    for entry in os.listdir(winapps_base):
                        if "inkscape" in entry.lower():
                            exe = os.path.join(winapps_base, entry, "VFS",
                                               "ProgramFilesX64", "Inkscape",
                                               "bin", "inkscape.exe")
                            if os.path.isfile(exe):
                                candidates.append(exe)
                except PermissionError:
                    pass

        if not any(os.path.isfile(c) for c in candidates):
            try:
                ps = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-AppxPackage *inkscape* | Select-Object -First 1).InstallLocation"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=_NO_WINDOW,
                )
                if ps.returncode == 0 and ps.stdout.strip():
                    store_dir = ps.stdout.strip()
                    exe = os.path.join(store_dir, "VFS", "ProgramFilesX64",
                                       "Inkscape", "bin", "inkscape.exe")
                    if os.path.isfile(exe):
                        candidates.append(exe)
            except Exception:
                pass

        for c in candidates:
            if os.path.isfile(c):
                return c

    elif sys.platform == "darwin":
        mac = "/Applications/Inkscape.app/Contents/MacOS/inkscape"
        if os.path.isfile(mac):
            return mac

    return None


def run_inkscape_actions(svg_path, actions_str, output_path=None):
    """Run Inkscape CLI actions on an SVG file.
    
    actions_str: semicolon-separated action commands, e.g.
      "select-by-id:rect_001,rect_002;path-union;export-filename:/path/out.svg;export-overwrite;export-plain-svg;export-do;"
    
    If output_path is None, modifies the file in-place.
    Returns (success: bool, message: str)
    """
    exe = find_inkscape()
    if not exe:
        return False, "Inkscape not found"
    
    out = output_path or svg_path
    
    # Build the full action string with export at the end
    # If the user already included export commands, use as-is
    if "export-do" not in actions_str:
        # Append export commands to save the result
        actions_str = actions_str.rstrip(";")
        actions_str += f";export-filename:{out};export-overwrite;export-plain-svg;export-do;"
    
    cmd = [
        exe,
        svg_path,
        "--batch-process",
        f"--actions={actions_str}",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
            creationflags=_NO_WINDOW,
        )
        
        # Inkscape outputs status to stderr
        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""
        
        if result.returncode == 0:
            return True, f"Actions completed. {stderr}"
        else:
            return False, f"Inkscape error (code {result.returncode}): {stderr or stdout}"
    except subprocess.TimeoutExpired:
        return False, "Inkscape action timed out (30s limit)"
    except Exception as e:
        return False, f"Error running Inkscape: {e}"


def open_in_inkscape(svg_path):
    """Open an SVG file in Inkscape (one time, for editing the final result)."""
    exe = find_inkscape()
    if not exe:
        return "Inkscape not found"
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [exe, svg_path],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen([exe, svg_path], start_new_session=True)
        return f"Opened in Inkscape"
    except Exception as e:
        return f"Error: {e}"
