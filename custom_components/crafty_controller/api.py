"""A tiny Crafty Controller API client.

There is exactly one function here on purpose: both the poller (coordinator.py) and
the config flow (config_flow.py) use it, so timeouts, auth and response checking
live in a single place.
"""

from __future__ import annotations

from aiohttp import ClientSession

from .const import TIMEOUT


async def request(session: ClientSession, method: str, url: str, token: str) -> dict:
    """Call a Crafty API v2 endpoint and return the decoded JSON body.

    Raises one of const.ERRORS on any failure. For HTTP errors the exception is an
    aiohttp ClientResponseError, whose `.status` lets the config flow tell a bad
    token (401/403) apart from other problems.
    """
    async with session.request(method, url, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        # content_type=None: do not insist on a JSON Content-Type header. A reverse
        # proxy may send something odd; a non-JSON body still fails (ValueError).
        body = await resp.json(content_type=None)

    # Crafty wraps every reply as {"status": "ok", "data": ...}. Anything else
    # (including a JSON list or a login page that happened to return 200) is an error.
    if not isinstance(body, dict) or body.get("status") != "ok":
        raise ValueError("Crafty returned an error or an unexpected response")
    return body
