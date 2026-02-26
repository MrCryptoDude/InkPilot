"""
Path — Mathematical path construction for SVG.

Build complex shapes with bezier curves, arcs, and straight lines.
All coordinates are in SVG units (pixels).

Example:
    p = Path()
    p.move(256, 100)
    p.cubic(200, 50, 150, 150, 180, 250)  # smooth curve
    p.cubic(200, 350, 312, 350, 332, 250)
    p.cubic(362, 150, 312, 50, 256, 100)
    p.close()
    
    # Or use PathBuilder for common shapes:
    tear = PathBuilder.teardrop(256, 256, 80, 120)
    star = PathBuilder.star(256, 256, 100, 50, 5)
"""
import math
from typing import List, Tuple


class Path:
    """SVG path builder using method chaining.
    
    Produces an SVG path data string (the 'd' attribute).
    All methods return self for chaining.
    """
    
    def __init__(self):
        self._commands: List[str] = []
    
    # ── Core Commands ──
    
    def move(self, x: float, y: float) -> 'Path':
        """Move to point (absolute)."""
        self._commands.append(f"M {x:.1f} {y:.1f}")
        return self
    
    def line(self, x: float, y: float) -> 'Path':
        """Line to point (absolute)."""
        self._commands.append(f"L {x:.1f} {y:.1f}")
        return self
    
    def cubic(self, c1x: float, c1y: float, c2x: float, c2y: float,
              x: float, y: float) -> 'Path':
        """Cubic bezier curve (absolute).
        c1: first control point, c2: second control point, (x,y): end point."""
        self._commands.append(f"C {c1x:.1f} {c1y:.1f}, {c2x:.1f} {c2y:.1f}, {x:.1f} {y:.1f}")
        return self
    
    def smooth_cubic(self, c2x: float, c2y: float, x: float, y: float) -> 'Path':
        """Smooth cubic bezier — c1 is mirror of previous c2."""
        self._commands.append(f"S {c2x:.1f} {c2y:.1f}, {x:.1f} {y:.1f}")
        return self
    
    def quad(self, cx: float, cy: float, x: float, y: float) -> 'Path':
        """Quadratic bezier curve (absolute)."""
        self._commands.append(f"Q {cx:.1f} {cy:.1f}, {x:.1f} {y:.1f}")
        return self
    
    def smooth_quad(self, x: float, y: float) -> 'Path':
        """Smooth quadratic — control point mirrors previous."""
        self._commands.append(f"T {x:.1f} {y:.1f}")
        return self
    
    def arc(self, rx: float, ry: float, rotation: float,
            large_arc: bool, sweep: bool,
            x: float, y: float) -> 'Path':
        """Elliptical arc."""
        la = 1 if large_arc else 0
        sw = 1 if sweep else 0
        self._commands.append(f"A {rx:.1f} {ry:.1f} {rotation:.1f} {la} {sw} {x:.1f} {y:.1f}")
        return self
    
    def close(self) -> 'Path':
        """Close the path."""
        self._commands.append("Z")
        return self
    
    # ── Relative Commands ──
    
    def rmove(self, dx: float, dy: float) -> 'Path':
        self._commands.append(f"m {dx:.1f} {dy:.1f}")
        return self
    
    def rline(self, dx: float, dy: float) -> 'Path':
        self._commands.append(f"l {dx:.1f} {dy:.1f}")
        return self
    
    def rcubic(self, dc1x, dc1y, dc2x, dc2y, dx, dy) -> 'Path':
        self._commands.append(f"c {dc1x:.1f} {dc1y:.1f}, {dc2x:.1f} {dc2y:.1f}, {dx:.1f} {dy:.1f}")
        return self
    
    def hline(self, x: float) -> 'Path':
        """Horizontal line to absolute x."""
        self._commands.append(f"H {x:.1f}")
        return self
    
    def vline(self, y: float) -> 'Path':
        """Vertical line to absolute y."""
        self._commands.append(f"V {y:.1f}")
        return self
    
    # ── Compound Operations ──
    
    def smooth_through(self, points: List[Tuple[float, float]], tension: float = 0.4) -> 'Path':
        """Draw a smooth curve through a series of points using cubic beziers.
        
        tension: 0.0 = straight lines, 0.5 = smooth, 1.0 = very round
        """
        if len(points) < 2:
            return self
        
        self.move(points[0][0], points[0][1])
        
        if len(points) == 2:
            self.line(points[1][0], points[1][1])
            return self
        
        for i in range(1, len(points)):
            p0 = points[max(i - 2, 0)]
            p1 = points[i - 1]
            p2 = points[i]
            p3 = points[min(i + 1, len(points) - 1)]
            
            # Catmull-Rom to cubic bezier conversion
            c1x = p1[0] + (p2[0] - p0[0]) * tension
            c1y = p1[1] + (p2[1] - p0[1]) * tension
            c2x = p2[0] - (p3[0] - p1[0]) * tension
            c2y = p2[1] - (p3[1] - p1[1]) * tension
            
            self.cubic(c1x, c1y, c2x, c2y, p2[0], p2[1])
        
        return self
    
    def rounded_rect(self, x: float, y: float, w: float, h: float,
                     r: float) -> 'Path':
        """Draw a rounded rectangle."""
        r = min(r, w / 2, h / 2)
        self.move(x + r, y)
        self.hline(x + w - r)
        self.arc(r, r, 0, False, True, x + w, y + r)
        self.vline(y + h - r)
        self.arc(r, r, 0, False, True, x + w - r, y + h)
        self.hline(x + r)
        self.arc(r, r, 0, False, True, x, y + h - r)
        self.vline(y + r)
        self.arc(r, r, 0, False, True, x + r, y)
        self.close()
        return self
    
    def circle_path(self, cx: float, cy: float, r: float) -> 'Path':
        """Draw a circle using arcs."""
        self.move(cx + r, cy)
        self.arc(r, r, 0, True, True, cx - r, cy)
        self.arc(r, r, 0, True, True, cx + r, cy)
        self.close()
        return self
    
    def ellipse_path(self, cx: float, cy: float, rx: float, ry: float) -> 'Path':
        """Draw an ellipse using arcs."""
        self.move(cx + rx, cy)
        self.arc(rx, ry, 0, True, True, cx - rx, cy)
        self.arc(rx, ry, 0, True, True, cx + rx, cy)
        self.close()
        return self
    
    # ── Output ──
    
    @property
    def d(self) -> str:
        """Get the SVG path data string."""
        return " ".join(self._commands)
    
    def __str__(self):
        return self.d
    
    def __repr__(self):
        return f"Path({len(self._commands)} commands)"


