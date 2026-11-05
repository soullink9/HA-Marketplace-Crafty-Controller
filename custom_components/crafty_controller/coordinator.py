"""Polls Crafty Controller and keeps the latest state of every server."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import request
from .const import DOMAIN, ERRORS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Typed alias: lets `entry.runtime_data` be recognised as a CraftyCoordinator.
type CraftyConfigEntry = ConfigEntry[CraftyCoordinator]


def _parse_server(server: dict, stats: dict) -> dict:
    """Combine one entry of GET /servers with its GET /servers/{id}/stats reply.

    Returns the small record the entities read:
        name    - display name from Crafty
        port    - Minecraft port (may be None if Crafty did not report one)
        running - the server process is running (what the switch shows)
        online  - the server answers Crafty's ping, i.e. players can join
                  (what the Status sensor shows; stays False while it is starting)
    """
    # The API spec is inconsistent about whether stats fields sit at the top level
    # or inside "data", so look in both places.
    nested = stats.get("data") if isinstance(stats.get("data"), dict) else {}

    def field(key: str):
        """A stats field from the top level, or from inside "data" when it isn't there."""
        return stats.get(key, nested.get(key))

    return {
        "name": server.get("server_name") or server["server_id"],
        "port": server.get("server_port") or field("server_port"),
        "running": bool(field("running")),
        # Crafty reports the ping result as the string "True" or a real boolean;
        # comparing the string form handles both, and a missing value counts as offline.
        "online": str(field("int_ping_results")) == "True",
    }


class CraftyCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Fetches every server's state each UPDATE_INTERVAL.

    `self.data` is a dict keyed by Crafty server ID, values as built by _parse_server.
    A server missing from `data` is shown as unavailable by its entities.
    """

    def __init__(self, hass: HomeAssistant, entry: CraftyConfigEntry) -> None:
        """Set up the API address, session and token. The session follows the entry's SSL check setting."""
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=UPDATE_INTERVAL)
        self.base = entry.data[CONF_URL].rstrip("/") + "/api/v2"
        self.session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
        self._token = entry.data[CONF_TOKEN]

    async def call(self, method: str, path: str) -> dict:
        """Call a Crafty endpoint, e.g. call("GET", "/servers"). Raises const.ERRORS."""
        return await request(self.session, method, self.base + path, self._token)

    async def _async_update_data(self) -> dict[str, dict]:
        """List the servers, then fetch every server's stats in parallel.

        A server whose stats fail is left out of the data, so only its own entities go unavailable."""
        # Step 1: list the servers this API token can see. If this fails, the whole
        # update fails and every entity goes unavailable until Crafty answers again.
        try:
            listed = (await self.call("GET", "/servers")).get("data")
        except ERRORS as err:
            raise UpdateFailed(err) from err

        # Ignore anything that is not a proper server record.
        servers = [s for s in listed or [] if isinstance(s, dict) and s.get("server_id")]
        _LOGGER.debug("Crafty returned %d server(s)", len(servers))

        # Step 2: fetch each server's stats in parallel. return_exceptions=True means
        # one failing server (e.g. a 403) does not take the others down with it.
        stats = await asyncio.gather(
            *(self.call("GET", f"/servers/{s['server_id']}/stats") for s in servers),
            return_exceptions=True,
        )

        data: dict[str, dict] = {}
        for server, result in zip(servers, stats):
            if isinstance(result, BaseException):
                # Leave it out of `data`; its entities will show as unavailable.
                _LOGGER.debug("Stats failed for %s: %s", server["server_id"], result)
                continue
            data[server["server_id"]] = _parse_server(server, result)
        return data
