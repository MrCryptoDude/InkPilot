"""
Inkpilot MCP — Inkscape Remote Control (Background Mode)
Controls Inkscape WITHOUT stealing focus or moving the user's mouse.
Uses Win32 messages sent directly to the Inkscape window handle.

The user can work on other things while Claude draws in Inkscape.
If the user wants to watch, they just open the Inkscape window.
"""
import os
import sys
import time
import struct
import base64
import io

try:
    import pygetwindow as gw
    from PIL import Image
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

# Win32 API via ctypes (no focus stealing)
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    
    user32 = ctypes.windll.user32
    
    # Window messages
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_MOUSEMOVE = 0x0200
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_CHAR = 0x0102
    WM_MOUSEWHEEL = 0x020A
    
    # Mouse button flags
    MK_LBUTTON = 0x0001
    MK_RBUTTON = 0x0002
    
    # Virtual key codes
    VK_MAP = {
        'backspace': 0x08, 'tab': 0x09, 'return': 0x0D, 'enter': 0x0D,
        'shift': 0x10, 'ctrl': 0x11, 'control': 0x11, 'alt': 0x12,
        'escape': 0x1B, 'esc': 0x1B, 'space': 0x20,
        'pageup': 0x21, 'page_up': 0x21, 'pagedown': 0x22, 'page_down': 0x22,
        'end': 0x23, 'home': 0x24,
        'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
        'delete': 0x2E, 'del': 0x2E,
        'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
        'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
        'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
        '+': 0xBB, '=': 0xBB, '-': 0xBD, ',': 0xBC, '.': 0xBE,
    }
    
    def _make_lparam(x, y):
        """Pack x,y into LPARAM for mouse messages."""
        return (y << 16) | (x & 0xFFFF)
    
    def _vk_from_char(c):
        """Get virtual key code from character."""
        c_lower = c.lower()
        if c_lower in VK_MAP:
            return VK_MAP[c_lower]
        if c_lower.isalpha():
            return ord(c_lower.upper())
        if c_lower.isdigit():
            return ord(c_lower)
        return None
    
    HAS_WIN32 = True
else:
    HAS_WIN32 = False


def _find_inkscape_window():
    """Find the Inkscape window. Returns window object or None."""
    if not HAS_GUI:
        return None
    try:
        windows = gw.getWindowsWithTitle("Inkscape")
        if not windows:
            for w in gw.getAllWindows():
                if "inkscape" in w.title.lower():
                    return w
            return None
        return windows[0]
    except Exception:
        return None


def _get_hwnd():
    """Get the Inkscape window handle for Win32 messages."""
    win = _find_inkscape_window()
    if win is None:
        return None, None
    try:
        return win._hWnd, win
    except Exception:
        return None, win


def screenshot(output_path):
    """Capture the Inkscape window as PNG WITHOUT stealing focus.
    Uses PrintWindow API to capture even background windows."""
    if not HAS_GUI or not HAS_WIN32:
        return False, "Requires Windows + pygetwindow", None
    
    hwnd, win = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found", None
    
    try:
        # Get window dimensions
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        
        if width <= 0 or height <= 0:
            return False, "Invalid window dimensions", None
        
        # Use PrintWindow to capture without focus
        gdi32 = ctypes.windll.gdi32
        
        hdc_window = user32.GetDC(hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbm = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
        gdi32.SelectObject(hdc_mem, hbm)
        
        # PrintWindow flag 2 = PW_RENDERFULLCONTENT (captures even if obscured)
        user32.PrintWindow(hwnd, hdc_mem, 2)
        
        # Convert HBITMAP to PIL Image
        bmpinfo = ctypes.create_string_buffer(40)
        struct.pack_into('IiiHHIIiiII', bmpinfo, 0,
                         40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        
        buf = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(hdc_mem, hbm, 0, height, buf, bmpinfo, 0)
        
        img = Image.frombuffer('RGBA', (width, height), buf, 'raw', 'BGRA', 0, 1)
        
        # Cleanup GDI objects
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_window)
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        img.save(output_path)
        
        return True, f"Screenshot saved ({img.width}x{img.height})", output_path
    except Exception as e:
        return False, f"Screenshot failed: {e}", None


def click(x, y, button="left"):
    """Click at (x, y) in the Inkscape window WITHOUT stealing focus.
    Coordinates are relative to the Inkscape window's client area."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    lparam = _make_lparam(x, y)
    
    try:
        if button == "right":
            user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
            time.sleep(0.05)
            user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam)
        elif button == "double":
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
            time.sleep(0.05)
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.02)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        else:
            user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.05)
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        return True, f"Clicked ({x}, {y}) [{button}]"
    except Exception as e:
        return False, f"Click failed: {e}"


def drag(x1, y1, x2, y2, duration=0.5, button="left", steps=20):
    """Drag from (x1,y1) to (x2,y2) WITHOUT stealing focus.
    Sends mouse messages directly to Inkscape's window handle.
    steps: number of intermediate mouse-move messages (more = smoother)."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    btn_flag = MK_RBUTTON if button == "right" else MK_LBUTTON
    btn_down = WM_RBUTTONDOWN if button == "right" else WM_LBUTTONDOWN
    btn_up = WM_RBUTTONUP if button == "right" else WM_LBUTTONUP
    
    try:
        # Mouse down at start
        user32.PostMessageW(hwnd, btn_down, btn_flag, _make_lparam(x1, y1))
        
        # Interpolate movement
        delay = duration / max(steps, 1)
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)
            user32.PostMessageW(hwnd, WM_MOUSEMOVE, btn_flag, _make_lparam(cx, cy))
            time.sleep(delay)
        
        # Mouse up at end
        user32.PostMessageW(hwnd, btn_up, 0, _make_lparam(x2, y2))
        return True, f"Dragged ({x1},{y1}) → ({x2},{y2})"
    except Exception as e:
        return False, f"Drag failed: {e}"


