"""
Inkpilot — Desktop App
Hub for AI creative tools. Bridges Claude to Blender, Inkscape, and more.
"""
import sys
import os
import json
import threading
import subprocess
import webbrowser
import time
import shutil
import glob
from pathlib import Path

# -- Paths --

if getattr(sys, '_MEIPASS', None):
    _exe_dir = Path(sys.executable).parent.resolve()
    _candidate = _exe_dir.parent.parent
    if (_candidate / "run_mcp.py").exists():
        PROJECT_DIR = _candidate
    else:
        PROJECT_DIR = _exe_dir
else:
    PROJECT_DIR = Path(__file__).parent.resolve()

HOME = Path(os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or Path.home())
WORK_DIR = HOME / ".inkpilot"
OUTPUT_DIR = WORK_DIR / "output"
CONFIG_FILE = WORK_DIR / "config.json"
WORK_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_DIR))


# -- Deps --

def _ensure_deps():
    missing = []
    try: import customtkinter
    except ImportError: missing.append("customtkinter")
    try: from PIL import Image
    except ImportError: missing.append("Pillow")
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])

_ensure_deps()

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk


# -- Config --

def load_config():
    defaults = {"output_dir": str(OUTPUT_DIR), "blender_enabled": False}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return {**defaults, **json.load(f)}
        except: pass
    return defaults

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except: pass


# -- Claude Desktop Config --

def get_claude_config_path():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "claude" / "claude_desktop_config.json"

def is_installed():
    config_path = get_claude_config_path()
    if not config_path.exists(): return False
    try:
        with open(config_path) as f:
            config = json.load(f)
        return "inkpilot" in config.get("mcpServers", {})
    except: return False

def install_to_claude():
    config_path = get_claude_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except: config = {}
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    run_script = str(PROJECT_DIR / "run_mcp.py")
    venv_python = str(PROJECT_DIR / ".venv" / "Scripts" / "python.exe")
    system_python = str(Path(sys.executable))
    python_exe = venv_python if Path(venv_python).exists() else system_python
    config["mcpServers"]["inkpilot"] = {"command": python_exe, "args": [run_script]}
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    return True

def uninstall_from_claude():
    config_path = get_claude_config_path()
    if not config_path.exists(): return
    try:
        with open(config_path) as f:
            config = json.load(f)
        if "inkpilot" in config.get("mcpServers", {}):
            del config["mcpServers"]["inkpilot"]
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
    except: pass


# -- Find Blender --

def find_blender():
    """Find Blender executable on the system."""
    # Check PATH first
    blender = shutil.which("blender")
    if blender: return blender

    if sys.platform == "win32":
        # Common Windows locations
        candidates = []

        # Program Files
        for pf in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if pf:
                # Check versioned folders
                pattern = os.path.join(pf, "Blender Foundation", "Blender*", "blender.exe")
                candidates.extend(glob.glob(pattern))

        # Steam
        steam_paths = [
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "steamapps", "common", "Blender", "blender.exe"),
            os.path.join("D:\\", "SteamLibrary", "steamapps", "common", "Blender", "blender.exe"),
        ]
        candidates.extend(steam_paths)

        # Microsoft Store
        local_apps = os.path.join(HOME, "AppData", "Local", "Microsoft", "WindowsApps")
        if os.path.isdir(local_apps):
            pattern = os.path.join(local_apps, "blender.exe")
            candidates.extend(glob.glob(pattern))

        for c in candidates:
            if os.path.isfile(c):
                return c

    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
        ]
        for c in candidates:
            if os.path.isfile(c): return c

    else:  # Linux
        candidates = ["/usr/bin/blender", "/snap/bin/blender",
                     os.path.expanduser("~/blender/blender")]
        for c in candidates:
            if os.path.isfile(c): return c

    return None


def get_blender_addons_dir():
    """Get Blender's user addons directory."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            base = os.path.join(appdata, "Blender Foundation", "Blender")
            if os.path.isdir(base):
                versions = sorted(os.listdir(base), reverse=True)
                if versions:
                    d = os.path.join(base, versions[0], "scripts", "addons")
                    os.makedirs(d, exist_ok=True)
                    return d
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Blender")
        if os.path.isdir(base):
            versions = sorted(os.listdir(base), reverse=True)
            if versions:
                return os.path.join(base, versions[0], "scripts", "addons")
    else:
        base = os.path.expanduser("~/.config/blender")
        if os.path.isdir(base):
            versions = sorted(os.listdir(base), reverse=True)
            if versions:
                return os.path.join(base, versions[0], "scripts", "addons")
    return None


def install_blender_addon():
    """Copy addon.py to Blender's addons directory."""
    addons_dir = get_blender_addons_dir()
    if not addons_dir:
        return False, "Could not find Blender addons directory"

    os.makedirs(addons_dir, exist_ok=True)
    src = PROJECT_DIR / "blender" / "addon.py"
    dst = os.path.join(addons_dir, "inkpilot_bridge.py")

    if not src.exists():
        return False, f"Addon source not found: {src}"

    shutil.copy2(str(src), dst)
    return True, f"Installed to {dst}"


