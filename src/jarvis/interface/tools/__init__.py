# Import UI-enabled modules so their decorators register tools with Apps.
from jarvis.interface.tools import capture as _capture
from jarvis.interface.tools.google_calendar import connect_google_calendar
from jarvis.interface.tools.health import hello

TOOLS = [
    hello,
    connect_google_calendar
]

__all__ = ["TOOLS"]
