#!/usr/bin/env python3
"""Inkpilot MCP launcher — ensures correct path."""
import sys
import os

# Add project dir to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from inkpilot_mcp.server import run
run()
