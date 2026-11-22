"""Polls Crafty Controller and keeps the latest state of every server."""

import asyncio
import logging

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import request, server_path, valid_server_id
from .const import DOMAIN, ERRORS, MAX_NAME_LENGTH, MAX_PARALLEL_STATS, MAX_SERVERS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Typed alias: lets `entry.runtime_data` be recognised as a CraftyCoordinator.
type CraftyConfigEntry = ConfigEntry[CraftyCoordinator]


def _flag(value) -> bool:
    """True only for a real True or the string "True" (Crafty sends either); anything else counts as False."""
    return value is True or value == "True"


def _port(value) -> int | None:
    """A port number (1-65535) from an int or a string of digits, else None."""
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535:
        return value
    return None


def _parse_server(server_id: str, server: dict, stats: dict) -> dict:
    """Combine one entry of GET /servers with its GET /servers/{id}/stats reply.

    Every field is type-checked, so odd values become a safe default instead of reaching an entity. Returns the
    small record the entities read:
        name    - display name from Crafty (the server ID if it has none), at most MAX_NAME_LENGTH characters
        port    - Minecraft port (None if Crafty did not report a valid one)
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

    name = server.get("server_name")
    name = name.strip()[:MAX_NAME_LENGTH] if isinstance(name, str) else ""
    return {
        "name": name or server_id,
        "port": _port(server.get("server_port")) or _port(field("server_port")),
        "running": _flag(field("running")),
        # Crafty reports the ping result as the string "True" or a real boolean; a missing value counts as offline.
        "online": _flag(field("int_ping_results")),
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
        self._stats_slots = asyncio.Semaphore(MAX_PARALLEL_STATS)

    async def call(self, method: str, path: str) -> dict:
        """Call a Crafty endpoint, e.g. call("GET", "/servers"). Raises const.ERRORS."""
        return await request(self.session, method, self.base + path, self._token)

    async def _stats(self, server_id: str) -> dict:
        """One server's stats, waiting for a free slot so at most MAX_PARALLEL_STATS requests run at once."""
        async with self._stats_slots:
            return await self.call("GET", server_path(server_id, "stats"))

    async def _async_update_data(self) -> dict[str, dict]:
        """List the servers, then fetch every server's stats, a few at a time.

        A server whose stats fail is left out of the data, so only its own entities go unavailable. A token Crafty
        rejects raises ConfigEntryAuthFailed, which makes Home Assistant ask for a new one (the reauth flow)."""
        # Step 1: list the servers this API token can see. If this fails, the whole
        # update fails and every entity goes unavailable until Crafty answers again.
        try:
            listed = (await self.call("GET", "/servers")).get("data")
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed("Crafty rejected the API token") from err
            raise UpdateFailed(err) from err
        except ERRORS as err:
            raise UpdateFailed(err) from err
        if listed is None:
            listed = []
        if not isinstance(listed, list):
            raise UpdateFailed("Crafty's server list is not a list")

        # Keep only proper server records with a valid ID, each ID once.
        servers: dict[str, dict] = {}
        for record in listed:
            server_id = valid_server_id(record.get("server_id")) if isinstance(record, dict) else None
            if server_id is None:
                _LOGGER.debug("Skipping a server record without a valid server_id")
                continue
            servers.setdefault(server_id, record)
        if len(servers) > MAX_SERVERS:
            _LOGGER.warning("Crafty listed %d servers; only the first %d are shown", len(servers), MAX_SERVERS)
            servers = dict(list(servers.items())[:MAX_SERVERS])
        _LOGGER.debug("Crafty returned %d server(s)", len(servers))

        # Step 2: fetch each server's stats. return_exceptions=True means
        # one failing server (e.g. a 403) does not take the others down with it.
        stats = await asyncio.gather(*(self._stats(server_id) for server_id in servers), return_exceptions=True)

        data: dict[str, dict] = {}
        for (server_id, server), result in zip(servers.items(), stats):
            if isinstance(result, BaseException):
                # Leave it out of `data`; its entities will show as unavailable.
                _LOGGER.debug("Stats failed for %s: %s", server_id, result)
                continue
            data[server_id] = _parse_server(server_id, server, result)
        return data
