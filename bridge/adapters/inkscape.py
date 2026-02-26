"""
CreativeBridge — Inkscape Adapter (Native Bridge Mode)

Connects to the Inkpilot Bridge extension running INSIDE Inkscape.
Commands are sent via TCP socket and executed through Inkscape's
native API — not by writing files, not by simulating clicks.

Claude controls Inkscape the way Claude Code controls VSCode.

Two modes:
  1. BRIDGE MODE (preferred): Connects to the inkpilot_bridge.py
     extension running inside Inkscape on localhost:9147.
     Full native API access, real-time rendering.
  
  2. FALLBACK MODE: Uses Inkscape CLI for export/actions when
     bridge is not available. Writes SVG via engine.py.
"""
import os
import sys
import socket
import json
import time
import shutil
from typing import Tuple, Optional, List, Dict, Any

from .base import BaseAdapter

# Import legacy modules for fallback
try:
    _pkg_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from inkpilot_mcp import remote
    from inkpilot_mcp.inkscape import find_inkscape as _legacy_find_inkscape
    from inkpilot_mcp.inkscape import run_inkscape_actions as _legacy_run_actions
    from inkpilot_mcp.inkscape import open_in_inkscape as _legacy_open
    HAS_REMOTE = remote.HAS_GUI
    HAS_LEGACY = True
except ImportError:
    HAS_REMOTE = False
    HAS_LEGACY = False


# ── Bridge Connection ────────────────────────────────────────────

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9147
BRIDGE_TIMEOUT = 5.0  # seconds


