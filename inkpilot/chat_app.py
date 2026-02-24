#!/usr/bin/env python3
"""
Inkpilot — Standalone Chat Application
Uses GLib polling (not thread callbacks) to keep GTK responsive.
"""
import sys
import os
import time
import argparse
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
for p in [PARENT_DIR, SCRIPT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from lxml import etree

from inkpilot.config import ensure_config, load_config
from inkpilot.api_client import InkpilotAPI
from inkpilot.context_builder import build_context
from inkpilot.response_parser import parse_response, validate_svg_fragment, validate_command
from inkpilot.svg_engine import SVGEngine
from inkpilot.gui import InkpilotPanel


SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
NSMAP = {
    None: SVG_NS,
    "inkscape": INKSCAPE_NS,
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}


def create_svg_root(w=1024, h=1024):
    root = etree.Element(f"{{{SVG_NS}}}svg", nsmap=NSMAP)
    root.set("width", str(w))
    root.set("height", str(h))
    root.set("viewBox", f"0 0 {w} {h}")
    root.set("version", "1.1")
    layer = etree.SubElement(root, f"{{{SVG_NS}}}g")
    layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
    layer.set(f"{{{INKSCAPE_NS}}}label", "Layer 1")
    layer.set("id", "layer1")
    return root


def load_doc(path):
    if path and os.path.exists(path):
        try:
            return etree.parse(path).getroot()
        except Exception:
            pass
    return create_svg_root()


def save_svg(root, output_dir, name=None):
    os.makedirs(output_dir, exist_ok=True)
    if not name:
        name = f"inkpilot_{int(time.time())}.svg"
    path = os.path.join(output_dir, name)
    etree.ElementTree(root).write(path, xml_declaration=True, encoding="utf-8", pretty_print=True)
    return path


def run_gui(output_dir, doc_path):
    config = ensure_config()
    api = InkpilotAPI()
    svg_root = load_doc(doc_path)
    engine = SVGEngine(svg_root)
    gen_count = [0]
    panel_ref = [None]

    def handle_send(text, image_data=None):
        panel = panel_ref[0]
        if panel is None:
            return
        panel.set_waiting(True)

        try:
            context = build_context(svg_root, max_chars=config.get("max_context_chars", 12000))
        except Exception:
            context = ""

        # Start async API call — result goes to api.result_queue
        api.send_message_async(text, context=context, image_data=image_data)

        # Start polling for result (every 200ms)
        GLib.timeout_add(200, lambda: poll_result(panel))

    def poll_result(panel):
        """Called by GLib timer. Returns True to keep polling, False to stop."""
        result = api.poll_result()
        if result is None:
            return True  # Keep polling

        status, data = result
        if status == "error":
            panel.add_error_message(data)
            panel.set_waiting(False)
            return False  # Stop polling

        # Success — process the response
        try:
            process_response(panel, data)
        except Exception as e:
            panel.add_error_message(str(e))
            traceback.print_exc()
        panel.set_waiting(False)
        return False  # Stop polling

    def process_response(panel, response_text):
        parsed = parse_response(response_text)
        results = []

        for svg_frag in parsed.svg_fragments:
            is_valid, cleaned = validate_svg_fragment(svg_frag)
            if is_valid:
                ids = engine.insert_svg_fragment(cleaned)
                results.append(f"✓ Created {len(ids)} element(s)")
            else:
                results.append(f"⚠ SVG: {cleaned}")

        for cmd in parsed.commands:
            is_valid, err = validate_command(cmd)
            if is_valid:
                try:
                    r = engine.execute_command(cmd)
                    if r:
                        results.append(f"✓ {cmd.get('action', '?')}: {r}")
                except Exception as e:
                    results.append(f"⚠ {cmd.get('action', '?')}: {e}")

        # Save output SVG
        gen_count[0] += 1
        out_name = f"inkpilot_{int(time.time())}_{gen_count[0]:03d}.svg"
        out_path = save_svg(svg_root, output_dir, out_name)

        # Build response message
        ai_msg = ""
        if parsed.plain_text:
            ai_msg += parsed.plain_text
        if results:
            if ai_msg:
                ai_msg += "\n\n"
            ai_msg += "\n".join(results)
        ai_msg += f"\n\n📄 Saved: {out_path}"
        if not ai_msg.strip():
            ai_msg = "Done! Check the output folder."

        panel.add_ai_message(ai_msg.strip())
        panel.set_status(f"✓ Saved to {os.path.basename(out_path)}")

    # Create and show panel
    panel = InkpilotPanel(
        on_send=handle_send,
        on_clear=lambda: api.clear_conversation(),
    )
    panel_ref[0] = panel
    panel.connect("destroy", Gtk.main_quit)
    panel.show_all()
    Gtk.main()


def main():
    parser = argparse.ArgumentParser(description="Inkpilot Chat")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--doc", default=None)
    args = parser.parse_args()

    if not args.output_dir:
        home = os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "") or os.path.expanduser("~")
        args.output_dir = os.path.join(home, ".inkpilot", "output")

    os.makedirs(args.output_dir, exist_ok=True)
    run_gui(args.output_dir, args.doc)


if __name__ == "__main__":
    main()