def uninstall_blender_addon():
    """Remove addon from Blender's addons directory."""
    addons_dir = get_blender_addons_dir()
    if not addons_dir: return
    dst = os.path.join(addons_dir, "inkpilot_bridge.py")
    if os.path.isfile(dst):
        os.remove(dst)


def is_blender_addon_installed():
    """Check if our addon is in Blender's addons directory."""
    addons_dir = get_blender_addons_dir()
    if not addons_dir: return False
    return os.path.isfile(os.path.join(addons_dir, "inkpilot_bridge.py"))


# -- Icon --

def _find_icon_path():
    candidates = [
        PROJECT_DIR / "assets" / "inkpilot.ico",
        PROJECT_DIR / "assets" / "inkpilot_256.png",
    ]
    if getattr(sys, '_MEIPASS', None):
        candidates.insert(0, Path(sys._MEIPASS) / "assets" / "inkpilot.ico")
    for c in candidates:
        if c and c.exists(): return c
    return None


# -- Colors --

C = {
    "bg":           "#0f1117",
    "card":         "#1a1d27",
    "card_border":  "#2a2d3a",
    "accent":       "#3b82f6",
    "accent_hover": "#2563eb",
    "green":        "#22c55e",
    "green_dim":    "#16653a",
    "red":          "#ef4444",
    "orange":       "#f59e0b",
    "text":         "#e2e8f0",
    "text_dim":     "#64748b",
    "text_muted":   "#475569",
    "separator":    "#1e2130",
}


# ==================================================================
#  DESKTOP APP
# ==================================================================

class InkpilotApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.connected = is_installed()
        self.blender_found = find_blender() is not None
        self.blender_addon_installed = is_blender_addon_installed()
        self.output_dir = Path(self.config.get("output_dir", str(OUTPUT_DIR)))

        # Window
        self.title("Inkpilot")
        self.geometry("420x580")
        self.minsize(380, 520)
        self.configure(fg_color=C["bg"])
        self.resizable(True, True)

        ico = _find_icon_path()
        if ico:
            try:
                if str(ico).endswith(".ico"):
                    self.iconbitmap(str(ico))
                else:
                    img = ImageTk.PhotoImage(Image.open(str(ico)).resize((32, 32)))
                    self.iconphoto(True, img)
            except: pass

        # Build UI
        self._build_header()
        self._build_setup_guide()
        self._build_status_cards()
        self._build_settings()
        self._build_actions()
        self._build_footer()

        # Auto-install on first launch
        if not self.connected:
            self._connect()

        self._refresh_status()

    # -- Header --

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)

        title_frame = ctk.CTkFrame(inner, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(title_frame, text="Inkpilot", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=C["accent"]).pack(side="left")
        ctk.CTkLabel(title_frame, text="  v2.0", font=ctk.CTkFont(size=12),
                     text_color=C["text_dim"]).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(inner, text="AI Creative Hub", font=ctk.CTkFont(size=13),
                     text_color=C["text_muted"]).pack(side="right")

    # -- Setup Guide --

    def _build_setup_guide(self):
        container = ctk.CTkFrame(self, fg_color=C["card"], border_color=C["accent"],
                                 border_width=1, corner_radius=10)
        container.pack(fill="x", padx=16, pady=(16, 0))

        ctk.CTkLabel(container, text="Getting Started", font=ctk.CTkFont(size=11),
                     text_color=C["accent"]).pack(anchor="w", padx=16, pady=(10, 8))

        steps = [
            ("1", "Turn on Blender Bridge", "Toggle the switch below to install the addon"),
            ("2", "Open Blender", "Go to Edit > Preferences > Add-ons"),
            ("3", "Enable the addon", "Search 'Inkpilot', tick the checkbox to enable"),
            ("4", "Close & reopen Claude", "Quit from system tray, then reopen"),
        ]

        for num, title, desc in steps:
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 6))

            ctk.CTkLabel(row, text=num, width=24, height=24, corner_radius=12,
                         fg_color=C["accent"], text_color="#ffffff",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))

            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="x")
            ctk.CTkLabel(text_frame, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=C["text"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(text_frame, text=desc, font=ctk.CTkFont(size=11),
                         text_color=C["text_dim"], anchor="w").pack(anchor="w")

        # Turn off instructions
        off_frame = ctk.CTkFrame(container, fg_color="transparent")
        off_frame.pack(fill="x", padx=16, pady=(4, 10))
        ctk.CTkLabel(off_frame,
                     text="To turn off: switch off the toggle and restart Claude.",
                     font=ctk.CTkFont(size=11, slant="italic"),
                     text_color=C["text_muted"]).pack(anchor="w")
        ctk.CTkLabel(off_frame,
                     text="In Blender, press N in viewport to see the Inkpilot panel.",
                     font=ctk.CTkFont(size=11, slant="italic"),
                     text_color=C["text_muted"]).pack(anchor="w")

    # -- Status Cards --

    def _build_status_cards(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=16, pady=(16, 0))

        # Claude card
        self.llm_card_wrapper = ctk.CTkFrame(container, fg_color=C["card"],
                                              border_color=C["card_border"], border_width=1, corner_radius=10)
        self.llm_card_wrapper.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self.llm_card_wrapper, text="LLM Connection", font=ctk.CTkFont(size=11),
                     text_color=C["text_muted"]).pack(anchor="w", padx=16, pady=(10, 4))

        llm_content = ctk.CTkFrame(self.llm_card_wrapper, fg_color="transparent")
        llm_content.pack(fill="x", padx=16, pady=(0, 12))

        self.llm_dot = ctk.CTkLabel(llm_content, text="", width=10, height=10, corner_radius=5,
                                     fg_color=C["green"] if self.connected else C["red"])
        self.llm_dot.pack(side="left", padx=(0, 8))

        llm_text = ctk.CTkFrame(llm_content, fg_color="transparent")
        llm_text.pack(side="left", fill="x")

        self.llm_label = ctk.CTkLabel(llm_text,
                                       text="Claude Desktop (MCP)" if self.connected else "Not connected",
                                       font=ctk.CTkFont(size=14, weight="bold"), text_color=C["text"])
        self.llm_label.pack(anchor="w")

        self.llm_detail = ctk.CTkLabel(llm_text,
                                        text="MCP server registered" if self.connected else "Click Connect below",
                                        font=ctk.CTkFont(size=12), text_color=C["text_dim"])
        self.llm_detail.pack(anchor="w")

        # Blender card
        self.blender_card_wrapper = ctk.CTkFrame(container, fg_color=C["card"],
                                                   border_color=C["card_border"], border_width=1, corner_radius=10)
        self.blender_card_wrapper.pack(fill="x", pady=(0, 0))

        ctk.CTkLabel(self.blender_card_wrapper, text="Blender", font=ctk.CTkFont(size=11),
                     text_color=C["text_muted"]).pack(anchor="w", padx=16, pady=(10, 4))

        bl_content = ctk.CTkFrame(self.blender_card_wrapper, fg_color="transparent")
        bl_content.pack(fill="x", padx=16, pady=(0, 12))

        self.bl_dot = ctk.CTkLabel(bl_content, text="", width=10, height=10, corner_radius=5,
                                    fg_color=C["green"] if self.blender_found else C["orange"])
        self.bl_dot.pack(side="left", padx=(0, 8))

        bl_text = ctk.CTkFrame(bl_content, fg_color="transparent")
        bl_text.pack(side="left", fill="x")

        bl_path = find_blender()
        self.bl_label = ctk.CTkLabel(bl_text,
                                      text="Blender - Installed" if self.blender_found else "Blender - Not found",
                                      font=ctk.CTkFont(size=14, weight="bold"), text_color=C["text"])
        self.bl_label.pack(anchor="w")

        detail_text = str(bl_path) if bl_path else "Install from blender.org"
        if len(detail_text) > 45:
            detail_text = "..." + detail_text[-42:]

        self.bl_detail = ctk.CTkLabel(bl_text, text=detail_text,
                                       font=ctk.CTkFont(size=11), text_color=C["text_dim"])
        self.bl_detail.pack(anchor="w")

    # -- Settings --

    def _build_settings(self):
        container = ctk.CTkFrame(self, fg_color=C["card"], border_color=C["card_border"],
                                 border_width=1, corner_radius=10)
        container.pack(fill="x", padx=16, pady=(16, 0))

        ctk.CTkLabel(container, text="Settings", font=ctk.CTkFont(size=11),
                     text_color=C["text_muted"]).pack(anchor="w", padx=16, pady=(10, 8))

        # Blender toggle
        bl_row = ctk.CTkFrame(container, fg_color="transparent")
        bl_row.pack(fill="x", padx=16, pady=(0, 4))

        bl_label_frame = ctk.CTkFrame(bl_row, fg_color="transparent")
        bl_label_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(bl_label_frame, text="Blender Bridge", font=ctk.CTkFont(size=14),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(bl_label_frame, text="Install addon & connect to Blender",
                     font=ctk.CTkFont(size=11), text_color=C["text_dim"]).pack(anchor="w")

        self.blender_switch = ctk.CTkSwitch(bl_row, text="", width=46,
                                             command=self._toggle_blender,
                                             progress_color=C["accent"], fg_color=C["card_border"])
        self.blender_switch.pack(side="right")
        if self.config.get("blender_enabled") and self.blender_addon_installed:
            self.blender_switch.select()

        # Separator
        ctk.CTkFrame(container, fg_color=C["separator"], height=1).pack(fill="x", padx=16, pady=8)

        # Claude Desktop connection
        conn_row = ctk.CTkFrame(container, fg_color="transparent")
        conn_row.pack(fill="x", padx=16, pady=(0, 12))

        conn_label_frame = ctk.CTkFrame(conn_row, fg_color="transparent")
        conn_label_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(conn_label_frame, text="Claude Desktop", font=ctk.CTkFont(size=14),
                     text_color=C["text"]).pack(anchor="w")

        self.connect_btn = ctk.CTkButton(conn_row, width=100, height=30, corner_radius=6,
                                          font=ctk.CTkFont(size=13),
                                          text="Disconnect" if self.connected else "Connect",
                                          fg_color=C["red"] if self.connected else C["accent"],
                                          hover_color="#dc2626" if self.connected else C["accent_hover"],
                                          command=self._toggle_connection)
        self.connect_btn.pack(side="right")

    # -- Actions (removed — no buttons needed) --

    def _build_actions(self):
        pass

    # -- Footer --

    def _build_footer(self):
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        footer = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkLabel(footer, text="Inkpilot - Claude x Blender",
                     font=ctk.CTkFont(size=11), text_color=C["text_muted"]).pack(side="left", padx=16)

        self.status_label = ctk.CTkLabel(footer, text="Ready",
                                          font=ctk.CTkFont(size=11), text_color=C["text_dim"])
        self.status_label.pack(side="right", padx=16)

    # -- Actions --

    def _toggle_blender(self):
        on = self.blender_switch.get()
        if on:
            if not self.blender_found:
                self._set_status("Blender not found - install from blender.org")
                self.blender_switch.deselect()
                return
            ok, msg = install_blender_addon()
            if ok:
                self.config["blender_enabled"] = True
                save_config(self.config)
                self.blender_addon_installed = True
                self._set_status("Blender addon installed! Open Blender to connect")
            else:
                self._set_status(f"Install failed: {msg}")
                self.blender_switch.deselect()
        else:
            uninstall_blender_addon()
            self.config["blender_enabled"] = False
            save_config(self.config)
            self.blender_addon_installed = False
            self._set_status("Blender addon removed. Restart Claude to apply")

    def _toggle_connection(self):
        if self.connected:
            uninstall_from_claude()
            self.connected = False
            self._update_llm_ui()
            self._set_status("Disconnected - restart Claude Desktop to apply")
        else:
            install_to_claude()
            self.connected = True
            self._update_llm_ui()
            self._set_status("Connected - restart Claude Desktop to apply")

    def _update_llm_ui(self):
        if self.connected:
            self.llm_dot.configure(fg_color=C["green"])
            self.llm_label.configure(text="Claude Desktop (MCP)")
            self.llm_detail.configure(text="MCP server registered")
            self.connect_btn.configure(text="Disconnect", fg_color=C["red"], hover_color="#dc2626")
        else:
            self.llm_dot.configure(fg_color=C["red"])
            self.llm_label.configure(text="Not connected")
            self.llm_detail.configure(text="Click Connect to set up")
            self.connect_btn.configure(text="Connect", fg_color=C["accent"], hover_color=C["accent_hover"])

    def _set_status(self, msg):
        self.status_label.configure(text=msg)
        self.after(5000, lambda: self.status_label.configure(text="Ready"))

    def _refresh_status(self):
        current = is_installed()
        if current != self.connected:
            self.connected = current
            self._update_llm_ui()

        bl = find_blender()
        new_found = bl is not None
        if new_found != self.blender_found:
            self.blender_found = new_found
            self.bl_dot.configure(fg_color=C["green"] if new_found else C["orange"])
            self.bl_label.configure(text="Blender - Installed" if new_found else "Blender - Not found")

        self.after(10000, self._refresh_status)


# -- Main --

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = InkpilotApp()
    app.mainloop()

if __name__ == "__main__":
    main()
