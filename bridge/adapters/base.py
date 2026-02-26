"""
CreativeBridge — Abstract Adapter Interface

Every creative application gets an adapter. The adapter handles:
1. Connecting to the running application
2. Flushing document changes (engine → app)
3. Executing app-native operations (boolean ops, filters, etc.)
4. Live refresh / rendering synchronization

Implement this interface for each target application.
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseAdapter(ABC):
    """Abstract adapter for a creative application."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human name of the target app (e.g., 'Inkscape', 'Blender')."""
        ...
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Is the target application running and connected?"""
        ...
    
    @abstractmethod
    def connect(self) -> Tuple[bool, str]:
        """Find and connect to the running application.
        Returns (success, message)."""
        ...
    
    @abstractmethod
    def launch(self, file_path: str) -> Tuple[bool, str]:
        """Launch the application with a file.
        Returns (success, message)."""
        ...
    
    @abstractmethod
    def flush(self, svg_content: str, file_path: str) -> Tuple[bool, str]:
        """Push document changes to the application.
        Writes to disk and triggers the app to reload.
        Returns (success, message)."""
        ...
    
    @abstractmethod
    def execute(self, actions: str) -> Tuple[bool, str]:
        """Execute app-native commands (e.g., Inkscape CLI actions).
        Returns (success, message)."""
        ...
    
    @abstractmethod
    def export_png(self, output_path: str, dpi: int = 96,
                   width: int = None, height: int = None) -> Tuple[bool, str]:
        """Export the document as PNG.
        Returns (success, message)."""
        ...
    
    def screenshot(self, output_path: str) -> Tuple[bool, str, Optional[str]]:
        """Capture the application window. Optional — not all adapters need this.
        Returns (success, message, path_or_none)."""
        return False, "Not supported", None
