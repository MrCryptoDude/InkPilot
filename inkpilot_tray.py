"""
Inkpilot — Desktop App
Modern window application that bridges LLMs to Inkscape.
"""
import sys
import os
import json
import threading
import subprocess
import webbrowser
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────

# When running from PyInstaller .exe, find the real project dir
# The .exe lives in dist/Inkpilot/ so project root is 2 levels up
if getattr(sys, '_MEIPASS', None):
    _exe_dir = Path(sys.executable).parent.resolve()
    # Check if we're in dist/Inkpilot/
    _candidate = _exe_dir.parent.parent
    if (_candidate / "run_mcp.py").exists():
        PROJECT_DIR = _candidate
    else:
        # Fallback: check if project dir is stored in config
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

# ── Install deps if needed ───────────────────────────────────────

def _ensure_deps():
    missing = []
    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    if missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"]
        )

_ensure_deps()

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk


# ── Config ───────────────────────────────────────────────────────

def load_config():
    defaults = {"live_preview": True}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return {**defaults, **data}
        except Exception:
            pass
    return defaults


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


# ── Claude Desktop Config ───────────────────────────────────────

def get_claude_config_path():
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "claude" / "claude_desktop_config.json"


def is_installed():
    config_path = get_claude_config_path()
    if not config_path.exists():
        return False
    try:
        with open(config_path) as f:
            config = json.load(f)
        return "inkpilot" in config.get("mcpServers", {})
    except Exception:
        return False