class PathBuilder:
    """Static methods for creating common shape paths."""
    
    @staticmethod
    def circle(cx: float, cy: float, r: float) -> Path:
        return Path().circle_path(cx, cy, r)
    
    @staticmethod
    def ellipse(cx: float, cy: float, rx: float, ry: float) -> Path:
        return Path().ellipse_path(cx, cy, rx, ry)
    
    @staticmethod
    def rect(x: float, y: float, w: float, h: float, r: float = 0) -> Path:
        if r > 0:
            return Path().rounded_rect(x, y, w, h, r)
        p = Path()
        p.move(x, y).line(x + w, y).line(x + w, y + h).line(x, y + h).close()
        return p
    
    @staticmethod
    def polygon(cx: float, cy: float, r: float, sides: int,
                rotation: float = -90) -> Path:
        """Regular polygon centered at (cx, cy)."""
        p = Path()
        for i in range(sides):
            angle = math.radians(rotation + (360 / sides) * i)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                p.move(x, y)
            else:
                p.line(x, y)
        p.close()
        return p
    
    @staticmethod
    def star(cx: float, cy: float, outer_r: float, inner_r: float,
             points: int = 5, rotation: float = -90) -> Path:
        """Star shape."""
        p = Path()
        for i in range(points * 2):
            r = outer_r if i % 2 == 0 else inner_r
            angle = math.radians(rotation + (360 / (points * 2)) * i)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                p.move(x, y)
            else:
                p.line(x, y)
        p.close()
        return p
    
    @staticmethod
    def teardrop(cx: float, cy: float, w: float, h: float) -> Path:
        """Teardrop / leaf shape."""
        p = Path()
        top = cy - h * 0.4
        bottom = cy + h * 0.6
        p.move(cx, top)
        p.cubic(cx + w * 0.8, top + h * 0.2, cx + w * 0.5, bottom - h * 0.1, cx, bottom)
        p.cubic(cx - w * 0.5, bottom - h * 0.1, cx - w * 0.8, top + h * 0.2, cx, top)
        p.close()
        return p
    
    @staticmethod
    def heart(cx: float, cy: float, size: float) -> Path:
        """Heart shape."""
        s = size
        p = Path()
        p.move(cx, cy + s * 0.3)
        p.cubic(cx, cy - s * 0.1, cx - s * 0.5, cy - s * 0.5, cx - s * 0.5, cy - s * 0.15)
        p.cubic(cx - s * 0.5, cy + s * 0.1, cx, cy + s * 0.35, cx, cy + s * 0.65)
        p.cubic(cx, cy + s * 0.35, cx + s * 0.5, cy + s * 0.1, cx + s * 0.5, cy - s * 0.15)
        p.cubic(cx + s * 0.5, cy - s * 0.5, cx, cy - s * 0.1, cx, cy + s * 0.3)
        p.close()
        return p
    
    @staticmethod
    def smooth_blob(cx: float, cy: float, r: float,
                    irregularity: float = 0.3, seed: int = 42) -> Path:
        """Organic blob shape (like a natural form).
        irregularity: 0 = perfect circle, 1 = very irregular
        """
        import random
        rng = random.Random(seed)
        
        n_points = 12
        points = []
        for i in range(n_points):
            angle = (2 * math.pi / n_points) * i
            variation = 1 + (rng.random() - 0.5) * 2 * irregularity
            px = cx + r * variation * math.cos(angle)
            py = cy + r * variation * math.sin(angle)
            points.append((px, py))
        points.append(points[0])  # close
        
        p = Path()
        p.smooth_through(points, tension=0.35)
        p.close()
        return p
    
    @staticmethod
    def wave(x1: float, y: float, x2: float, amplitude: float,
             wavelength: float) -> Path:
        """Sine wave path (for water, hair, etc.)."""
        p = Path()
        p.move(x1, y)
        x = x1
        while x < x2:
            # Each wave is two cubic bezier segments
            hw = wavelength / 2
            cp_offset = hw * 0.55  # approximation for sine
            p.cubic(x + cp_offset, y - amplitude,
                    x + hw - cp_offset, y - amplitude,
                    x + hw, y)
            p.cubic(x + hw + cp_offset, y + amplitude,
                    x + wavelength - cp_offset, y + amplitude,
                    x + wavelength, y)
            x += wavelength
        return p
    
    @staticmethod
    def arrow(x1: float, y1: float, x2: float, y2: float,
              head_size: float = 15, shaft_width: float = 5) -> Path:
        """Arrow from (x1,y1) to (x2,y2)."""
        angle = math.atan2(y2 - y1, x2 - x1)
        perp = angle + math.pi / 2
        
        # Shaft
        sw = shaft_width / 2
        sx1 = x1 + sw * math.cos(perp)
        sy1 = y1 + sw * math.sin(perp)
        sx2 = x1 - sw * math.cos(perp)
        sy2 = y1 - sw * math.sin(perp)
        
        # Where shaft meets head
        hx = x2 - head_size * math.cos(angle)
        hy = y2 - head_size * math.sin(angle)
        
        hsx1 = hx + sw * math.cos(perp)
        hsy1 = hy + sw * math.sin(perp)
        hsx2 = hx - sw * math.cos(perp)
        hsy2 = hy - sw * math.sin(perp)
        
        # Head wings
        hw = head_size * 0.6
        wx1 = hx + hw * math.cos(perp)
        wy1 = hy + hw * math.sin(perp)
        wx2 = hx - hw * math.cos(perp)
        wy2 = hy - hw * math.sin(perp)
        
        p = Path()
        p.move(sx1, sy1)
        p.line(hsx1, hsy1)
        p.line(wx1, wy1)
        p.line(x2, y2)
        p.line(wx2, wy2)
        p.line(hsx2, hsy2)
        p.line(sx2, sy2)
        p.close()
        return p
