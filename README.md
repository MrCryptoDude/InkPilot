# Inkpilot — Claude AI x Blender Bridge

**Tell Claude what to build. Watch it appear in Blender.**

Inkpilot connects Claude AI to Blender through MCP (Model Context Protocol). Describe a scene, character, or object in plain English — Claude creates it directly in your Blender viewport. Full 3D modeling, materials, lighting, rendering, and even 2D art via Grease Pencil.

No terminal commands. No config files. Just a toggle switch.

---

## Why Inkpilot?

Other Blender-AI bridges require installing `uv`, editing JSON config files, running terminal commands, and debugging connection issues. Inkpilot is **one toggle switch**:

1. Toggle ON in the desktop app
2. Enable the addon in Blender
3. Open Claude Desktop
4. Start creating

---

## Features

- **Zero-config setup** — Desktop app handles everything
- **Full Blender control** — Objects, materials, cameras, lights, rendering
- **Grease Pencil 2D** — Draw 2D art in 3D space
- **PBR Materials** — Metallic, roughness, emission, colors
- **Scene inspection** — Claude can see what's in your scene
- **Code execution** — Run any bpy Python code through Claude
- **Viewport screenshots** — Claude can capture what Blender sees
- **Full renders** — Cycles or EEVEE rendering to PNG
- **Auto-start** — Bridge server starts when Blender opens

---

## Quick Start

### Prerequisites

