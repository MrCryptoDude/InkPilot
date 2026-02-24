# Inkpilot — AI Copilot for Inkscape

**Describe what you want. Watch Claude draw it live.**

Inkpilot bridges Claude AI to Inkscape via MCP (Model Context Protocol). You describe a character, sprite, or icon — Claude draws it path by path into a real SVG canvas with separate layers. Watch every stroke appear live in your browser, then open the final result in Inkscape to edit.

Built for indie game developers who need layered SVG sprites that AI image generators can't make.

---

## Why Inkpilot?

AI image generators (DALL-E, Midjourney, Stable Diffusion) output flat PNGs. If you're building a game and need:

- **Separated body parts** (arms, legs, body on different layers for animation)
- **Editable vector art** (not locked raster images)
- **Paper Mario / Angry Birds style** characters
- **Fast iteration** without waiting in generation queues

...then you need Inkpilot.

---

## Features

- **Live Drawing Preview** — Watch Claude paint stroke by stroke in a browser window via Server-Sent Events
- **Layered SVG Output** — Each body part on its own Inkscape layer (arm, body, tail, etc.)
- **Editable Vectors** — Every path, shape, and curve is fully editable in Inkscape
- **Desktop App** — One-click install, auto-detects Inkscape (including Microsoft Store installs)
- **Live Preview Toggle** — Turn off if you just want the final result
- **Pixel Art Support** — Grid-perfect pixel art using SVG rects
- **Auto-saves** — Canvas saves to disk after every operation

---

## Quick Start

### Prerequisites

- [Python 3.10+](https://python.org)
- [Inkscape](https://inkscape.org) (any install method — standard, Microsoft Store, etc.)
- [Claude Desktop](https://claude.ai/download)

### Install

```bash
git clone https://github.com/YourUsername/Inkpilot.git
cd Inkpilot
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Setup

1. **Close Claude Desktop** (quit fully from system tray)
2. **Launch Inkpilot:**
   ```bash
   python inkpilot_tray.py
   ```
3. Click **Connect** in the Inkpilot window
4. **Open Claude Desktop** — it detects Inkpilot automatically
5. Ask Claude to draw something!

### Build Desktop App (Windows)

```bash
python build_icon.py   # Generate icon from SVG
python build.py        # Build standalone .exe
```

Output: `dist/Inkpilot/Inkpilot.exe`

---

## How It Works

```
You (Claude Desktop)              Inkpilot MCP Server              Inkscape
      |                                  |                            |
      |  "Draw a beaver with             |                            |
      |   separate arm layer"            |                            |
      |  ─────────────────────────────>  |                            |
      |                                  |  setup_canvas(512, 512)    |
      |                                  |  create_layer("Body")      |
      |                                  |  draw_path(body shape)     |
      |                                  |  create_layer("Left Arm")  |
      |                                  |  draw_path(arm shape)      |
      |                                  |          |                 |
      |                                  |    SSE stream ──> Browser  |
      |                                  |    (live preview)          |
      |                                  |          |                 |
      |                                  |  save("beaver.svg") ────> Opens in Inkscape
      |  <─────────────────────────────  |                            |
      |  "Done! Saved to output folder"  |                            |
```

1. You describe what you want in Claude Desktop
2. Claude calls Inkpilot's drawing tools via MCP
3. Each tool call updates an in-memory SVG canvas
4. The Live Preview server pushes updates to your browser via SSE
5. When done, the final SVG opens in Inkscape — fully layered and editable

---

## Architecture

```
Inkpilot/
├── inkpilot_tray.py          # Desktop app (CustomTkinter window)
├── run_mcp.py                # MCP server entry point
├── build.py                  # PyInstaller build script
├── build_icon.py             # SVG → ICO converter
│
├── inkpilot_mcp/             # Core MCP server
│   ├── server.py             # FastMCP tools (draw_path, draw_rect, etc.)
│   ├── canvas.py             # In-memory SVG canvas with change notifications
│   ├── inkscape.py           # Inkscape detection (PATH, Store, PowerShell)
│   ├── live_server.py        # HTTP + SSE server for live preview
│   └── viewer/
│       └── index.html        # Live preview browser UI
│
├── assets/                   # Built icon files
└── dist/                     # PyInstaller output
```

---

## MCP Tools

Inkpilot exposes these tools to Claude:

| Tool | Description |
|------|-------------|
| `inkpilot_setup_canvas` | Initialize canvas size, open live preview |
| `inkpilot_create_layer` | Create a named layer (Body, Arms, etc.) |
| `inkpilot_switch_layer` | Switch active layer |
| `inkpilot_draw_path` | Draw SVG paths (curves, outlines, shapes) |
| `inkpilot_draw_rect` | Draw rectangles |
| `inkpilot_draw_circle` | Draw circles |
| `inkpilot_draw_polygon` | Draw polygons |
| `inkpilot_draw_pixel_region` | Pixel art (batch of colored rects) |
| `inkpilot_draw_pixel_row` | Pixel art scanline |
| `inkpilot_draw_text` | Add text elements |
| `inkpilot_insert_svg` | Insert raw SVG markup |
| `inkpilot_delete` | Delete an element by ID |
| `inkpilot_save` | Save to output folder, optionally open in Inkscape |
| `inkpilot_get_state` | Get canvas info (size, layers, elements) |

---

## Example Prompts

```
"Draw a side-view beaver character in Paper Mario style with separate
 layers for: left arm, left foot, tail, and body with head"

"Create a 32x32 pixel art sword with a brown hilt and silver blade"

"Design a fantasy health bar — ornate gold frame, red fill gradient"

"Make a set of 16x16 terrain tiles: grass, dirt, water, stone"

"Draw a character walk cycle — 4 frames on separate layers"
```

---

## Desktop App Features

The Inkpilot desktop window shows:

- **LLM Connection** — Status of Claude Desktop integration
- **Inkscape Detection** — Auto-finds Inkscape installation
- **Live Preview Toggle** — Watch drawing live or just get the result
- **Connect / Disconnect** — One-click Claude Desktop setup
- **Quick Actions** — Open Inkscape, preview, output folder
- **Getting Started Guide** — Step-by-step setup instructions

---

## Configuration

Settings stored in `~/.inkpilot/config.json`:

```json
{
  "live_preview": true
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `live_preview` | `true` | Auto-open browser for live drawing preview |

---

## Roadmap

- [x] MCP server with drawing tools
- [x] Live browser preview (SSE)
- [x] Desktop app with CustomTkinter
- [x] Auto-detect Inkscape (Store, standard, PATH)
- [x] PyInstaller build for Windows
- [ ] Multi-LLM support (OpenAI, local models)
- [ ] Built-in chat panel (skip Claude Desktop)
- [ ] DALL-E → auto-trace → SVG import
- [ ] Animation timeline preview
- [ ] Export to Godot-ready sprite sheets
- [ ] Template library (characters, UI kits, tilesets)
- [ ] Mac and Linux builds

---

## License

MIT — Use it, modify it, ship games with it.

---

*Built with Claude by Dr.Crypto*
