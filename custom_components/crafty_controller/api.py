"""A tiny Crafty Controller API client.

`request` is the one place that talks to Crafty: both the poller (coordinator.py) and the config flow
(config_flow.py) use it, so timeouts, auth and response checking live in a single place. `server_path` builds the
path for one server, so a server ID always reaches a URL checked and encoded.
"""

import json
from urllib.parse import quote

from aiohttp import ClientSession

from .const import MAX_RESPONSE_BYTES, SERVER_ID_PATTERN, TIMEOUT


def valid_server_id(value) -> str | None:
    """The server ID as a string if it looks like a Crafty server ID (a UUID or a number), else None."""
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if isinstance(value, str) and SERVER_ID_PATTERN.fullmatch(value):
        return value
    return None


def server_path(server_id: str, *parts: str) -> str:
    """The API path for one server, e.g. server_path(sid, "stats") -> "/servers/<sid>/stats".

    Raises ValueError (one of const.ERRORS) for an ID that isn't valid; a valid one is percent-encoded anyway.
    """
    if valid_server_id(server_id) != server_id:
        raise ValueError(f"Not a valid Crafty server ID: {server_id!r}")
    return "/".join(["/servers", quote(server_id, safe=""), *parts])


async def request(session: ClientSession, method: str, url: str, token: str) -> dict:
    """Call a Crafty API v2 endpoint and return the decoded JSON body.

    Raises one of const.ERRORS on any failure. For HTTP errors the exception is an
    aiohttp ClientResponseError, whose `.status` lets callers tell a bad token
    (401/403) apart from other problems.

    Redirects are not followed: the token is only ever sent to the address that was set up, and a redirect (often a
    reverse proxy sending http:// to https://) is reported as an error, so the URL can be corrected instead.
    """
    async with session.request(
        method, url, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT, allow_redirects=False
    ) as resp:
        if 300 <= resp.status < 400:
            raise ValueError(f"Crafty answered with a redirect ({resp.status}); use the address it redirects to")
        resp.raise_for_status()
        # Read at most MAX_RESPONSE_BYTES; a bigger reply is not from a healthy Crafty.
        raw = bytearray()
        async for chunk in resp.content.iter_chunked(64 * 1024):
            raw += chunk
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Crafty's reply is too big")

    # Decode it whatever the Content-Type header says (a reverse proxy may send something odd): a body that isn't
    # JSON still fails with ValueError. Absurdly deep nesting fails the same way instead of with RecursionError.
    try:
        body = json.loads(raw)
    except RecursionError as err:
        raise ValueError("Crafty's reply is nested too deeply") from err

    # Crafty wraps every reply as {"status": "ok", "data": ...}. Anything else
    # (including a JSON list or a login page that happened to return 200) is an error.
    if not isinstance(body, dict) or body.get("status") != "ok":
        raise ValueError("Crafty returned an error or an unexpected response")
    return body
