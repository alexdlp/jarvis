"""The tools an agent can invoke.

TOOLS is the single list of what Jarvis exposes: adding a capability means
writing the function in one of the modules here and naming it below. The
server registers whatever is in the list and knows nothing else about them.

The functions are plain functions, not decorated with @mcp.tool(). A decorator
binds to one server instance, and this application builds a fresh one on every
invocation — so the tools would have to be defined inside that build. Keeping
them undecorated is what lets them live in their own modules, and it also means
they can be called directly in a test with no server at all.

The agent chooses between them by reading their docstrings, so those are the
selection logic, not documentation.
"""

from jarvis.interface.tools.health import hello

TOOLS = [
    hello,
]

__all__ = ["TOOLS"]