- [Python 3.10+](https://python.org)
- [Blender 3.0+](https://blender.org) (tested on 5.0.1)
- [Claude Desktop](https://claude.ai/download)

### Install

```bash
git clone https://github.com/AIMindSpark/Inkpilot.git
cd Inkpilot
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements_mcp.txt
```

### Setup

1. **Launch the Inkpilot desktop app:**
   ```bash
   python inkpilot_tray.py
   ```

2. **Toggle ON "Blender Bridge"** — This copies the addon to Blender's addons folder

3. **Open Blender** and enable the addon:
   - Go to `Edit > Preferences > Add-ons`
   - Search for **"Inkpilot"**
   - Tick the checkbox to enable it
   - You'll see `[Inkpilot] Bridge started on 127.0.0.1:9876` in the console

4. **Close Claude Desktop** completely (right-click system tray icon → Quit)

5. **Reopen Claude Desktop** — It detects Inkpilot automatically

6. **Start creating!** Tell Claude to build something in Blender.

### Verify the connection

In Blender's 3D viewport, press **N** to open the sidebar. You'll see an **Inkpilot** tab showing the bridge status.

### To disable

Toggle OFF "Blender Bridge" in the desktop app and restart Claude Desktop.

---

## Example Prompts

```
"Clear the scene and create a low-poly island with water, sand, and palm trees"

"Make a metallic red sports car — use cylinders for wheels and cubes for the body"

"Set up studio lighting with a 3-point light rig and render the scene"

"Create a Grease Pencil character — draw a stick figure with thick black lines"

"Build a chess set — all 32 pieces on an 8x8 board with alternating materials"

"Make the background a sunset gradient and render at 1920x1080"
```

---

## How It Works

```
You (Claude Desktop)
    │
    ▼
Inkpilot MCP Server (Python, runs via stdio)
    │
    ▼  TCP socket (localhost:9876)
    │
Blender Addon (runs inside Blender)
    │
    ▼  bpy API (main thread via timers)
    │
Blender Viewport (you see changes live)
```

1. You describe what you want in Claude Desktop
2. Claude calls Inkpilot's Blender tools via MCP
3. The MCP server sends JSON commands over TCP to the Blender addon
4. The addon executes commands on Blender's main thread (thread-safe)
5. Objects, materials, and lights appear in your viewport instantly

---

## Blender Tools

Inkpilot exposes these tools to Claude:

### Scene
| Tool | Description |
|------|-------------|
| `blender_ping` | Check connection, get Blender version and scene summary |
| `blender_get_scene` | List all objects with transforms, materials, render settings |
| `blender_get_object` | Detailed info: vertices, faces, materials, dimensions |
| `blender_clear_scene` | Delete all objects (or filter by type: MESH, LIGHT, etc.) |

### Objects
| Tool | Description |
|------|-------------|
| `blender_create_object` | Create cube, sphere, cylinder, cone, plane, torus, monkey, text, camera, light, empty |
| `blender_delete_object` | Remove an object by name |
| `blender_modify_object` | Move, rotate, scale, rename, show/hide |
| `blender_duplicate_object` | Copy an object with optional offset |

### Materials
| Tool | Description |
|------|-------------|
| `blender_set_material` | Apply PBR material: color, metallic, roughness, emission |

### Camera & Lighting
| Tool | Description |
|------|-------------|
| `blender_set_camera` | Position camera, look-at target, focal length |
| `blender_add_light` | Add POINT, SUN, SPOT, or AREA light |
| `blender_set_world` | Set background color and strength |

### Rendering
| Tool | Description |
|------|-------------|
| `blender_render` | Full render to PNG (Cycles or EEVEE) |
| `blender_set_render_settings` | Engine, resolution, samples, transparent background |
| `blender_screenshot_viewport` | Quick viewport capture |

### 2D Drawing
| Tool | Description |
|------|-------------|
| `blender_grease_pencil_create` | Create a Grease Pencil object |
| `blender_grease_pencil_stroke` | Draw strokes with color and width |

### Advanced
| Tool | Description |
|------|-------------|
| `blender_execute_code` | Run arbitrary Python (bpy) code in Blender |

---

## Architecture

```
Inkpilot/
├── inkpilot_tray.py              # Desktop app (toggle switch UI)
├── run_mcp.py                    # MCP server entry point
│
├── inkpilot_mcp/
│   └── server.py                 # MCP tools (blender_* and inkpilot_*)
│
├── blender/
│   └── addon.py                  # Blender addon (TCP server + command handler)
│
├── bridge/
│   ├── engine.py                 # In-memory SVG engine (Inkscape backend)
│   └── adapters/
│       ├── blender.py            # TCP client for Blender bridge
│       └── inkscape.py           # Inkscape CLI adapter
│
└── assets/                       # Icons and images
```

### Desktop App (`inkpilot_tray.py`)
- Detects Blender installation
- Copies addon to Blender's addons folder
- Registers MCP server in Claude Desktop's config
- No terminal commands needed

### MCP Server (`inkpilot_mcp/server.py`)
- Exposes 17+ Blender tools + Inkscape tools
- Connects to Blender addon via TCP socket
- Runs as stdio MCP server (launched by Claude Desktop)

### Blender Addon (`blender/addon.py`)
- TCP socket server running inside Blender (port 9876)
- Commands execute on main thread via `bpy.app.timers`
- Auto-starts when addon is enabled
- Sidebar panel shows connection status

---

## Troubleshooting

### "Blender not connected" error
1. Make sure Blender is open
2. Check the addon is enabled: `Edit > Preferences > Add-ons > search "Inkpilot"`
3. Look for `[Inkpilot] Bridge started` in Blender's system console (`Window > Toggle System Console`)

### Claude doesn't see Inkpilot tools
1. Make sure you fully quit Claude Desktop (system tray → Quit)
2. Reopen Claude Desktop
3. The hammer icon should show Inkpilot tools

### Addon not showing in Blender
1. Run the desktop app and toggle Blender Bridge ON
2. Check the file exists: `%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\inkpilot_bridge.py`
3. Restart Blender after installing

### Render crashes or times out
- Complex renders can exceed the default 30-second timeout
- Use `blender_set_render_settings` to lower samples for previews
- Use EEVEE instead of Cycles for faster renders

---

## Roadmap

- [x] Blender bridge with TCP socket addon
- [x] Desktop app with one-toggle setup
- [x] Full 3D object creation and manipulation
- [x] PBR materials
- [x] Camera and lighting control
- [x] Rendering (Cycles + EEVEE)
- [x] Grease Pencil 2D drawing
- [x] Arbitrary code execution
- [x] Auto-detect Blender installation
- [ ] DALL-E image generation → Blender texture import
- [ ] HDRI environment lighting
- [ ] Animation and keyframes
- [ ] Geometry Nodes control
- [ ] Multi-LLM support (Claude.ai web, local models)
- [ ] Export to game engines (Godot, Unity)
- [ ] Photoshop / Illustrator adapters
- [ ] Mac and Linux builds

---

## License

MIT — Use it, modify it, ship games with it.

---

*Built with Claude by Dr.Crypto*
