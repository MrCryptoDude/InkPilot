"""
Build Inkpilot into a standalone Windows executable.
Uses PyInstaller to bundle everything into a single folder.
Then Inno Setup creates the installer .exe.
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = PROJECT_DIR / "assets"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"


def check_tools():
    """Verify required tools are available."""
    # PyInstaller
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"])
        print("  ✓ PyInstaller installed")

    # Check icon exists
    ico = ASSETS_DIR / "inkpilot.ico"
    if not ico.exists():
        print("  ⚠ Icon not found. Building icon first...")
        subprocess.check_call([sys.executable, str(PROJECT_DIR / "build_icon.py")])

    # Check Inno Setup
    inno = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if os.path.isfile(inno):
        print(f"  ✓ Inno Setup found")
        return inno
    else:
        print("  ⚠ Inno Setup not found (install from https://jrsoftware.org/isdownload.php)")
        print("    The .exe will still be built, just no installer wrapper.")
        return None


def build_exe():
    """Bundle with PyInstaller."""
    print("\n📦 Building executable...")
    ico = ASSETS_DIR / "inkpilot.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Inkpilot",
        f"--icon={ico}",
        "--noconsole",               # No terminal window
        "--onedir",                  # Folder with exe + deps
        "--clean",
        "--noconfirm",
        # Include our packages
        "--add-data", f"{PROJECT_DIR / 'inkpilot_mcp'};inkpilot_mcp",
        "--add-data", f"{PROJECT_DIR / 'run_mcp.py'};.",
        "--add-data", f"{ASSETS_DIR / 'inkpilot.ico'};assets",
        # CustomTkinter theme files
        "--collect-all=customtkinter",
        # Hidden imports
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "--hidden-import=lxml",
        "--hidden-import=lxml.etree",
        "--hidden-import=mcp",
        "--hidden-import=mcp.server",
        "--hidden-import=mcp.server.fastmcp",
        # Entry point
        str(PROJECT_DIR / "inkpilot_tray.py"),
    ]

    subprocess.check_call(cmd, cwd=str(PROJECT_DIR))
    print(f"\n✅ Executable built: {DIST_DIR / 'Inkpilot' / 'Inkpilot.exe'}")


def build_installer(inno_path):
    """Create Windows installer with Inno Setup."""
    print("\n📦 Building Windows installer...")
    iss_file = PROJECT_DIR / "installer.iss"
    subprocess.check_call([inno_path, str(iss_file)])
    print(f"\n✅ Installer built: {DIST_DIR / 'InkpilotSetup.exe'}")


def main():
    print("=" * 50)
    print("  ✦ Inkpilot — Build System")
    print("=" * 50)
    print("\n🔍 Checking tools...")

    inno = check_tools()
    build_exe()

    if inno:
        build_installer(inno)
    else:
        print("\n⚠ Skipping installer (Inno Setup not found).")
        print("  You can still distribute the dist/Inkpilot/ folder directly.")

    print("\n" + "=" * 50)
    print("  Build complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