class BridgeConnection:
    """TCP connection to the Inkpilot Bridge server inside Inkscape."""
    
    def __init__(self, host: str = BRIDGE_HOST, port: int = BRIDGE_PORT):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._file = None
    
    @property
    def connected(self) -> bool:
        return self._sock is not None
    
    def connect(self) -> Tuple[bool, str]:
        """Connect to the bridge server."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(BRIDGE_TIMEOUT)
            self._sock.connect((self.host, self.port))
            self._file = self._sock.makefile('rb')
            return True, f"Connected to Inkscape bridge at {self.host}:{self.port}"
        except ConnectionRefusedError:
            self._sock = None
            return False, (f"Bridge not running on {self.host}:{self.port}. "
                          f"Open Inkscape → Extensions → Inkpilot → Start Bridge")
        except Exception as e:
            self._sock = None
            return False, f"Connection failed: {e}"
    
    def disconnect(self):
        """Close the connection."""
        try:
            if self._file:
                self._file.close()
            if self._sock:
                self._sock.close()
        except:
            pass
        self._sock = None
        self._file = None
    
    def send(self, command: dict) -> dict:
        """Send a command and receive the response."""
        if not self.connected:
            ok, msg = self.connect()
            if not ok:
                return {"ok": False, "error": msg}
        
        try:
            # Send command as JSON + newline
            data = json.dumps(command) + "\n"
            self._sock.sendall(data.encode("utf-8"))
            
            # Read response line
            response_line = self._file.readline()
            if not response_line:
                self.disconnect()
                return {"ok": False, "error": "Bridge connection closed"}
            
            return json.loads(response_line.decode("utf-8"))
        
        except socket.timeout:
            return {"ok": False, "error": "Bridge timeout"}
        except ConnectionResetError:
            self.disconnect()
            return {"ok": False, "error": "Bridge connection reset"}
        except Exception as e:
            self.disconnect()
            return {"ok": False, "error": f"Bridge error: {e}"}
    
    def send_batch(self, commands: List[dict]) -> dict:
        """Send multiple commands as a batch."""
        return self.send({
            "cmd": "batch",
            "params": {"commands": commands}
        })


# ══════════════════════════════════════════════════════════════════
# INKSCAPE ADAPTER
# ══════════════════════════════════════════════════════════════════

class InkscapeAdapter(BaseAdapter):
    """Adapter for Inkscape — prefers native bridge, falls back to CLI."""
    
    def __init__(self, work_file: str, output_dir: str,
                 bridge_host: str = BRIDGE_HOST, bridge_port: int = BRIDGE_PORT):
        self.work_file = work_file
        self.output_dir = output_dir
        self.bridge = BridgeConnection(bridge_host, bridge_port)
        self._inkscape_path = _legacy_find_inkscape() if HAS_LEGACY else None
        self._connected = False
        
        os.makedirs(os.path.dirname(work_file), exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
    
    @property
    def name(self) -> str:
        return "Inkscape"
    
    @property
    def is_connected(self) -> bool:
        return self.bridge.connected
    
    @property
    def mode(self) -> str:
        """Current operating mode."""
        if self.bridge.connected:
            return "bridge"
        return "fallback"
    
    def connect(self) -> Tuple[bool, str]:
        """Connect to the Inkscape bridge server."""
        ok, msg = self.bridge.connect()
        if ok:
            self._connected = True
            return True, f"[BRIDGE MODE] {msg}"
        
        # Check if Inkscape GUI is at least running
        if HAS_REMOTE:
            ok2, info = remote.get_window_info()
            if ok2:
                return False, (f"Inkscape is running but bridge is not active. "
                              f"Go to Extensions → Inkpilot → Start Bridge. "
                              f"({msg})")
        
        return False, msg
    
    def launch(self, file_path: str = None) -> Tuple[bool, str]:
        """Launch Inkscape with a file."""
        target = file_path or self.work_file
        
        if HAS_LEGACY:
            msg = _legacy_open(target)
            ok = "Error" not in msg and "not found" not in msg
            if ok:
                self._connected = True
                # Try connecting to bridge (user may have already started it)
                time.sleep(1)
                self.bridge.connect()
            return ok, msg
        
        return False, "Inkscape launcher not available."
    
    def flush(self, svg_content: str, file_path: str = None) -> Tuple[bool, str]:
        """Write SVG to disk (fallback mode)."""
        target = file_path or self.work_file
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(svg_content)
            return True, f"Written to {target}"
        except Exception as e:
            return False, f"Write failed: {e}"
    
    # ── Bridge Commands (native mode) ──
    
    def draw(self, command: dict) -> dict:
        """Send a drawing command to Inkscape via bridge.
        
        Commands:
          {"cmd": "ellipse", "params": {"cx": 100, "cy": 100, "rx": 50, ...}}
          {"cmd": "path", "params": {"d": "M 10 20 L 30 40", "fill": "#FF0000"}}
          {"cmd": "create_layer", "params": {"name": "sprites"}}
          {"cmd": "batch", "params": {"commands": [...]}}
        
        Returns result dict from bridge.
        """
        if not self.bridge.connected:
            ok, msg = self.bridge.connect()
            if not ok:
                return {"ok": False, "error": msg}
        
        return self.bridge.send(command)
    
    def draw_batch(self, commands: List[dict]) -> dict:
        """Send multiple drawing commands at once."""
        return self.bridge.send_batch(commands)
    
    def create_layer(self, name: str, hidden: bool = False,
                     opacity: float = 1.0) -> dict:
        """Create a layer in Inkscape."""
        return self.draw({
            "cmd": "create_layer",
            "params": {"name": name, "hidden": hidden, "opacity": opacity}
        })
    
    def get_document_info(self) -> dict:
        """Get document state from Inkscape."""
        return self.draw({"cmd": "get_document_info", "params": {}})
    
    def save_document(self, path: str) -> dict:
        """Save Inkscape document to a path."""
        return self.draw({"cmd": "save", "params": {"path": path}})
    
    # ── CLI Operations (work in both modes) ──
    
    def execute(self, actions: str, select_ids: list = None) -> Tuple[bool, str]:
        """Execute Inkscape CLI actions."""
        if HAS_LEGACY:
            action_parts = []
            if select_ids:
                action_parts.append(f"select-by-id:{','.join(select_ids)}")
            action_parts.append(actions.strip(";"))
            full_actions = ";".join(action_parts)
            return _legacy_run_actions(self.work_file, full_actions)
        return False, "Inkscape CLI not available."
    
    def export_png(self, output_path: str = None, dpi: int = 96,
                   width: int = None, height: int = None) -> Tuple[bool, str]:
        """Export as PNG via Inkscape CLI."""
        if not output_path:
            output_path = os.path.join(
                self.output_dir, f"export_{int(time.time())}.png"
            )
        
        action_parts = ["export-area-page"]
        action_parts.append(f"export-filename:{output_path}")
        action_parts.append(f"export-dpi:{dpi}")
        if width: action_parts.append(f"export-width:{width}")
        if height: action_parts.append(f"export-height:{height}")
        action_parts.append("export-do")
        actions_str = ";".join(action_parts)
        
        if HAS_LEGACY:
            ok, msg = _legacy_run_actions(self.work_file, actions_str)
            if ok or os.path.isfile(output_path):
                return True, output_path
            return False, f"Export failed: {msg}"
        
        return False, "Inkscape not found."
    
    def screenshot(self, output_path: str) -> Tuple[bool, str, Optional[str]]:
        """Capture Inkscape window."""
        if not HAS_REMOTE:
            return False, "Remote control not available", None
        return remote.screenshot(output_path)
