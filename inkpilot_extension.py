#!/usr/bin/env python3
"""
Inkpilot — Inkscape Extension Entry Point
Launches chat panel using GLib polling to keep UI responsive.
Note: Inkscape pauses while the chat is open (normal for extensions).
Close the chat window to return control to Inkscape with your changes.
"""
import sys
import os
import time
import traceback

EXT_DIR = os.path.dirname(os.path.abspath(__file__))
if EXT_DIR not in sys.path:
    sys.path.insert(0, EXT_DIR)

try:
    import inkex
    from inkex import EffectExtension
    RUNNING_IN_INKSCAPE = True
except ImportError:
    RUNNING_IN_INKSCAPE = False

from inkpilot.config import ensure_config
from inkpilot.api_client import InkpilotAPI
from inkpilot.context_builder import build_context
from inkpilot.response_parser import parse_response, validate_svg_fragment, validate_command
from inkpilot.svg_engine import SVGEngine


class InkpilotExtension(EffectExtension if RUNNING_IN_INKSCAPE else object):

    def __init__(self):
        if RUNNING_IN_INKSCAPE:
            super().__init__()
        self.config = ensure_config()

    def effect(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib
        from inkpilot.gui import InkpilotPanel

        api = InkpilotAPI()
        engine = SVGEngine(self.svg)
        panel_ref = [None]

        def get_selected():
            try:
                return [e.get('id') for e in self.svg.selection.values() if e.get('id')]
            except Exception:
                return []

        def handle_send(text, image_data=None):
            panel = panel_ref[0]
            if panel is None:
                return
            panel.set_waiting(True)

            try:
                context = build_context(self.svg, selected_ids=get_selected(),
                                        max_chars=self.config.get("max_context_chars", 12000))
            except Exception:
                context = ""

            # Start async call — uses queue, not callbacks
            api.send_message_async(text, context=context, image_data=image_data)

            # Poll every 200ms using GLib (keeps GTK responsive!)
            def poll():
                result = api.poll_result()
                if result is None:
                    return True  # keep polling

                status, data = result
                if status == "error":
                    panel.add_error_message(data)
                    panel.set_waiting(False)
                    return False

                try:
                    parsed = parse_response(data)
                    results = []

                    for svg_frag in parsed.svg_fragments:
                        ok, cleaned = validate_svg_fragment(svg_frag)
                        if ok:
                            ids = engine.insert_svg_fragment(cleaned)
                            results.append(f"✓ Created {len(ids)} element(s)")
                        else:
                            results.append(f"⚠ {cleaned}")

                    for cmd in parsed.commands:
                        ok, err = validate_command(cmd)
                        if ok:
                            try:
                                r = engine.execute_command(cmd)
                                if r:
                                    results.append(f"✓ {cmd.get('action','?')}: {r}")
                            except Exception as e:
                                results.append(f"⚠ {cmd.get('action','?')}: {e}")

                    msg = ""
                    if parsed.plain_text:
                        msg += parsed.plain_text
                    if results:
                        if msg:
                            msg += "\n\n"
                        msg += "\n".join(results)
                    if not msg.strip():
                        msg = "Done! Close this window to see changes in Inkscape."

                    panel.add_ai_message(msg.strip())
                    panel.set_status(f"✓ {len(results)} change(s) — close window to apply")

                except Exception as e:
                    panel.add_error_message(str(e))
                    traceback.print_exc()

                panel.set_waiting(False)
                return False

            GLib.timeout_add(200, poll)

        panel = InkpilotPanel(
            on_send=handle_send,
            on_clear=lambda: api.clear_conversation(),
        )
        panel_ref[0] = panel
        panel.set_title("Inkpilot — close window when done to apply changes")
        panel.connect("destroy", Gtk.main_quit)
        panel.show_all()
        Gtk.main()

        # When window closes, Inkscape receives the modified SVG automatically


if __name__ == "__main__":
    if RUNNING_IN_INKSCAPE:
        ext = InkpilotExtension()
        ext.run()
    else:
        print("Use 'python inkpilot/chat_app.py' for standalone mode.")
