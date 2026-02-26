"""
Blender Adapter — Connects MCP server to Blender via TCP socket.

The Blender addon (blender/addon.py) runs a TCP server inside Blender.
This adapter connects to it and sends JSON commands.
"""
import socket
import json


class BlenderConnection:
    """TCP client that talks to the Blender bridge addon."""

    def __init__(self, host="127.0.0.1", port=9876, timeout=30):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, command_type: str, params: dict = None) -> dict:
        """Send a command to Blender and return the response."""
        cmd = {"type": command_type, "params": params or {}}
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            s.sendall(json.dumps(cmd).encode("utf-8") + b"\n")

            # Read response (may come in chunks)
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            s.close()
            return json.loads(data.decode("utf-8").strip())
        except ConnectionRefusedError:
            return {"status": "error", "message": "Blender not connected. Open Blender and enable the Inkpilot addon."}
        except socket.timeout:
            return {"status": "error", "message": "Blender command timed out (render may take longer — increase timeout)."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def is_alive(self) -> bool:
        """Check if Blender bridge is running."""
        resp = self.send("ping")
        return resp.get("status") == "ok"
