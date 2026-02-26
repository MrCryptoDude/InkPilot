"""
Inkpilot Engine — Mathematical Drawing API

A high-performance, code-first drawing engine that generates SVG.
Designed for AI-driven art: Claude writes Python code using this API,
the engine produces pixel-perfect vector graphics.

Usage:
    canvas = Canvas(512, 512)
    canvas.fill_rect(0, 0, 512, 512, color="#87CEEB")
    canvas.draw_path(body_path, fill="#8B6914")
    svg_string = canvas.to_svg()
"""
from .canvas import Canvas
from .path import Path, PathBuilder
from .color import Color, Gradient, Palette
from .transform import Transform

__all__ = ["Canvas", "Path", "PathBuilder", "Color", "Gradient", "Palette", "Transform"]
