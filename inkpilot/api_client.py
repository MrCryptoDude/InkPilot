"""
Inkpilot — Claude API Client
Uses queue-based communication to avoid GTK threading issues.
"""
import json
import os
import ssl
import threading
import queue
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional


def _make_ssl_context():
    """Create an SSL context that works with Inkscape's bundled Python."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    try:
        ctx = ssl.create_default_context()
        if ctx.get_ca_certs():
            return ctx
    except Exception:
        pass

    for env_var in ['SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE']:
        cert_file = os.environ.get(env_var)
        if cert_file and os.path.exists(cert_file):
            try:
                return ssl.create_default_context(cafile=cert_file)
            except Exception:
                pass

    # Unverified fallback (still encrypted)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


from .config import get_api_key, load_config

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.txt"


def _load_system_prompt():
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


class InkpilotAPI:

    def __init__(self):
        self.config = load_config()
        self.system_prompt = _load_system_prompt()
        self.conversation = []
        self.max_memory = self.config.get("conversation_memory", 20)
        self.result_queue = queue.Queue()

    def _build_user_content(self, user_message, context="", image_data=None):
        content = []
        if image_data and image_data.get("base64"):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_data.get("media_type", "image/png"),
                    "data": image_data["base64"],
                }
            })
        text = ""
        if context:
            text += f"<document_context>\n{context}\n</document_context>\n\n"
        text += user_message
        content.append({"type": "text", "text": text})
        return content

    def _build_messages(self, user_content):
        history = self.conversation[-(self.max_memory):]
        return history + [{"role": "user", "content": user_content}]

    def send_message_async(self, user_message, context="", image_data=None):
        """Start API call in background thread. Poll result_queue for result."""
        def _worker():
            try:
                result = self._call_api(user_message, context, image_data)
                self.conversation.append({"role": "user", "content": user_message})
                self.conversation.append({"role": "assistant", "content": result})
                if len(self.conversation) > self.max_memory * 2:
                    self.conversation = self.conversation[-(self.max_memory * 2):]
                self.result_queue.put(("ok", result))
            except Exception as e:
                self.result_queue.put(("error", str(e)))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def poll_result(self):
        """Check if API result is ready. Returns None if still waiting, or (status, data)."""
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None

    def send_message_sync(self, user_message, context="", image_data=None):
        """Blocking version for CLI use."""
        result = self._call_api(user_message, context, image_data)
        self.conversation.append({"role": "user", "content": user_message})
        self.conversation.append({"role": "assistant", "content": result})
        return result

    def _call_api(self, user_message, context="", image_data=None):
        api_key = get_api_key()
        if not api_key:
            raise ValueError("No API key configured. Click Settings to add your key.")

        config = load_config()
        user_content = self._build_user_content(user_message, context, image_data)
        messages = self._build_messages(user_content)

        payload = {
            "model": config.get("model", "claude-sonnet-4-5-20250929"),
            "max_tokens": config.get("max_tokens", 8192),
            "system": self.system_prompt,
            "messages": messages,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        ssl_ctx = _make_ssl_context()
        try:
            with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(error_body).get("error", {}).get("message", error_body)
            except Exception:
                msg = error_body
            raise RuntimeError(f"API error: {msg}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e

        text_parts = [b["text"] for b in body.get("content", []) if b.get("type") == "text"]
        if not text_parts:
            raise RuntimeError("Empty response from API")
        return "\n".join(text_parts)

    def clear_conversation(self):
        self.conversation.clear()
