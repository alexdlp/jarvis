"""UI resources exposed by the Jarvis MCP server."""

from pathlib import Path

from mcp.server.apps import APP_MIME_TYPE, Apps
from mcp.server.mcpserver.resources import FileResource


# Resolve assets relative to this module inside the deployment package.
UI_ASSETS_DIR = Path(__file__).resolve().parent / "ui_assets"

# Declare the stable URI once. Tools reference this resource object.
TODO_WIDGET = FileResource(
    uri="ui://jarvis/todo.html",
    name="todo-widget",
    title="Jarvis tasks",
    mime_type=APP_MIME_TYPE,
    path=UI_ASSETS_DIR / "todo.html",
    encoding="utf-8",
)

# Collect UI resources and tools without creating a server at import time.
apps = Apps()
apps.add_resource(TODO_WIDGET)
