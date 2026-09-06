"""Tools that answer whether Jarvis is reachable and working.

`hello` is the placeholder that proved the whole path end to end — client,
authorizer, lambda, SDK, response — before there was anything real behind it.
It stays until the backlog tools replace it as the obvious thing to call.
"""


def hello() -> str:
    """Return a test greeting."""
    return "Hello from Jarvis"
