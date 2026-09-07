"""Launch the MCP Inspector using this project's environment."""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from mcp.cli import app

load_dotenv(override=True)
sys.argv = ["mcp", "dev", "src\\mcp_server\\server.py"]

if __name__ == "__main__":
    app()
