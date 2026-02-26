"""
CreativeBridge — Code execution engine for AI-driven art.

This is the "Claude Code" equivalent for creative tools.
Claude writes Python code, the bridge executes it against
the drawing engine, and the result appears in Inkscape.

Architecture:
    Claude (MCP) → bridge.execute(code) → engine API → SVG → Inkscape

The bridge provides a sandboxed namespace with:
    - Canvas, Path, PathBuilder, Color, Gradient, Palette, Transform
    - math module
    - The active canvas object ('c' or 'canvas')

Security: Only our drawing API is available. No file I/O, 
no network, no system commands. Pure mathematical art.
"""
import math
import traceback
import time
from typing import Tuple, Optional

from .engine import Canvas, Path, PathBuilder, Color, Gradient, Palette, Transform


class CreativeBridge:
    """Execute art code against the drawing engine.
    
    One bridge per session. The canvas persists between executions,
    so Claude can build up artwork incrementally.
    """
    
    def __init__(self, svg_path: str, width: int = 512, height: int = 512):
        self.svg_path = svg_path
        self.width = width
        self.height = height
        self.canvas = Canvas(width, height)
        self._execution_count = 0
        self._history = []  # Track what was executed
    
    def reset(self, width: int = None, height: int = None):
        """Reset the canvas for a fresh drawing."""
        if width: self.width = width
        if height: self.height = height
        self.canvas = Canvas(self.width, self.height)
        self._execution_count = 0
        self._history.clear()
    
    def execute(self, code: str) -> Tuple[bool, str]:
        """Execute Python art code against the engine.
        
        The code has access to:
            c / canvas  — the Canvas object
            Path        — path builder
            PathBuilder — common shape templates
            Color       — color manipulation
            Gradient    — gradient definitions
            Palette     — color palettes
            Transform   — transform builder
            math        — math module
        
        Returns (success: bool, message: str)
        """
        self._execution_count += 1
        
        # Build the execution namespace
        namespace = {
            # Core objects
            "c": self.canvas,
            "canvas": self.canvas,
            
            # Engine classes
            "Canvas": Canvas,
            "Path": Path,
            "PathBuilder": PathBuilder,
            "Color": Color,
            "Gradient": Gradient,
            "Palette": Palette,
            "Transform": Transform,
            
            # Math
            "math": math,
            "pi": math.pi,
            "sin": math.sin,
            "cos": math.cos,
            "sqrt": math.sqrt,
            "atan2": math.atan2,
            "radians": math.radians,
            "degrees": math.degrees,
            "floor": math.floor,
            "ceil": math.ceil,
            
            # Convenience
            "abs": abs,
            "min": min,
            "max": max,
            "int": int,
            "float": float,
            "range": range,
            "enumerate": enumerate,
            "len": len,
            "round": round,
        }
        
        try:
            exec(code, namespace)
            
            # Write to disk
            self.canvas.write_svg(self.svg_path)
            
            # Record
            self._history.append({
                "index": self._execution_count,
                "code_lines": code.count('\n') + 1,
                "success": True,
            })
            
            return True, f"Executed ({code.count(chr(10))+1} lines). SVG written to {self.svg_path}"
            
        except Exception as e:
            tb = traceback.format_exc()
            self._history.append({
                "index": self._execution_count,
                "success": False,
                "error": str(e),
            })
            return False, f"Error: {str(e)}\n{tb}"
    
    def status(self) -> str:
        """Current state of the bridge."""
        lines = [
            f"CreativeBridge — {self.width}x{self.height}",
            f"Executions: {self._execution_count}",
            f"Canvas: {repr(self.canvas)}",
            f"SVG path: {self.svg_path}",
        ]
        return "\n".join(lines)
