"""
Inkpilot Blender Addon — TCP Bridge Server

Runs inside Blender. Creates a TCP socket server that the
Inkpilot MCP server connects to for Claude - Blender control.

Auto-starts when enabled. No buttons to click, no config to edit.

Architecture:
  Claude - Inkpilot MCP Server - TCP socket - This Addon - bpy API

All bpy operations run on Blender's main thread via bpy.app.timers.
"""

bl_info = {
    "name": "Inkpilot Bridge",
    "author": "Inkpilot",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Inkpilot",
    "description": "Connect Blender to Claude AI via Inkpilot",
    "category": "Interface",
}

import bpy
import bmesh
import socket
import threading
import json
import traceback
import mathutils
import math
import os
import sys
import tempfile
import base64
from bpy.props import IntProperty, BoolProperty, StringProperty


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876


# ==================================================================
#  BRIDGE SERVER
# ==================================================================

class BlenderBridge:
    """TCP server inside Blender. Commands queued, executed on main thread."""

    def __init__(self):
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.command_queue = []
        self.response_queue = []
        self.lock = threading.Lock()
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT

    def start(self, host=None, port=None):
        if self.running:
            return
        self.host = host or DEFAULT_HOST
        self.port = port or DEFAULT_PORT
        self.running = True
        t = threading.Thread(target=self._listen, daemon=True)
        t.start()
        if not bpy.app.timers.is_registered(self._process_commands):
            bpy.app.timers.register(self._process_commands, persistent=True)
        print(f"[Inkpilot] Bridge started on {self.host}:{self.port}")

    def stop(self):
        self.running = False
        if bpy.app.timers.is_registered(self._process_commands):
            bpy.app.timers.unregister(self._process_commands)
        for s in (self.client_socket, self.server_socket):
            if s:
                try: s.close()
                except: pass
        self.client_socket = None
        self.server_socket = None
        print("[Inkpilot] Bridge stopped")

    def _listen(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
        except Exception as e:
            print(f"[Inkpilot] Server bind failed: {e}")
            self.running = False
            return

        while self.running:
            try:
                client, addr = self.server_socket.accept()
                client.settimeout(1.0)
                self.client_socket = client
                print(f"[Inkpilot] MCP connected from {addr}")
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                if self.running:
                    print(f"[Inkpilot] Accept error: {e}")

    def _handle_client(self, client):
        buffer = ""
        while self.running:
            try:
                data = client.recv(65536)
                if not data:
                    print("[Inkpilot] MCP disconnected")
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        command = json.loads(line)
                    except json.JSONDecodeError as e:
                        err = json.dumps({"status": "error", "message": f"Bad JSON: {e}"}) + "\n"
                        client.sendall(err.encode("utf-8"))
                        continue
                    event = threading.Event()
                    with self.lock:
                        self.command_queue.append((command, event))
                    event.wait(timeout=60.0)
                    with self.lock:
                        if self.response_queue:
                            response = self.response_queue.pop(0)
                        else:
                            response = {"status": "error", "message": "Timeout"}
                    resp_json = json.dumps(response) + "\n"
                    client.sendall(resp_json.encode("utf-8"))
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError):
                print("[Inkpilot] Connection lost")
                break
            except Exception as e:
                print(f"[Inkpilot] Client error: {e}")
                break
        self.client_socket = None

    def _process_commands(self):
        with self.lock:
            if not self.command_queue:
                return 0.05
            command, event = self.command_queue.pop(0)
        try:
            result = execute_command(command)
            with self.lock:
                self.response_queue.append(result)
        except Exception as e:
            with self.lock:
                self.response_queue.append({
                    "status": "error", "message": str(e),
                    "trace": traceback.format_exc(),
                })
        event.set()
        return 0.05


bridge = BlenderBridge()


# ==================================================================
#  COMMAND EXECUTION (main thread only)
# ==================================================================

