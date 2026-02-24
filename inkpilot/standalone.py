"""
Inkpilot — Standalone mode
Run outside Inkscape for testing: python -m inkpilot.standalone
"""
import sys
import os
import argparse
import time
import traceback
from pathlib import Path

# Ensure package imports work
PKG_DIR = Path(__file__).parent.parent
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

from lxml import etree
from inkpilot.config import ensure_config, load_config
from inkpilot.api_client import InkpilotAPI
from inkpilot.context_builder import build_context
from inkpilot.response_parser import parse_response, validate_svg_fragment, validate_command
from inkpilot.svg_engine import SVGEngine


SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
NSMAP = {
    None: SVG_NS,
    "inkscape": INKSCAPE_NS,
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}


def create_blank_svg(w=1024, h=1024):
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


def run_gui(args):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    from inkpilot.gui import InkpilotPanel

    config = ensure_config()
    api = InkpilotAPI()

    if args.input and os.path.exists(args.input):
        svg_root = etree.parse(args.input).getroot()
    else:
        svg_root = create_blank_svg(args.width, args.height)

    engine = SVGEngine(svg_root)
    output_path = args.output or "inkpilot_output.svg"
    panel_ref = [None]

    def handle_send(text, image_data=None):
        panel = panel_ref[0]
        if not panel:
            return
        panel.set_waiting(True)

        try:
            context = build_context(svg_root, max_chars=config.get("max_context_chars", 12000))
        except Exception:
            context = ""

        api.send_message_async(text, context=context, image_data=image_data)

        def poll():
            result = api.poll_result()
            if result is None:
                return True

            status, data = result
            if status == "error":
                panel.add_error_message(data)
                panel.set_waiting(False)
                return False

            try:
                parsed = parse_response(data)
                results = []

                for frag in parsed.svg_fragments:
                    ok, cleaned = validate_svg_fragment(frag)
                    if ok:
                        ids = engine.insert_svg_fragment(cleaned)
                        results.append(f"✓ Created {len(ids)} element(s)")

                for cmd in parsed.commands:
                    ok, err = validate_command(cmd)
                    if ok:
                        try:
                            r = engine.execute_command(cmd)
                            if r:
                                results.append(f"✓ {cmd.get('action','?')}: {r}")
                        except Exception as e:
                            results.append(f"⚠ {cmd.get('action','?')}: {e}")

                # Save
                tree = etree.ElementTree(svg_root)
                tree.write(output_path, xml_declaration=True, encoding="utf-8", pretty_print=True)

                msg = ""
                if parsed.plain_text:
                    msg += parsed.plain_text
                if results:
                    if msg:
                        msg += "\n\n"
                    msg += "\n".join(results)
                msg += f"\n\n📄 Saved to: {output_path}"

                panel.add_ai_message(msg.strip())
                panel.set_status(f"✓ Saved to {output_path}")

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
    panel.set_title(f"Inkpilot Standalone — {output_path}")
    panel.connect("destroy", Gtk.main_quit)
    panel.show_all()
    Gtk.main()


def run_cli(args):
    config = ensure_config()
    api = InkpilotAPI()
    svg_root = create_blank_svg(args.width, args.height)
    engine = SVGEngine(svg_root)
    output_path = args.output or "inkpilot_output.svg"

    print(f"Inkpilot CLI — output: {output_path}")
    print("Type your prompt (or 'quit' to exit):\n")

    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt or prompt.lower() in ("quit", "exit"):
            break

        context = build_context(svg_root, max_chars=config.get("max_context_chars", 12000))
        print("  Generating...", flush=True)

        try:
            response = api.send_message_sync(prompt, context=context)
            parsed = parse_response(response)

            for frag in parsed.svg_fragments:
                ok, cleaned = validate_svg_fragment(frag)
                if ok:
                    ids = engine.insert_svg_fragment(cleaned)
                    print(f"  ✓ Created {len(ids)} element(s)")

            for cmd in parsed.commands:
                ok, err = validate_command(cmd)
                if ok:
                    r = engine.execute_command(cmd)
                    if r:
                        print(f"  ✓ {cmd.get('action','?')}: {r}")

            tree = etree.ElementTree(svg_root)
            tree.write(output_path, xml_declaration=True, encoding="utf-8", pretty_print=True)
            print(f"  📄 Saved to {output_path}")

            if parsed.plain_text:
                print(f"\n  AI: {parsed.plain_text}\n")

        except Exception as e:
            print(f"  ⚠ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Inkpilot Standalone")
    parser.add_argument("--cli", action="store_true", help="CLI mode (no GUI)")
    parser.add_argument("-i", "--input", help="Input SVG file")
    parser.add_argument("-o", "--output", default="inkpilot_output.svg", help="Output SVG file")
    parser.add_argument("-W", "--width", type=int, default=1024)
    parser.add_argument("-H", "--height", type=int, default=1024)
    args = parser.parse_args()

    if args.cli:
        run_cli(args)
    else:
        run_gui(args)


if __name__ == "__main__":
    main()