def install_to_claude():
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

    # MCP server MUST run via Python + run_mcp.py (not the bundled .exe)
    # The .exe is the GUI app; the MCP server is a separate stdio process.
    run_script = str(PROJECT_DIR / "run_mcp.py")
    venv_python = str(PROJECT_DIR / ".venv" / "Scripts" / "python.exe")
    system_python = str(Path(sys.executable))

    # Prefer venv python (has all deps), fall back to current python
    if Path(venv_python).exists():
        python_exe = venv_python
    else:
        python_exe = system_python

    config["mcpServers"]["inkpilot"] = {
        "command": python_exe,
        "args": [run_script],
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    return True


def uninstall_from_claude():
    config_path = get_claude_config_path()
    if not config_path.exists():
        return
    try:
        with open(config_path) as f:
            config = json.load(f)
        if "inkpilot" in config.get("mcpServers", {}):
            del config["mcpServers"]["inkpilot"]
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
    except Exception:
        pass


# ── Find Inkscape ────────────────────────────────────────────────

def _find_inkscape():
    try:
        from inkpilot_mcp.inkscape import find_inkscape
        return find_inkscape()
    except Exception:
        return None


# ── Icon helpers ─────────────────────────────────────────────────

def _find_icon_path():
    candidates = [
        PROJECT_DIR / "assets" / "inkpilot.ico",
        PROJECT_DIR / "assets" / "inkpilot_256.png",
    ]
    if getattr(sys, '_MEIPASS', None):
        candidates.insert(0, Path(sys._MEIPASS) / "assets" / "inkpilot.ico")
    for c in candidates:
        if c and c.exists():
            return c
    return None


# ── Color Palette ────────────────────────────────────────────────

COLORS = {
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


# ── Desktop App ──────────────────────────────────────────────────

class InkpilotApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.connected = is_installed()
        self.inkscape_found = _find_inkscape() is not None

        # ── Window Setup ──
        self.title("Inkpilot")
        self.geometry("420x740")
        self.minsize(380, 680)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(True, True)

        # Window icon
        ico_path = _find_icon_path()
        if ico_path:
            try:
                if str(ico_path).endswith(".ico"):
                    self.iconbitmap(str(ico_path))
                else:
                    img = ImageTk.PhotoImage(Image.open(str(ico_path)).resize((32, 32)))
                    self.iconphoto(True, img)
            except Exception:
                pass

        # ── Build UI ──
        self._build_header()
        self._build_setup_guide()
        self._build_status_cards()
        self._build_controls()
        self._build_actions()
        self._build_footer()

        # Auto-install on first launch
        if not self.connected:
            self._connect()

        # Periodic status refresh
        self._refresh_status()

    # ── Header ───────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=70)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)

        # Logo + title
        title_frame = ctk.CTkFrame(inner, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame, text="Inkpilot",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text="  v1.0",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(4, 0))

        # Minimize to tray hint
        ctk.CTkLabel(
            inner, text="AI + Inkscape",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_muted"],
        ).pack(side="right")

    # ── Setup Guide ─────────────────────────────────────────────

    def _build_setup_guide(self):
        container = ctk.CTkFrame(
            self,
            fg_color=COLORS["card"],
            border_color=COLORS["accent"],
            border_width=1,
            corner_radius=10,
        )
        container.pack(fill="x", padx=16, pady=(16, 0))

        ctk.CTkLabel(
            container, text="Getting Started",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=16, pady=(10, 8))

        steps = [
            ("1", "Close Claude Desktop", "Quit it fully from the system tray"),
            ("2", "Connect Inkpilot", "Click the Connect button below"),
            ("3", "Open Claude Desktop", "It will detect Inkpilot automatically"),
        ]

        for num, title, desc in steps:
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 6))

            # Step number badge
            badge = ctk.CTkLabel(
                row, text=num,
                width=24, height=24,
                corner_radius=12,
                fg_color=COLORS["accent"],
                text_color="#ffffff",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            badge.pack(side="left", padx=(0, 10))

            # Step text
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="x")

            ctk.CTkLabel(
                text_frame, text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["text"],
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_frame, text=desc,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_dim"],
                anchor="w",
            ).pack(anchor="w")

        # Bottom padding
        ctk.CTkFrame(container, fg_color="transparent", height=6).pack()

    # ── Status Cards ─────────────────────────────────────────────

    def _build_status_cards(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=16, pady=(16, 0))

        # LLM Card
        self.llm_card = self._make_card(
            container,
            title="LLM Connection",
            row=0,
        )
        self.llm_status_dot = ctk.CTkLabel(
            self.llm_card, text="",
            width=10, height=10,
            corner_radius=5,
            fg_color=COLORS["green"] if self.connected else COLORS["red"],
        )
        self.llm_status_dot.grid(row=0, column=0, padx=(0, 8))

        self.llm_status_label = ctk.CTkLabel(
            self.llm_card,
            text="Claude Desktop (MCP)" if self.connected else "Not connected",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        )
        self.llm_status_label.grid(row=0, column=1, sticky="w")

        self.llm_detail = ctk.CTkLabel(
            self.llm_card,
            text="MCP server registered" if self.connected else "Click Connect to set up",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
        )
        self.llm_detail.grid(row=1, column=1, sticky="w", pady=(2, 0))

        # Inkscape Card
        self.ink_card = self._make_card(
            container,
            title="Inkscape",
            row=1,
        )
        self.ink_status_dot = ctk.CTkLabel(
            self.ink_card, text="",
            width=10, height=10,
            corner_radius=5,
            fg_color=COLORS["green"] if self.inkscape_found else COLORS["orange"],
        )
        self.ink_status_dot.grid(row=0, column=0, padx=(0, 8))

        ink_path = _find_inkscape() or "Not found"
        ink_short = "Installed" if self.inkscape_found else "Not found"

        self.ink_status_label = ctk.CTkLabel(
            self.ink_card,
            text=f"Inkscape - {ink_short}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        )
        self.ink_status_label.grid(row=0, column=1, sticky="w")

        # Show abbreviated path
        if self.inkscape_found and ink_path:
            short_path = str(ink_path)
            if len(short_path) > 45:
                short_path = "..." + short_path[-42:]
        else:
            short_path = "Install from inkscape.org"

        self.ink_detail = ctk.CTkLabel(
            self.ink_card,
            text=short_path,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self.ink_detail.grid(row=1, column=1, sticky="w", pady=(2, 0))

    def _make_card(self, parent, title, row):
        wrapper = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            border_color=COLORS["card_border"],
            border_width=1,
            corner_radius=10,
        )
        wrapper.pack(fill="x", pady=(0, 10))

        # Card title
        ctk.CTkLabel(
            wrapper, text=title,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(10, 4))

        # Card content frame (for grid layout)
        content = ctk.CTkFrame(wrapper, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=(0, 12))
        content.columnconfigure(1, weight=1)

        return content

    # ── Controls ─────────────────────────────────────────────────

    def _build_controls(self):
        container = ctk.CTkFrame(
            self,
            fg_color=COLORS["card"],
            border_color=COLORS["card_border"],
            border_width=1,
            corner_radius=10,
        )
        container.pack(fill="x", padx=16, pady=(6, 0))

        ctk.CTkLabel(
            container, text="Settings",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(10, 8))

        # Live Preview toggle
        preview_row = ctk.CTkFrame(container, fg_color="transparent")
        preview_row.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(
            preview_row, text="Live Preview",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            preview_row, text="Auto-open browser while drawing",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(8, 0))

        self.preview_switch = ctk.CTkSwitch(
            preview_row,
            text="",
            width=46,
            command=self._toggle_preview,
            progress_color=COLORS["accent"],
            fg_color=COLORS["card_border"],
        )
        self.preview_switch.pack(side="right")
        if self.config.get("live_preview", True):
            self.preview_switch.select()

        # Separator
        sep = ctk.CTkFrame(container, fg_color=COLORS["separator"], height=1)
        sep.pack(fill="x", padx=16, pady=8)

        # Connection toggle
        conn_row = ctk.CTkFrame(container, fg_color="transparent")
        conn_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            conn_row, text="Claude Desktop",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"],
        ).pack(side="left")

        self.connect_btn = ctk.CTkButton(
            conn_row,
            text="Disconnect" if self.connected else "Connect",
            width=100,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["red"] if self.connected else COLORS["accent"],
            hover_color="#dc2626" if self.connected else COLORS["accent_hover"],
            command=self._toggle_connection,
        )
        self.connect_btn.pack(side="right")

    # ── Action Buttons ───────────────────────────────────────────

    def _build_actions(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=16, pady=(16, 0))

        ctk.CTkLabel(
            container, text="Quick Actions",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=(0, 8))

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        btn_frame.columnconfigure((0, 1), weight=1)

        buttons = [
            ("Open Inkscape", self._open_inkscape, 0, 0),
            ("Live Preview", self._open_preview, 0, 1),
            ("Output Folder", self._open_output, 1, 0),
            ("Canvas File", self._open_canvas, 1, 1),
        ]

        for text, cmd, row, col in buttons:
            btn = ctk.CTkButton(
                btn_frame,
                text=text,
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=13),
                fg_color=COLORS["card"],
                border_color=COLORS["card_border"],
                border_width=1,
                hover_color=COLORS["card_border"],
                text_color=COLORS["text"],
                command=cmd,
            )
            btn.grid(row=row, column=col, padx=(0 if col == 0 else 4, 0 if col == 1 else 4),
                     pady=(0, 6), sticky="ew")

    # ── Footer ───────────────────────────────────────────────────

    def _build_footer(self):
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        footer = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkLabel(
            footer,
            text="Inkpilot - Claude x Inkscape",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=16)

        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self.status_label.pack(side="right", padx=16)

    # ── Actions ──────────────────────────────────────────────────

    def _toggle_preview(self):
        on = self.preview_switch.get()
        self.config["live_preview"] = bool(on)
        save_config(self.config)
        self._set_status(f"Live Preview {'ON' if on else 'OFF'}")

    def _toggle_connection(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        install_to_claude()
        self.connected = True
        self._update_connection_ui()
        self._set_status("Connected - restart Claude Desktop to apply")

    def _disconnect(self):
        uninstall_from_claude()
        self.connected = False
        self._update_connection_ui()
        self._set_status("Disconnected - restart Claude Desktop to apply")

    def _update_connection_ui(self):
        if self.connected:
            self.llm_status_dot.configure(fg_color=COLORS["green"])
            self.llm_status_label.configure(text="Claude Desktop (MCP)")
            self.llm_detail.configure(text="MCP server registered")
            self.connect_btn.configure(
                text="Disconnect",
                fg_color=COLORS["red"],
                hover_color="#dc2626",
            )
        else:
            self.llm_status_dot.configure(fg_color=COLORS["red"])
            self.llm_status_label.configure(text="Not connected")
            self.llm_detail.configure(text="Click Connect to set up")
            self.connect_btn.configure(
                text="Connect",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
            )

    def _open_inkscape(self):
        ink = _find_inkscape()
        if ink:
            canvas_file = str(WORK_DIR / "canvas.svg")
            target = canvas_file if os.path.exists(canvas_file) else None
            try:
                cmd = [ink] + ([target] if target else [])
                if sys.platform == "win32":
                    subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                else:
                    subprocess.Popen(cmd, start_new_session=True)
                self._set_status("Inkscape opened")
            except Exception as e:
                self._set_status(f"Error: {e}")
        else:
            self._set_status("Inkscape not found - install from inkscape.org")

    def _open_preview(self):
        webbrowser.open("http://localhost:7878")
        self._set_status("Opened live preview")

    def _open_output(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(OUTPUT_DIR))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(OUTPUT_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])
        self._set_status("Opened output folder")

    def _open_canvas(self):
        canvas_file = WORK_DIR / "canvas.svg"
        if canvas_file.exists():
            if sys.platform == "win32":
                os.startfile(str(canvas_file))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(canvas_file)])
            else:
                subprocess.Popen(["xdg-open", str(canvas_file)])
            self._set_status("Opened canvas file")
        else:
            self._set_status("No canvas yet - ask Claude to draw something")

    def _set_status(self, msg):
        self.status_label.configure(text=msg)
        # Auto-clear after 5 seconds
        self.after(5000, lambda: self.status_label.configure(text="Ready"))

    def _refresh_status(self):
        """Periodically check connection status."""
        current = is_installed()
        if current != self.connected:
            self.connected = current
            self._update_connection_ui()

        # Check Inkscape
        ink = _find_inkscape()
        new_found = ink is not None
        if new_found != self.inkscape_found:
            self.inkscape_found = new_found
            self.ink_status_dot.configure(
                fg_color=COLORS["green"] if new_found else COLORS["orange"]
            )

        self.after(10000, self._refresh_status)


# ── Main ─────────────────────────────────────────────────────────

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = InkpilotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