def execute_command(command):
    cmd_type = command.get("type", "")
    params = command.get("params", {})
    handler = COMMAND_HANDLERS.get(cmd_type)
    if not handler:
        return {"status": "error", "message": f"Unknown command: {cmd_type}"}
    try:
        result = handler(params)
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}


# -- Scene --

def cmd_ping(p):
    return {"status": "alive", "blender": ".".join(str(v) for v in bpy.app.version),
            "scene": bpy.context.scene.name, "objects": len(bpy.context.scene.objects)}

def cmd_get_scene_info(p):
    scene = bpy.context.scene
    objects = []
    for obj in scene.objects:
        info = {"name": obj.name, "type": obj.type, "location": list(obj.location),
                "rotation": list(obj.rotation_euler), "scale": list(obj.scale),
                "visible": obj.visible_get()}
        if obj.active_material:
            info["material"] = obj.active_material.name
        objects.append(info)
    return {"scene_name": scene.name, "object_count": len(objects), "objects": objects,
            "render_engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y]}

def cmd_get_object_info(p):
    obj = bpy.data.objects.get(p.get("name", ""))
    if not obj: return {"error": f"Object not found: {p.get('name')}"}
    info = {"name": obj.name, "type": obj.type, "location": list(obj.location),
            "rotation": list(obj.rotation_euler), "scale": list(obj.scale),
            "dimensions": list(obj.dimensions), "visible": obj.visible_get(),
            "materials": [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else []}
    if obj.type == "MESH" and obj.data:
        info.update({"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons), "edges": len(obj.data.edges)})
    return info

def cmd_clear_scene(p):
    bpy.ops.object.select_all(action="DESELECT")
    obj_type = p.get("type")
    for obj in bpy.context.scene.objects:
        if obj_type is None or obj.type == obj_type.upper():
            obj.select_set(True)
    bpy.ops.object.delete()
    return {"cleared": obj_type or "all"}


# -- Objects --

def cmd_create_object(p):
    obj_type = p.get("object_type", "cube").lower()
    location = p.get("location", [0, 0, 0])
    scale = p.get("scale", [1, 1, 1])
    rotation = p.get("rotation", [0, 0, 0])
    bpy.ops.object.select_all(action="DESELECT")

    creators = {
        "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=p.get("size", 2), location=location),
        "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=p.get("radius", 1), segments=p.get("segments", 32), ring_count=p.get("rings", 16), location=location),
        "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=p.get("radius", 1), depth=p.get("depth", 2), vertices=p.get("vertices", 32), location=location),
        "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=p.get("radius1", 1), radius2=p.get("radius2", 0), depth=p.get("depth", 2), location=location),
        "plane": lambda: bpy.ops.mesh.primitive_plane_add(size=p.get("size", 2), location=location),
        "torus": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=p.get("major_radius", 1), minor_radius=p.get("minor_radius", 0.25), location=location),
        "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=p.get("size", 2), location=location),
        "text": lambda: bpy.ops.object.text_add(location=location),
        "camera": lambda: bpy.ops.object.camera_add(location=location),
        "empty": lambda: bpy.ops.object.empty_add(type=p.get("empty_type", "PLAIN_AXES"), location=location),
    }

    if obj_type == "light":
        bpy.ops.object.light_add(type=p.get("light_type", "POINT").upper(), location=location)
    elif obj_type in creators:
        creators[obj_type]()
    else:
        return {"error": f"Unknown type: {obj_type}"}

    obj = bpy.context.active_object
    if p.get("name"): obj.name = p["name"]
    obj.scale = scale
    obj.rotation_euler = [math.radians(r) if abs(r) > 2 * math.pi else r for r in rotation]

    if obj_type == "text" and p.get("text"):
        obj.data.body = p["text"]
    if obj_type == "light":
        if p.get("energy"): obj.data.energy = p["energy"]
        if p.get("color"): obj.data.color = p["color"][:3]

    if p.get("material_color"):
        _apply_quick_material(obj, p["material_color"], p.get("material_name"))

    return {"name": obj.name, "type": obj.type}

def cmd_delete_object(p):
    obj = bpy.data.objects.get(p.get("name", ""))
    if not obj: return {"error": f"Not found: {p.get('name')}"}
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": p["name"]}

def cmd_modify_object(p):
    obj = bpy.data.objects.get(p.get("name", ""))
    if not obj: return {"error": f"Not found: {p.get('name')}"}
    if "location" in p: obj.location = p["location"]
    if "rotation" in p:
        r = p["rotation"]
        obj.rotation_euler = [math.radians(x) if abs(x) > 2 * math.pi else x for x in r]
    if "scale" in p: obj.scale = p["scale"]
    if "visible" in p:
        obj.hide_viewport = not p["visible"]
        obj.hide_render = not p["visible"]
    if p.get("new_name"): obj.name = p["new_name"]
    return {"name": obj.name}

def cmd_duplicate_object(p):
    obj = bpy.data.objects.get(p.get("name", ""))
    if not obj: return {"error": f"Not found: {p.get('name')}"}
    new_obj = obj.copy()
    if obj.data: new_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(new_obj)
    if p.get("new_name"): new_obj.name = p["new_name"]
    if p.get("offset"):
        off = p["offset"]
        new_obj.location = (obj.location.x + off[0], obj.location.y + off[1], obj.location.z + off[2])
    return {"name": new_obj.name}


# -- Materials --

def _apply_quick_material(obj, color, mat_name=None):
    if isinstance(color, str) and color.startswith("#"):
        r, g, b = int(color[1:3], 16)/255, int(color[3:5], 16)/255, int(color[5:7], 16)/255
        color = [r, g, b, 1.0]
    elif isinstance(color, list) and len(color) == 3:
        color = color + [1.0]
    if not mat_name:
        mat_name = f"IP_{color[0]:.1f}_{color[1]:.1f}_{color[2]:.1f}"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf: bsdf.inputs["Base Color"].default_value = color
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return mat.name

def cmd_set_material(p):
    obj = bpy.data.objects.get(p.get("name", ""))
    if not obj: return {"error": f"Not found: {p.get('name')}"}
    color = p.get("color", [0.8, 0.8, 0.8, 1.0])
    mat_name = _apply_quick_material(obj, color, p.get("material_name"))
    mat = bpy.data.materials.get(mat_name)
    if mat and mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if "metallic" in p: bsdf.inputs["Metallic"].default_value = p["metallic"]
            if "roughness" in p: bsdf.inputs["Roughness"].default_value = p["roughness"]
            if p.get("emission_color"):
                ec = p["emission_color"]
                if isinstance(ec, str) and ec.startswith("#"):
                    ec = [int(ec[1:3],16)/255, int(ec[3:5],16)/255, int(ec[5:7],16)/255, 1.0]
                bsdf.inputs["Emission Color"].default_value = ec
                bsdf.inputs["Emission Strength"].default_value = p.get("emission_strength", 1.0)
    return {"material": mat_name, "applied_to": obj.name}

def cmd_create_material(p):
    mat_name = p.get("name", "IP_Material")
    color = p.get("color", [0.8, 0.8, 0.8, 1.0])
    if isinstance(color, str) and color.startswith("#"):
        color = [int(color[1:3],16)/255, int(color[3:5],16)/255, int(color[5:7],16)/255, 1.0]
    elif isinstance(color, list) and len(color) == 3:
        color = color + [1.0]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        if "metallic" in p: bsdf.inputs["Metallic"].default_value = p["metallic"]
        if "roughness" in p: bsdf.inputs["Roughness"].default_value = p["roughness"]
    return {"material": mat.name}


# -- Camera & Lighting --

def cmd_set_camera(p):
    cam = bpy.context.scene.camera
    if not cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        bpy.context.scene.camera = cam
    if "location" in p: cam.location = p["location"]
    if "rotation" in p:
        r = p["rotation"]
        cam.rotation_euler = [math.radians(x) if abs(x) > 2*math.pi else x for x in r]
    if "look_at" in p:
        target = mathutils.Vector(p["look_at"])
        direction = target - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    if "focal_length" in p: cam.data.lens = p["focal_length"]
    return {"camera": cam.name, "location": list(cam.location)}

def cmd_add_light(p):
    light_type = p.get("light_type", "POINT").upper()
    location = p.get("location", [0, 0, 5])
    bpy.ops.object.light_add(type=light_type, location=location)
    light = bpy.context.active_object
    if p.get("name"): light.name = p["name"]
    light.data.energy = p.get("energy", 1000)
    light.data.color = p.get("color", [1, 1, 1])[:3]
    if p.get("shadow") is not None: light.data.use_shadow = p["shadow"]
    return {"light": light.name, "type": light_type}


# -- Rendering --

def cmd_set_render_settings(p):
    scene = bpy.context.scene
    if "engine" in p:
        engine = p["engine"].upper()
        if engine in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            scene.render.engine = engine
    if "resolution_x" in p: scene.render.resolution_x = p["resolution_x"]
    if "resolution_y" in p: scene.render.resolution_y = p["resolution_y"]
    if "samples" in p and scene.render.engine == "CYCLES":
        scene.cycles.samples = p["samples"]
    if "film_transparent" in p: scene.render.film_transparent = p["film_transparent"]
    return {"engine": scene.render.engine, "resolution": [scene.render.resolution_x, scene.render.resolution_y]}

def cmd_render(p):
    output_path = p.get("output_path") or os.path.join(tempfile.gettempdir(), "inkpilot_render.png")
    scene = bpy.context.scene
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = p.get("format", "PNG").upper()
    bpy.ops.render.render(write_still=True)
    return {"rendered": output_path, "exists": os.path.isfile(output_path)}

def cmd_screenshot_viewport(p):
    output_path = p.get("output_path") or os.path.join(tempfile.gettempdir(), "inkpilot_viewport.png")
    old_path = bpy.context.scene.render.filepath
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.opengl(write_still=True)
    bpy.context.scene.render.filepath = old_path
    result = {"path": output_path, "exists": os.path.isfile(output_path)}
    if p.get("as_base64") and os.path.isfile(output_path):
        with open(output_path, "rb") as f:
            result["base64"] = base64.b64encode(f.read()).decode("utf-8")
    return result


# -- Code Execution --

def cmd_execute_code(p):
    code = p.get("code", "")
    if not code: return {"error": "No code provided"}
    import io
    from contextlib import redirect_stdout
    stdout = io.StringIO()
    try:
        with redirect_stdout(stdout):
            exec(code, {"bpy": bpy, "mathutils": mathutils, "math": math, "bmesh": bmesh, "os": os, "json": json})
        return {"output": stdout.getvalue(), "success": True}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc(), "success": False}


# -- Grease Pencil --

def cmd_create_grease_pencil(p):
    name = p.get("name", "IP_GPencil")
    bpy.ops.object.gpencil_add(type="EMPTY", location=p.get("location", [0, 0, 0]))
    gp = bpy.context.active_object
    gp.name = name
    layer_name = p.get("layer_name", "Lines")
    if not gp.data.layers.get(layer_name):
        gp.data.layers.new(name=layer_name)
    return {"name": gp.name}

def cmd_draw_grease_pencil_stroke(p):
    gp = bpy.data.objects.get(p.get("gp_name", "IP_GPencil"))
    if not gp or gp.type != "GPENCIL":
        return {"error": f"GP not found: {p.get('gp_name')}"}
    layer_name = p.get("layer_name", "Lines")
    layer = gp.data.layers.get(layer_name)
    if not layer: layer = gp.data.layers.new(name=layer_name)
    frame = layer.active_frame
    if frame is None: frame = layer.frames.new(bpy.context.scene.frame_current)
    stroke = frame.strokes.new()
    stroke.display_mode = "3DSPACE"
    stroke.line_width = p.get("line_width", 10)
    points = p.get("points", [])
    stroke.points.add(count=len(points))
    for i, pt in enumerate(points):
        stroke.points[i].co = (pt[0], pt[1], pt[2] if len(pt) > 2 else 0)
        if len(pt) > 3: stroke.points[i].pressure = pt[3]
    color = p.get("color", [0, 0, 0, 1])
    if isinstance(color, str) and color.startswith("#"):
        color = [int(color[1:3],16)/255, int(color[3:5],16)/255, int(color[5:7],16)/255, 1.0]
    mat_name = f"GP_{color[0]:.2f}_{color[1]:.2f}_{color[2]:.2f}"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = color[:4]
    if mat.name not in [m.name for m in gp.data.materials]:
        gp.data.materials.append(mat)
    stroke.material_index = list(gp.data.materials).index(mat)
    return {"stroke_points": len(points)}

# -- World --

def cmd_set_world(p):
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        if "color" in p:
            c = p["color"]
            if isinstance(c, str) and c.startswith("#"):
                c = [int(c[1:3],16)/255, int(c[3:5],16)/255, int(c[5:7],16)/255, 1.0]
            bg.inputs["Color"].default_value = c
        if "strength" in p: bg.inputs["Strength"].default_value = p["strength"]
    return {"world": world.name}


# -- Command Registry --

COMMAND_HANDLERS = {
    "ping": cmd_ping,
    "get_scene_info": cmd_get_scene_info,
    "get_object_info": cmd_get_object_info,
    "clear_scene": cmd_clear_scene,
    "set_world": cmd_set_world,
    "create_object": cmd_create_object,
    "delete_object": cmd_delete_object,
    "modify_object": cmd_modify_object,
    "duplicate_object": cmd_duplicate_object,
    "set_material": cmd_set_material,
    "create_material": cmd_create_material,
    "set_camera": cmd_set_camera,
    "add_light": cmd_add_light,
    "set_render_settings": cmd_set_render_settings,
    "render": cmd_render,
    "screenshot_viewport": cmd_screenshot_viewport,
    "execute_code": cmd_execute_code,
    "create_grease_pencil": cmd_create_grease_pencil,
    "draw_grease_pencil_stroke": cmd_draw_grease_pencil_stroke,
}


# ==================================================================
#  BLENDER UI PANEL
# ==================================================================

class INKPILOT_PT_Panel(bpy.types.Panel):
    bl_label = "Inkpilot"
    bl_idname = "INKPILOT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Inkpilot"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        if bridge.running:
            box.label(text="Bridge: Running", icon="LINKED")
            if bridge.client_socket:
                box.label(text="Claude: Connected", icon="CHECKMARK")
            else:
                box.label(text="Claude: Waiting...", icon="TIME")
            box.label(text=f"Port: {bridge.port}")
            box.operator("inkpilot.stop_server", text="Stop Server", icon="PAUSE")
        else:
            box.label(text="Bridge: Stopped", icon="UNLINKED")
            box.operator("inkpilot.start_server", text="Start Server", icon="PLAY")


class INKPILOT_OT_StartServer(bpy.types.Operator):
    bl_idname = "inkpilot.start_server"
    bl_label = "Start Inkpilot Server"
    def execute(self, context):
        bridge.start()
        return {"FINISHED"}


class INKPILOT_OT_StopServer(bpy.types.Operator):
    bl_idname = "inkpilot.stop_server"
    bl_label = "Stop Inkpilot Server"
    def execute(self, context):
        bridge.stop()
        return {"FINISHED"}


classes = (INKPILOT_PT_Panel, INKPILOT_OT_StartServer, INKPILOT_OT_StopServer)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bridge.start()
    print("[Inkpilot] Addon registered - bridge auto-started")

def unregister():
    bridge.stop()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
