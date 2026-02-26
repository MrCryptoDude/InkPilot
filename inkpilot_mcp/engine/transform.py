"""
Transform — SVG transform operations.
"""
import math


class Transform:
    """Build SVG transform strings with chaining."""
    
    def __init__(self):
        self._ops = []
    
    def translate(self, tx: float, ty: float = 0) -> 'Transform':
        self._ops.append(f"translate({tx:.2f},{ty:.2f})")
        return self
    
    def scale(self, sx: float, sy: float = None) -> 'Transform':
        if sy is None:
            self._ops.append(f"scale({sx:.4f})")
        else:
            self._ops.append(f"scale({sx:.4f},{sy:.4f})")
        return self
    
    def rotate(self, angle: float, cx: float = None, cy: float = None) -> 'Transform':
        """Rotate in degrees. cx, cy = center of rotation."""
        if cx is not None and cy is not None:
            self._ops.append(f"rotate({angle:.2f},{cx:.2f},{cy:.2f})")
        else:
            self._ops.append(f"rotate({angle:.2f})")
        return self
    
    def skew_x(self, angle: float) -> 'Transform':
        self._ops.append(f"skewX({angle:.2f})")
        return self
    
    def skew_y(self, angle: float) -> 'Transform':
        self._ops.append(f"skewY({angle:.2f})")
        return self
    
    def matrix(self, a, b, c, d, e, f) -> 'Transform':
        self._ops.append(f"matrix({a},{b},{c},{d},{e},{f})")
        return self
    
    @classmethod
    def flip_h(cls, cx: float) -> 'Transform':
        """Horizontal flip around x=cx."""
        return cls().translate(cx, 0).scale(-1, 1).translate(-cx, 0)
    
    @classmethod
    def flip_v(cls, cy: float) -> 'Transform':
        """Vertical flip around y=cy."""
        return cls().translate(0, cy).scale(1, -1).translate(0, -cy)
    
    @property
    def svg(self) -> str:
        return " ".join(self._ops)
    
    def __str__(self):
        return self.svg
