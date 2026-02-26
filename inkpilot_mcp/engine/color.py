"""
Color — Color theory and gradient generation.

Supports hex, RGB, HSL, and named colors.
Generate harmonious palettes, shade variations, and gradients.
"""
import colorsys
import math
from typing import List, Tuple


class Color:
    """Color with conversion between hex, RGB, HSL."""
    
    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: float = 1.0):
        self.r = max(0, min(255, r))
        self.g = max(0, min(255, g))
        self.b = max(0, min(255, b))
        self.a = max(0.0, min(1.0, a))
    
    # ── Constructors ──
    
    @classmethod
    def hex(cls, h: str) -> 'Color':
        """From hex string: '#FF8800' or 'FF8800'."""
        h = h.lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0
        return cls(r, g, b, a)
    
    @classmethod
    def hsl(cls, h: float, s: float, l: float, a: float = 1.0) -> 'Color':
        """From HSL: h=0-360, s=0-1, l=0-1."""
        r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
        return cls(int(r * 255), int(g * 255), int(b * 255), a)
    
    @classmethod
    def hsv(cls, h: float, s: float, v: float, a: float = 1.0) -> 'Color':
        """From HSV: h=0-360, s=0-1, v=0-1."""
        r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
        return cls(int(r * 255), int(g * 255), int(b * 255), a)
    
    @classmethod
    def rgb(cls, r: int, g: int, b: int, a: float = 1.0) -> 'Color':
        return cls(r, g, b, a)
    
    @classmethod
    def named(cls, name: str) -> 'Color':
        """Common color names."""
        colors = {
            "black": "#000000", "white": "#FFFFFF",
            "red": "#FF0000", "green": "#00FF00", "blue": "#0000FF",
            "yellow": "#FFFF00", "cyan": "#00FFFF", "magenta": "#FF00FF",
            "orange": "#FF8800", "purple": "#8800FF", "pink": "#FF88AA",
            "brown": "#8B6914", "darkbrown": "#5C4400", "lightbrown": "#C49A3C",
            "tan": "#D2B48C", "beige": "#F5F5DC", "cream": "#FFFDD0",
            "grey": "#888888", "lightgrey": "#CCCCCC", "darkgrey": "#444444",
            "skyblue": "#87CEEB", "navy": "#000080", "forest": "#228B22",
            "gold": "#FFD700", "silver": "#C0C0C0", "coral": "#FF7F50",
            "salmon": "#FA8072", "ivory": "#FFFFF0",
        }
        return cls.hex(colors.get(name.lower(), "#000000"))
    
    # ── Conversions ──
    
    @property
    def hex_str(self) -> str:
        """To hex string: '#FF8800'."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"
    
    @property
    def hsl_tuple(self) -> Tuple[float, float, float]:
        """To (h, s, l) where h=0-360, s=0-1, l=0-1."""
        h, l, s = colorsys.rgb_to_hls(self.r / 255, self.g / 255, self.b / 255)
        return (h * 360, s, l)
    
    @property
    def hsv_tuple(self) -> Tuple[float, float, float]:
        h, s, v = colorsys.rgb_to_hsv(self.r / 255, self.g / 255, self.b / 255)
        return (h * 360, s, v)
    
    # ── Color Manipulation ──
    
    def lighten(self, amount: float = 0.2) -> 'Color':
        """Lighten by amount (0-1)."""
        h, s, l = self.hsl_tuple
        return Color.hsl(h, s, min(1.0, l + amount), self.a)
    
    def darken(self, amount: float = 0.2) -> 'Color':
        """Darken by amount (0-1)."""
        h, s, l = self.hsl_tuple
        return Color.hsl(h, s, max(0.0, l - amount), self.a)
    
    def saturate(self, amount: float = 0.2) -> 'Color':
        h, s, l = self.hsl_tuple
        return Color.hsl(h, min(1.0, s + amount), l, self.a)
    
    def desaturate(self, amount: float = 0.2) -> 'Color':
        h, s, l = self.hsl_tuple
        return Color.hsl(h, max(0.0, s - amount), l, self.a)
    
    def rotate_hue(self, degrees: float) -> 'Color':
        h, s, l = self.hsl_tuple
        return Color.hsl((h + degrees) % 360, s, l, self.a)
    
    def with_alpha(self, a: float) -> 'Color':
        return Color(self.r, self.g, self.b, a)
    
    def mix(self, other: 'Color', t: float = 0.5) -> 'Color':
        """Mix with another color. t=0 is self, t=1 is other."""
        return Color(
            int(self.r + (other.r - self.r) * t),
            int(self.g + (other.g - self.g) * t),
            int(self.b + (other.b - self.b) * t),
            self.a + (other.a - self.a) * t
        )
    
    # ── Harmony ──
    
    def complementary(self) -> 'Color':
        return self.rotate_hue(180)
    
    def triadic(self) -> Tuple['Color', 'Color']:
        return (self.rotate_hue(120), self.rotate_hue(240))
    
    def split_complementary(self) -> Tuple['Color', 'Color']:
        return (self.rotate_hue(150), self.rotate_hue(210))
    
    def analogous(self, spread: float = 30) -> Tuple['Color', 'Color']:
        return (self.rotate_hue(-spread), self.rotate_hue(spread))
    
    def __str__(self):
        return self.hex_str
    
    def __repr__(self):
        return f"Color('{self.hex_str}')"


class Gradient:
    """SVG gradient builder."""
    
    def __init__(self, grad_id: str, grad_type: str = "linear"):
        self.id = grad_id
        self.type = grad_type  # "linear" or "radial"
        self.stops: List[Tuple[float, str, float]] = []
        
        # Linear gradient coordinates
        self.x1 = "0%"
        self.y1 = "0%"
        self.x2 = "0%"
        self.y2 = "100%"
        
        # Radial gradient coordinates
        self.cx = "50%"
        self.cy = "50%"
        self.r = "50%"
        self.fx = None  # focal point
        self.fy = None
    
    def add_stop(self, offset: float, color, opacity: float = 1.0) -> 'Gradient':
        """Add a color stop. offset: 0-100, color: hex or Color."""
        c = str(color) if isinstance(color, Color) else color
        self.stops.append((offset, c, opacity))
        return self
    
    @classmethod
    def linear(cls, grad_id: str, color1, color2,
               x1="0%", y1="0%", x2="0%", y2="100%") -> 'Gradient':
        """Quick linear gradient between two colors."""
        g = cls(grad_id, "linear")
        g.x1, g.y1, g.x2, g.y2 = x1, y1, x2, y2
        g.add_stop(0, color1).add_stop(100, color2)
        return g
    
    @classmethod
    def radial(cls, grad_id: str, center_color, edge_color,
               cx="50%", cy="50%", r="50%") -> 'Gradient':
        """Quick radial gradient from center to edge."""
        g = cls(grad_id, "radial")
        g.cx, g.cy, g.r = cx, cy, r
        g.add_stop(0, center_color).add_stop(100, edge_color)
        return g
    
    @classmethod
    def three_stop(cls, grad_id: str, c1, c2, c3,
                   direction: str = "vertical") -> 'Gradient':
        """Three-color gradient for richer shading."""
        x1, y1, x2, y2 = {
            "vertical": ("0%", "0%", "0%", "100%"),
            "horizontal": ("0%", "0%", "100%", "0%"),
            "diagonal": ("0%", "0%", "100%", "100%"),
        }.get(direction, ("0%", "0%", "0%", "100%"))
        
        g = cls(grad_id, "linear")
        g.x1, g.y1, g.x2, g.y2 = x1, y1, x2, y2
        g.add_stop(0, c1).add_stop(50, c2).add_stop(100, c3)
        return g
    
    @property
    def url(self) -> str:
        """Reference string for use in fill/stroke."""
        return f"url(#{self.id})"
    
    def __str__(self):
        return self.url


class Palette:
    """Color palette generation for cohesive artwork."""
    
    @staticmethod
    def earth_tones() -> List[Color]:
        """Warm earth colors (good for animals, nature)."""
        return [Color.hex(h) for h in [
            "#8B6914", "#5C4400", "#C49A3C", "#D2B48C",
            "#A0522D", "#DEB887", "#F5DEB3", "#704214",
        ]]
    
    @staticmethod
    def forest() -> List[Color]:
        return [Color.hex(h) for h in [
            "#228B22", "#006400", "#32CD32", "#90EE90",
            "#556B2F", "#8FBC8F", "#2E8B57", "#3CB371",
        ]]
    
    @staticmethod
    def ocean() -> List[Color]:
        return [Color.hex(h) for h in [
            "#006994", "#00CED1", "#20B2AA", "#48D1CC",
            "#4682B4", "#87CEEB", "#B0E0E6", "#5F9EA0",
        ]]
    
    @staticmethod
    def sunset() -> List[Color]:
        return [Color.hex(h) for h in [
            "#FF6B35", "#FF8C42", "#FFB347", "#FFD166",
            "#E63946", "#F77F00", "#FCBF49", "#EAE2B7",
        ]]
    
    @staticmethod
    def from_base(base: Color, n: int = 5) -> List[Color]:
        """Generate a palette of n colors from a base color.
        Creates tints (lighter) and shades (darker)."""
        colors = []
        for i in range(n):
            t = i / (n - 1)  # 0 to 1
            lightness_shift = (t - 0.5) * 0.5  # -0.25 to +0.25
            h, s, l = base.hsl_tuple
            colors.append(Color.hsl(h, s, max(0, min(1, l + lightness_shift))))
        return colors
    
    @staticmethod
    def monochromatic(base: Color, n: int = 5) -> List[Color]:
        """Shades of one hue."""
        h, s, _ = base.hsl_tuple
        return [Color.hsl(h, s, (i + 1) / (n + 1)) for i in range(n)]
    
    @staticmethod
    def warm_cool(warm: Color, cool: Color, n: int = 5) -> List[Color]:
        """Blend between warm and cool colors."""
        return [warm.mix(cool, i / (n - 1)) for i in range(n)]
