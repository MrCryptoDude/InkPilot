"""
Inkpilot — GTK Chat Panel UI v4
Big readable text, dark button text, native file picker, robust error handling.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import base64
import os
import traceback
from typing import Callable, Optional


QUICK_ACTIONS = [
    ("🗡️ Weapon", "Draw a 32x32 pixel art weapon with shading on transparent background"),
    ("🧑 Character", "Create a 32x32 pixel art game character on separate layers"),
    ("🗺️ Tiles", "Create a 3x3 tileset of 32x32 seamless tiles"),
    ("📊 Sprites", "Set up a sprite sheet grid: 4 columns, 4 rows, 64x64 cells"),
    ("❤️ HP Bar", "Design a game health bar, 200px wide, with decorative frame"),
    ("📁 Layers", "Set up game layers: Background, Midground, Characters, Props, Effects, UI"),
]


class InkpilotPanel(Gtk.Window):

    def __init__(self, on_send=None, on_clear=None, on_settings=None, theme="dark"):
        super().__init__(title="Inkpilot")
        self.set_default_size(500, 740)
        self.set_resizable(True)
        self.set_keep_above(True)

        self.on_send = on_send
        self.on_clear = on_clear
        self.is_waiting = False
        self.pending_image_b64 = None
        self.pending_image_media = None

        self._apply_css()
        self._build_ui()

    def _apply_css(self):
        css = """
        window { background-color: #0f172a; }

        .header { background-color: #0a0f1e; padding: 16px 20px; border-bottom: 3px solid #2563eb; }
        .header-title { color: #60a5fa; font-weight: bold; font-size: 24px; }
        .header-sub { color: #94a3b8; font-size: 15px; }

        .header-btn {
            background-color: #e2e8f0;
            border: none;
            border-radius: 8px;
            color: #0f172a;
            padding: 8px 16px;
            font-size: 15px;
            font-weight: bold;
        }
        .header-btn:hover { background-color: #f1f5f9; }

        .chat-area { background-color: #0f172a; }

        .msg-box { padding: 14px 16px; margin: 5px 12px; border-radius: 12px; }
        .user-msg { background-color: #1e293b; margin-left: 30px; border: 1px solid #334155; }
        .ai-msg { background-color: #0c2340; margin-right: 12px; border-left: 4px solid #2563eb; }
        .msg-role { color: #94a3b8; font-size: 14px; font-weight: bold; }
        .msg-role-ai { color: #60a5fa; }
        .msg-text { color: #f1f5f9; font-size: 16px; }

        .quick-bar { background-color: #0a0f1e; padding: 10px 12px; border-bottom: 1px solid #1e293b; }
        .quick-btn {
            background-color: #e2e8f0;
            border: none;
            border-radius: 20px;
            color: #0f172a;
            padding: 8px 16px;
            font-size: 15px;
            font-weight: bold;
        }
        .quick-btn:hover { background-color: #f1f5f9; }

        .input-area { background-color: #0a0f1e; padding: 14px 16px; border-top: 2px solid #1e293b; }
        .chat-entry {
            background-color: #1e293b; color: #f1f5f9; border: 2px solid #334155;
            border-radius: 12px; padding: 14px 16px; font-size: 16px;
        }
        .chat-entry:focus { border-color: #2563eb; }

        .send-btn {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 12px;
            padding: 14px 24px;
            font-weight: bold;
            font-size: 18px;
        }
        .send-btn:hover { background-color: #1d4ed8; }
        .send-btn:disabled { opacity: 0.35; }

        .attach-btn {
            background-color: #e2e8f0;
            border: none;
            border-radius: 10px;
            color: #0f172a;
            padding: 12px 14px;
            font-size: 20px;
        }
        .attach-btn:hover { background-color: #f1f5f9; }

        .attach-preview { background-color: #1e293b; border-radius: 8px; padding: 10px 16px; margin: 4px 12px; }
        .attach-label { color: #e2e8f0; font-size: 15px; }
        .attach-remove {
            background-color: #dc2626;
            border: none;
            border-radius: 6px;
            color: #ffffff;
            padding: 4px 12px;
            font-size: 14px;
            font-weight: bold;
        }
        .attach-remove:hover { background-color: #b91c1c; }

        .status-bar { background-color: #0a0f1e; padding: 6px 20px; }
        .status-text { color: #64748b; font-size: 14px; }
        .status-ok { color: #4ade80; font-size: 14px; }

        .error-text { color: #f87171; font-size: 15px; padding: 8px 16px; }

        .welcome-box {
            background-color: #1e293b; border: 1px solid #334155;
            border-radius: 14px; padding: 24px; margin: 16px;
        }
        .welcome-title { color: #60a5fa; font-size: 22px; font-weight: bold; }
        .welcome-text { color: #cbd5e1; font-size: 16px; }

        .login-box {
            background-color: #1e293b; border: 1px solid #334155;
            border-radius: 16px; padding: 36px; margin: 28px;
        }
        .login-title { color: #60a5fa; font-size: 30px; font-weight: bold; }
        .login-subtitle { color: #94a3b8; font-size: 17px; }
        .login-label { color: #e2e8f0; font-size: 16px; font-weight: bold; }
        .login-entry {
            background-color: #0f172a; color: #f1f5f9; border: 2px solid #334155;
            border-radius: 10px; padding: 14px 16px; font-size: 17px;
        }
        .login-entry:focus { border-color: #2563eb; }
        .login-btn {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 10px;
            padding: 16px 32px;
            font-weight: bold;
            font-size: 20px;
        }
        .login-btn:hover { background-color: #1d4ed8; }
        .login-help { color: #60a5fa; font-size: 14px; }
        .login-error { color: #f87171; font-size: 15px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(200)

        self.stack.add_named(self._build_login_screen(), "login")
        self.stack.add_named(self._build_chat_screen(), "chat")
        self.add(self.stack)

        from .config import get_api_key
        if get_api_key():
            self.stack.set_visible_child_name("chat")
        else:
            self.stack.set_visible_child_name("login")

    # ── Login Screen ─────────────────────────────────────────────

    def _build_login_screen(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_halign(Gtk.Align.CENTER)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.get_style_context().add_class("login-box")
        box.set_size_request(400, -1)

        title = Gtk.Label(label="✦ Inkpilot")
        title.get_style_context().add_class("login-title")
        box.pack_start(title, False, False, 0)

        sub = Gtk.Label(label="AI Copilot for Inkscape")
        sub.get_style_context().add_class("login-subtitle")
        box.pack_start(sub, False, False, 4)

        box.pack_start(Gtk.Separator(), False, False, 8)

        lbl = Gtk.Label(label="API Key")
        lbl.get_style_context().add_class("login-label")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        self.login_entry = Gtk.Entry()
        self.login_entry.set_placeholder_text("Paste your key here...")
        self.login_entry.set_visibility(False)
        self.login_entry.get_style_context().add_class("login-entry")
        self.login_entry.connect("activate", self._on_login)
        box.pack_start(self.login_entry, False, False, 0)

        help_lbl = Gtk.Label(label="Get your key at console.anthropic.com → API Keys")
        help_lbl.get_style_context().add_class("login-help")
        help_lbl.set_halign(Gtk.Align.START)
        box.pack_start(help_lbl, False, False, 0)

        btn = Gtk.Button(label="Connect")
        btn.get_style_context().add_class("login-btn")
        btn.connect("clicked", self._on_login)
        box.pack_start(btn, False, False, 8)

        self.login_error_label = Gtk.Label()
        self.login_error_label.get_style_context().add_class("login-error")
        self.login_error_label.set_no_show_all(True)
        self.login_error_label.hide()
        box.pack_start(self.login_error_label, False, False, 0)

        outer.pack_start(box, False, False, 0)
        return outer

    def _on_login(self, *args):
        key = self.login_entry.get_text().strip()
        if not key:
            self.login_error_label.set_text("Please enter your API key")
            self.login_error_label.show()
            return
        if not key.startswith("sk-"):
            self.login_error_label.set_text("Invalid key format — should start with sk-")
            self.login_error_label.show()
            return

        try:
            from .config import load_config, save_config
            config = load_config()
            config["api_key"] = key
            save_config(config)
            self.login_error_label.hide()
            self.stack.set_visible_child_name("chat")
        except Exception as e:
            self.login_error_label.set_text(f"Error saving: {e}")
            self.login_error_label.show()

    # ── Chat Screen ──────────────────────────────────────────────

    def _build_chat_screen(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.get_style_context().add_class("header")

        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t = Gtk.Label(label="✦ INKPILOT")
        t.get_style_context().add_class("header-title")
        t.set_halign(Gtk.Align.START)
        tbox.pack_start(t, False, False, 0)
        s = Gtk.Label(label="AI Copilot for Game Dev")
        s.get_style_context().add_class("header-sub")
        s.set_halign(Gtk.Align.START)
        tbox.pack_start(s, False, False, 0)
        header.pack_start(tbox, True, True, 0)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.get_style_context().add_class("header-btn")
        clear_btn.connect("clicked", self._on_clear)
        header.pack_end(clear_btn, False, False, 0)

        gear_btn = Gtk.Button(label="Settings")
        gear_btn.get_style_context().add_class("header-btn")
        gear_btn.connect("clicked", self._on_settings)
        header.pack_end(gear_btn, False, False, 0)

        main.pack_start(header, False, False, 0)

        # Quick actions
        qscroll = Gtk.ScrolledWindow()
        qscroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        qscroll.get_style_context().add_class("quick-bar")
        qbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, prompt in QUICK_ACTIONS:
            b = Gtk.Button(label=label)
            b.get_style_context().add_class("quick-btn")
            b.set_tooltip_text(prompt)
            b.connect("clicked", self._on_quick, prompt)
            qbox.pack_start(b, False, False, 0)
        qscroll.add(qbox)
        main.pack_start(qscroll, False, False, 0)

        # Chat area
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.get_style_context().add_class("chat-area")
        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.chat_box.set_valign(Gtk.Align.END)
        scroll.add(self.chat_box)
        self.scroll = scroll
        main.pack_start(scroll, True, True, 0)
        self._add_welcome()

        # Attachment preview bar
        self.attach_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.attach_bar.get_style_context().add_class("attach-preview")
        self.attach_bar.set_no_show_all(True)
        self.attach_bar.hide()
        self.attach_name = Gtk.Label(label="🖼️ image.png")
        self.attach_name.get_style_context().add_class("attach-label")
        self.attach_bar.pack_start(self.attach_name, True, True, 0)
        rm = Gtk.Button(label="✕ Remove")
        rm.get_style_context().add_class("attach-remove")
        rm.connect("clicked", self._on_remove_image)
        self.attach_bar.pack_end(rm, False, False, 0)
        main.pack_start(self.attach_bar, False, False, 0)

        # Status
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        sbar.get_style_context().add_class("status-bar")
        self.status_label = Gtk.Label(label="● Ready")
        self.status_label.get_style_context().add_class("status-ok")
        self.status_label.set_halign(Gtk.Align.START)
        sbar.pack_start(self.status_label, True, True, 0)
        main.pack_start(sbar, False, False, 0)

        # Input
        ibox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ibox.get_style_context().add_class("input-area")

        abtn = Gtk.Button(label="📎")
        abtn.get_style_context().add_class("attach-btn")
        abtn.set_tooltip_text("Attach a reference image")
        abtn.connect("clicked", self._on_attach)
        abtn.set_valign(Gtk.Align.END)
        ibox.pack_start(abtn, False, False, 0)

        iscroll = Gtk.ScrolledWindow()
        iscroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        iscroll.set_max_content_height(120)
        iscroll.set_propagate_natural_height(True)
        self.text_input = Gtk.TextView()
        self.text_input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_input.get_style_context().add_class("chat-entry")
        self.text_input.connect("key-press-event", self._on_key)
        iscroll.add(self.text_input)
        ibox.pack_start(iscroll, True, True, 0)

        self.send_btn = Gtk.Button(label="Send")
        self.send_btn.get_style_context().add_class("send-btn")
        self.send_btn.connect("clicked", self._on_send)
        self.send_btn.set_valign(Gtk.Align.END)
        ibox.pack_end(self.send_btn, False, False, 0)

        main.pack_start(ibox, False, False, 0)

        # Drag and drop for images
        main.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        main.drag_dest_add_uri_targets()
        main.connect("drag-data-received", self._on_drop)

        return main

    # ── Public API ───────────────────────────────────────────────

    def add_user_message(self, text, has_image=False):
        def _do():
            try:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.get_style_context().add_class("msg-box")
                box.get_style_context().add_class("user-msg")

                r = Gtk.Label(label="YOU" + ("  🖼️" if has_image else ""))
                r.get_style_context().add_class("msg-role")
                r.set_halign(Gtk.Align.START)
                box.pack_start(r, False, False, 0)

                m = Gtk.Label(label=text)
                m.get_style_context().add_class("msg-text")
                m.set_line_wrap(True)
                m.set_xalign(0)
                m.set_max_width_chars(40)
                m.set_selectable(True)
                box.pack_start(m, False, False, 0)

                self.chat_box.pack_start(box, False, False, 0)
                box.show_all()
                self._scroll_bottom()
            except Exception as e:
                print(f"[Inkpilot] Error adding user message: {e}", flush=True)
        GLib.idle_add(_do)

    def add_ai_message(self, text):
        def _do():
            try:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.get_style_context().add_class("msg-box")
                box.get_style_context().add_class("ai-msg")

                r = Gtk.Label(label="✦ INKPILOT")
                r.get_style_context().add_class("msg-role")
                r.get_style_context().add_class("msg-role-ai")
                r.set_halign(Gtk.Align.START)
                box.pack_start(r, False, False, 0)

                m = Gtk.Label(label=text)
                m.get_style_context().add_class("msg-text")
                m.set_line_wrap(True)
                m.set_xalign(0)
                m.set_max_width_chars(44)
                m.set_selectable(True)
                box.pack_start(m, False, False, 0)

                self.chat_box.pack_start(box, False, False, 0)
                box.show_all()
                self._scroll_bottom()
            except Exception as e:
                print(f"[Inkpilot] Error adding AI message: {e}", flush=True)
        GLib.idle_add(_do)

    def add_error_message(self, text):
        def _do():
            try:
                lbl = Gtk.Label()
                lbl.set_markup(f"<span foreground='#f87171'>⚠ {GLib.markup_escape_text(str(text))}</span>")
                lbl.set_line_wrap(True)
                lbl.set_xalign(0)
                lbl.get_style_context().add_class("error-text")
                lbl.set_max_width_chars(44)
                self.chat_box.pack_start(lbl, False, False, 4)
                lbl.show()
                self._scroll_bottom()
            except Exception as e:
                print(f"[Inkpilot] Error showing error: {e}", flush=True)
        GLib.idle_add(_do)

    def set_status(self, text):
        def _do():
            self.status_label.set_text(text)
            ctx = self.status_label.get_style_context()
            ctx.remove_class("status-text")
            ctx.remove_class("status-ok")
            if any(w in text for w in ["Ready", "Connected", "✓", "Saved", "applied"]):
                ctx.add_class("status-ok")
            else:
                ctx.add_class("status-text")
        GLib.idle_add(_do)

    def set_waiting(self, waiting):
        self.is_waiting = waiting
        GLib.idle_add(self.send_btn.set_sensitive, not waiting)
        self.set_status("⏳ Generating..." if waiting else "● Ready")

    # ── Image Handling ───────────────────────────────────────────

    def _on_attach(self, btn):
        """Use native file dialog so user gets thumbnail view on Windows."""
        try:
            dialog = Gtk.FileChooserNative.new(
                "Attach Reference Image",
                self,
                Gtk.FileChooserAction.OPEN,
                "Attach",
                "Cancel",
            )
        except Exception:
            # Fallback if FileChooserNative not available
            dialog = Gtk.FileChooserDialog(
                title="Attach Reference Image",
                parent=self,
                action=Gtk.FileChooserAction.OPEN,
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Attach", Gtk.ResponseType.OK)

        f = Gtk.FileFilter()
        f.set_name("Images (PNG, JPG, WebP)")
        for mt in ["image/png", "image/jpeg", "image/webp"]:
            f.add_mime_type(mt)
        f.add_pattern("*.png")
        f.add_pattern("*.jpg")
        f.add_pattern("*.jpeg")
        f.add_pattern("*.webp")
        dialog.add_filter(f)

        # All files filter too
        af = Gtk.FileFilter()
        af.set_name("All Files")
        af.add_pattern("*")
        dialog.add_filter(af)

        response = dialog.run()
        accepted = response in (Gtk.ResponseType.OK, Gtk.ResponseType.ACCEPT)
        if accepted:
            filepath = dialog.get_filename()
            if filepath:
                self._load_image(filepath)
        dialog.destroy()

    def _load_image(self, path):
        try:
            with open(path, "rb") as f:
                raw = f.read()
            self.pending_image_b64 = base64.b64encode(raw).decode("utf-8")
            ext = os.path.splitext(path)[1].lower()
            self.pending_image_media = {
                ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".webp": "image/webp",
            }.get(ext, "image/png")
            self.attach_name.set_text(f"🖼️  {os.path.basename(path)}")
            self.attach_bar.show_all()
            self.set_status(f"📎 Image attached")
        except Exception as e:
            self.add_error_message(f"Failed to load image: {e}")

    def _on_remove_image(self, *a):
        self.pending_image_b64 = None
        self.pending_image_media = None
        self.attach_bar.hide()
        self.set_status("● Ready")

    def _on_drop(self, widget, ctx, x, y, data, info, time):
        try:
            uris = data.get_uris()
            if uris:
                import urllib.parse
                p = urllib.parse.unquote(uris[0].replace("file:///", "").replace("file://", ""))
                if os.path.isfile(p) and os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    self._load_image(p)
        except Exception as e:
            print(f"[Inkpilot] Drop error: {e}", flush=True)

    # ── Internal ─────────────────────────────────────────────────

    def _add_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("welcome-box")

        t = Gtk.Label(label="Ready to create!")
        t.get_style_context().add_class("welcome-title")
        t.set_halign(Gtk.Align.START)
        box.pack_start(t, False, False, 0)

        txt = Gtk.Label(label=(
            "Describe what you want and I'll draw it on your canvas.\n\n"
            "I work with layers, sprites, pixel art, tilesets, and UI.\n\n"
            "📎  Attach an image as reference\n"
            "⚡  Use quick buttons above for common tasks"
        ))
        txt.get_style_context().add_class("welcome-text")
        txt.set_line_wrap(True)
        txt.set_xalign(0)
        txt.set_max_width_chars(44)
        box.pack_start(txt, False, False, 0)

        self.chat_box.pack_start(box, False, False, 10)

    def _scroll_bottom(self):
        def _do():
            a = self.scroll.get_vadjustment()
            a.set_value(a.get_upper() - a.get_page_size())
        GLib.timeout_add(80, _do)

    def _get_text(self):
        b = self.text_input.get_buffer()
        return b.get_text(b.get_start_iter(), b.get_end_iter(), False).strip()

    def _on_send(self, *a):
        try:
            text = self._get_text()
            if not text or self.is_waiting:
                return

            has_img = self.pending_image_b64 is not None
            self.add_user_message(text, has_image=has_img)
            self.text_input.get_buffer().set_text("")

            img = None
            if self.pending_image_b64:
                img = {"base64": self.pending_image_b64, "media_type": self.pending_image_media or "image/png"}
                self._on_remove_image()

            if self.on_send:
                self.on_send(text, img)
        except Exception as e:
            self.add_error_message(f"Send error: {e}")
            traceback.print_exc()

    def _on_quick(self, btn, prompt):
        try:
            if not self.is_waiting:
                self.add_user_message(prompt)
                if self.on_send:
                    self.on_send(prompt, None)
        except Exception as e:
            self.add_error_message(f"Error: {e}")
            traceback.print_exc()

    def _on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Return and not (event.state & Gdk.ModifierType.SHIFT_MASK):
            self._on_send()
            return True
        return False

    def _on_clear(self, *a):
        for c in self.chat_box.get_children():
            self.chat_box.remove(c)
        self._add_welcome()
        self.chat_box.show_all()
        if self.on_clear:
            self.on_clear()

    def _on_settings(self, *a):
        from .config import load_config, save_config
        d = Gtk.Dialog(title="Inkpilot Settings", parent=self, flags=Gtk.DialogFlags.MODAL)
        d.add_button("Cancel", Gtk.ResponseType.CANCEL)
        d.add_button("Save", Gtk.ResponseType.OK)
        d.set_default_size(420, 240)

        cfg = load_config()
        box = d.get_content_area()
        box.set_spacing(10)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)

        l1 = Gtk.Label(label="API Key:")
        l1.set_halign(Gtk.Align.START)
        box.add(l1)
        ke = Gtk.Entry()
        ke.set_text(cfg.get("api_key", ""))
        ke.set_visibility(False)
        box.add(ke)

        l2 = Gtk.Label(label="Model:")
        l2.set_halign(Gtk.Align.START)
        box.add(l2)
        mc = Gtk.ComboBoxText()
        models = [
            ("claude-sonnet-4-5-20250929", "Sonnet 4.5 (Recommended)"),
            ("claude-opus-4-6", "Opus 4.6 (Best quality)"),
            ("claude-haiku-4-5-20251001", "Haiku 4.5 (Fastest)"),
        ]
        cur = cfg.get("model", "claude-sonnet-4-5-20250929")
        for i, (mid, mn) in enumerate(models):
            mc.append(mid, mn)
            if mid == cur:
                mc.set_active(i)
        box.add(mc)

        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            cfg["api_key"] = ke.get_text().strip()
            cfg["model"] = mc.get_active_id()
            save_config(cfg)
            self.set_status("✓ Settings saved")
        d.destroy()
