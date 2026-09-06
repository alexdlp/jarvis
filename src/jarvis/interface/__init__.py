"""The boundary between Jarvis and whatever agent is calling it.

Everything MCP-facing lives here: the tools an agent can invoke, the OAuth
metadata a client reads before it has a token, and the assembly of the two into
an ASGI application.
"""

from jarvis.interface.server import build_starlette_server

__all__ = ["build_starlette_server"]
