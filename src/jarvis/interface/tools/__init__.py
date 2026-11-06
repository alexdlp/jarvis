from jarvis.interface.tools.capture import capture_workitem
from jarvis.interface.tools.google_calendar import connect_google_calendar
from jarvis.interface.tools.health import hello

TOOLS = [
    capture_workitem,
    hello,
    connect_google_calendar
]

__all__ = ["TOOLS"]
