"""
Inkpilot Configuration
Handles config file in user's home directory.
"""
import os
import json
from pathlib import Path


def _get_config_dir():
    """Get config directory, handling Windows edge cases."""
    # Use USERPROFILE on Windows to avoid sandboxed paths
    home = os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or str(Path.home())
    return Path(home) / ".inkpilot"


CONFIG_DIR = _get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_DIR = CONFIG_DIR / "history"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 8192,
    "temperature": 0.7,
    "max_context_chars": 12000,
    "conversation_memory": 20,
    "auto_group": True,
    "auto_label": True,
    "default_canvas_size": [1024, 1024],
    "pixel_art_grid_size": 16,
    "sprite_sheet_padding": 2,
    "export_dpi": 96,
    "theme": "dark",
}


def ensure_config():
    """Create config directory and default config if they don't exist."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            save_config(DEFAULT_CONFIG)
    except Exception as e:
        print(f"[Inkpilot] Config init warning: {e}", flush=True)
    return load_config()


def load_config():
    """Load config from disk, merging with defaults."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
            return {**DEFAULT_CONFIG, **user_config}
    except Exception as e:
        print(f"[Inkpilot] Config load warning: {e}", flush=True)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save config to disk."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Inkpilot] Config save error: {e}", flush=True)
        raise


def get_api_key():
    """Get API key from config or environment."""
    config = load_config()
    key = config.get("api_key", "")
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key
