# ✦ Inkpilot — AI Drawing for Inkscape via Claude

**Watch Claude draw pixel art, sprites, and game assets in real-time.**

Inkpilot is an MCP (Model Context Protocol) server that connects Claude to Inkscape. Chat with Claude naturally, and watch as it draws directly onto a live canvas — pixel by pixel, layer by layer.

![Live Preview](https://img.shields.io/badge/Live_Preview-Real_Time-blue)
![MCP](https://img.shields.io/badge/Protocol-MCP-green)
![Inkscape](https://img.shields.io/badge/Export-Inkscape_SVG-orange)

## ⚡ How It Works

```
You (Claude chat) → "Draw a 16x16 pixel art sword"
    ↓
Claude calls inkpilot tools (setup_canvas → create_layer → draw_pixel_region → ...)
    ↓
Inkpilot MCP Server (runs locally)
    ↓
Live Preview (browser) ← you watch each part appear in real-time
    ↓
Save → Open in Inkscape
```

## 🚀 Install (30 seconds)

**Requirements:** Python 3.10+, Claude Desktop or Claude in Chrome

```bash
cd Inkpilot
pip install -r requirements_mcp.txt
python install_mcp.py
```

That's it. Restart Claude and you're ready.

## 🎮 Usage

Just talk to Claude:

> "Draw a 32x32 pixel art sword with a brown leather hilt, silver blade, and golden pommel.
> Use separate layers for shadow, blade, guard, hilt, and pommel.
> Save it as sword.svg and open in Inkscape."

Claude will:
1. Set up the canvas and open the live preview in your browser
2. Create layers for each part
3. Draw pixel by pixel — you watch it happen live
4. Save the SVG and open it in Inkscape

### More examples:

- "Create a 4-frame walk cycle for a knight character, 32x32 each"
- "Design a health bar UI with a decorative frame"
- "Make a 3x3 tileset of grass, dirt, and stone tiles"
- "Draw a treasure chest in 3 states: closed, opening, open"

## 🧰 Available Tools

| Tool | Purpose |
|------|---------|
| `inkpilot_setup_canvas` | Set size, open live preview |
| `inkpilot_create_layer` | Create named layer (Background, Body, etc.) |
| `inkpilot_switch_layer` | Switch active layer |
| `inkpilot_draw_pixel_region` | **Primary pixel art tool** — batch of [x,y,color] |
| `inkpilot_draw_pixel_row` | Draw one row (scanline effect) |
| `inkpilot_draw_rect` | Rectangles, UI panels, health bars |
| `inkpilot_draw_circle` | Circles |
| `inkpilot_draw_path` | SVG paths for complex shapes |
| `inkpilot_draw_polygon` | Polygons |
| `inkpilot_draw_text` | Text labels |
| `inkpilot_insert_svg` | Raw SVG markup |
| `inkpilot_delete` | Remove elements |
| `inkpilot_get_state` | Check what's on the canvas |
| `inkpilot_save` | Save SVG + open in Inkscape |

## 🏗 Architecture

```
inkpilot_mcp/
├── server.py        # MCP server (FastMCP) — tool definitions
├── canvas.py        # SVG canvas engine with change notifications
├── live_server.py   # HTTP + SSE server for real-time preview
├── inkscape.py      # Inkscape integration (find + launch)
├── viewer/
│   └── index.html   # Beautiful live preview page
├── __init__.py
└── __main__.py      # Entry: python -m inkpilot_mcp
```

## 🔧 Manual Config

If the installer doesn't auto-configure, add this to your Claude Desktop config:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "inkpilot": {
      "command": "python",
      "args": ["-m", "inkpilot_mcp"],
      "cwd": "C:\\path\\to\\Inkpilot"
    }
  }
}
```

## 🧪 Test Without Claude

```bash
python test_live.py
```

This draws a pixel art sword with live preview — no Claude needed. Great for verifying your setup works.

## 📝 License

MIT