def drag_path(points, duration_per_segment=0.2, button="left", steps_per_seg=10):
    """Drag along a series of points WITHOUT stealing focus.
    points: [(x1,y1), (x2,y2), ...]
    For drawing complex strokes with pen/pencil tools."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    if len(points) < 2:
        return False, "Need at least 2 points"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    btn_flag = MK_RBUTTON if button == "right" else MK_LBUTTON
    btn_down = WM_RBUTTONDOWN if button == "right" else WM_LBUTTONDOWN
    btn_up = WM_RBUTTONUP if button == "right" else WM_LBUTTONUP
    
    try:
        # Mouse down at first point
        x0, y0 = points[0]
        user32.PostMessageW(hwnd, btn_down, btn_flag, _make_lparam(x0, y0))
        
        # Drag through all segments
        delay = duration_per_segment / max(steps_per_seg, 1)
        for i in range(1, len(points)):
            px, py = points[i - 1]
            nx, ny = points[i]
            for s in range(1, steps_per_seg + 1):
                t = s / steps_per_seg
                cx = int(px + (nx - px) * t)
                cy = int(py + (ny - py) * t)
                user32.PostMessageW(hwnd, WM_MOUSEMOVE, btn_flag, _make_lparam(cx, cy))
                time.sleep(delay)
        
        # Mouse up at last point
        lx, ly = points[-1]
        user32.PostMessageW(hwnd, btn_up, 0, _make_lparam(lx, ly))
        return True, f"Dragged through {len(points)} points"
    except Exception as e:
        return False, f"Drag path failed: {e}"


def key(keys):
    """Press keyboard key(s) in Inkscape WITHOUT stealing focus.
    Sends key messages directly to Inkscape's window handle.
    Examples: 'r', 'ctrl+z', 'ctrl+shift+e', 'delete'."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    try:
        parts = keys.lower().split("+")
        modifiers = []
        main_key = None
        
        for p in parts:
            p = p.strip()
            if p in ("ctrl", "control"):
                modifiers.append(0x11)  # VK_CONTROL
            elif p in ("shift",):
                modifiers.append(0x10)  # VK_SHIFT
            elif p in ("alt",):
                modifiers.append(0x12)  # VK_MENU
            else:
                main_key = _vk_from_char(p)
        
        if main_key is None:
            return False, f"Unknown key: {keys}"
        
        # Press modifiers
        for vk in modifiers:
            user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
        
        # Press main key
        user32.PostMessageW(hwnd, WM_KEYDOWN, main_key, 0)
        time.sleep(0.05)
        user32.PostMessageW(hwnd, WM_KEYUP, main_key, 0)
        
        # Release modifiers (reverse order)
        for vk in reversed(modifiers):
            user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
        
        return True, f"Pressed '{keys}'"
    except Exception as e:
        return False, f"Key press failed: {e}"


def type_text(text):
    """Type text into Inkscape WITHOUT stealing focus.
    Sends WM_CHAR messages for each character."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    try:
        for ch in text:
            user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
            time.sleep(0.02)
        
        display = f"'{text[:30]}...'" if len(text) > 30 else f"'{text}'"
        return True, f"Typed {display}"
    except Exception as e:
        return False, f"Type failed: {e}"


def get_window_info():
    """Get Inkscape window info without stealing focus."""
    if not HAS_GUI:
        return False, {"error": "pygetwindow not installed"}
    
    win = _find_inkscape_window()
    if win is None:
        return False, {"error": "Inkscape window not found"}
    
    return True, {
        "title": win.title,
        "left": win.left,
        "top": win.top,
        "width": win.width,
        "height": win.height,
        "hwnd": getattr(win, '_hWnd', None),
    }


def scroll(x, y, clicks, direction="down"):
    """Scroll at position in Inkscape WITHOUT stealing focus."""
    if not HAS_WIN32:
        return False, "Requires Windows"
    
    hwnd, _ = _get_hwnd()
    if hwnd is None:
        return False, "Inkscape window not found"
    
    try:
        # WM_MOUSEWHEEL: wParam high word = delta (120 per notch)
        delta = clicks * 120 if direction == "up" else -clicks * 120
        wparam = (delta << 16) & 0xFFFFFFFF
        lparam = _make_lparam(x, y)
        user32.PostMessageW(hwnd, WM_MOUSEWHEEL, wparam, lparam)
        return True, f"Scrolled {direction} {clicks} at ({x},{y})"
    except Exception as e:
        return False, f"Scroll failed: {e}"
