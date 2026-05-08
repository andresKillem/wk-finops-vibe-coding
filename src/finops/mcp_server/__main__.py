"""Entrypoint for ``python -m finops.mcp_server.server`` style invocations."""
import sys

from finops.mcp_server.server import run_server

run_server(http="--http" in sys.argv)
