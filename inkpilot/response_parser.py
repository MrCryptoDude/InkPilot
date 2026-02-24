"""
Inkpilot — Response Parser
Parses Claude's responses to extract SVG elements and/or command sequences.
"""
import re
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedResponse:
    """Result of parsing a Claude response."""
    svg_fragments: list[str] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    command_description: str = ""
    plain_text: str = ""
    raw: str = ""


def parse_response(response_text: str) -> ParsedResponse:
    """
    Parse Claude's response into structured parts.
    
    Looks for:
    - ```svg ... ``` blocks → SVG fragments
    - ```inkpilot-commands ... ``` blocks → command JSON
    - Everything else → plain text (explanations, notes)
    """
    result = ParsedResponse(raw=response_text)

    # --- Extract SVG blocks ---
    svg_pattern = r"```svg\s*\n(.*?)```"
    svg_matches = re.findall(svg_pattern, response_text, re.DOTALL)
    for match in svg_matches:
        svg_str = match.strip()
        if svg_str:
            result.svg_fragments.append(svg_str)

    # --- Extract command blocks ---
    cmd_pattern = r"```inkpilot-commands\s*\n(.*?)```"
    cmd_matches = re.findall(cmd_pattern, response_text, re.DOTALL)
    for match in cmd_matches:
        try:
            cmd_data = json.loads(match.strip())
            if isinstance(cmd_data, dict):
                result.command_description = cmd_data.get("description", "")
                actions = cmd_data.get("actions", [])
                if isinstance(actions, list):
                    result.commands.extend(actions)
            elif isinstance(cmd_data, list):
                result.commands.extend(cmd_data)
        except json.JSONDecodeError as e:
            result.plain_text += f"\n[Parse error in commands: {e}]"

    # --- Extract plain text (everything outside code blocks) ---
    cleaned = response_text
    # Remove all code blocks
    cleaned = re.sub(r"```(?:svg|inkpilot-commands)\s*\n.*?```", "", cleaned, flags=re.DOTALL)
    # Remove any other code blocks too
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    result.plain_text = cleaned.strip()

    return result


def validate_svg_fragment(svg_str: str) -> tuple[bool, str]:
    """
    Basic validation of an SVG fragment.
    Returns (is_valid, cleaned_svg_or_error).
    """
    svg_str = svg_str.strip()

    # If it doesn't start with < it's probably not SVG
    if not svg_str.startswith("<"):
        return False, "SVG fragment doesn't start with an element"

    # Wrap in a group if it's multiple root elements
    # Check if it has multiple roots
    root_tags = re.findall(r"<(\w+)[\s>]", svg_str)
    close_tags = re.findall(r"</(\w+)>", svg_str)

    # Try to ensure it's well-formed by wrapping if needed
    try:
        from lxml import etree
        # Try parsing as-is first
        try:
            etree.fromstring(svg_str.encode("utf-8"))
            return True, svg_str
        except etree.XMLSyntaxError:
            pass

        # Try wrapping with namespace declarations
        ns_wrapped = f'<g xmlns="http://www.w3.org/2000/svg" xmlns:inkpilot="http://inkpilot.dev/ns" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">{svg_str}</g>'
        try:
            etree.fromstring(ns_wrapped.encode("utf-8"))
            return True, ns_wrapped
        except etree.XMLSyntaxError:
            pass

        # Try wrapping in a group
        wrapped = f'<g xmlns="http://www.w3.org/2000/svg" xmlns:inkpilot="http://inkpilot.dev/ns">{svg_str}</g>'
        try:
            etree.fromstring(wrapped.encode("utf-8"))
            return True, wrapped
        except etree.XMLSyntaxError as e:
            return False, f"Invalid SVG: {e}"
    except ImportError:
        # No lxml available, do basic check
        return True, svg_str


def validate_command(cmd: dict) -> tuple[bool, str]:
    """Basic validation of a command dict."""
    if not isinstance(cmd, dict):
        return False, "Command is not a dictionary"
    if "action" not in cmd:
        return False, "Command missing 'action' field"
    return True, ""
