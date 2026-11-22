"""Switch platform: one on/off switch per Crafty server."""

import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import const
from .api import server_path
from .const import ERRORS
from .coordinator import CraftyConfigEntry, CraftyCoordinator
from .entity import CraftyEntity, async_add_servers


async def async_setup_entry(hass: HomeAssistant, entry: CraftyConfigEntry, async_add_entities) -> None:
    """Create a switch for every server (and for servers that appear later)."""
    async_add_servers(entry, async_add_entities, CraftySwitch)


class CraftySwitch(CraftyEntity, SwitchEntity):
    """ON while the Minecraft server is running. Toggling starts or stops it."""

    _key = "power"  # part of the unique ID; never change
    _attr_name = None  # no suffix: the switch is named after the server itself

    def __init__(self, coordinator: CraftyCoordinator, server_id: str) -> None:
        """Start with nothing pending: the switch shows what Crafty reports."""
        super().__init__(coordinator, server_id)
        # After a start or stop: the state asked for, and until when (time.monotonic()) to show it while Crafty
        # catches up. None when nothing is pending.
        self._pending: bool | None = None
        self._pending_until = 0.0

    @property
    def is_on(self) -> bool:
        """On while Crafty reports the server process running.

        Right after a start or stop it shows the state asked for instead, until Crafty reports that state or
        PENDING_STATE_SECONDS pass (then whatever Crafty reports wins, e.g. a server that crashed on start)."""
        running = self.server.get("running", False)
        if self._pending is not None and (running == self._pending or time.monotonic() >= self._pending_until):
            self._pending = None
        return running if self._pending is None else self._pending

    async def _send(self, action: str, running: bool) -> None:
        """Send a Crafty action ("start_server" / "stop_server"), then ask the coordinator to refresh from Crafty."""
        try:
            await self.coordinator.call("POST", server_path(self.server_id, "action", action))
        except ERRORS as err:
            # Surface a readable error in the UI and leave the state unchanged.
            raise HomeAssistantError(f"Crafty {action} failed: {err}") from err
        # Show the new state straight away (Crafty can take a few seconds to report it, and the switch would flick
        # back meanwhile), without touching the coordinator's data, then refresh from Crafty so the real state
        # follows as soon as Crafty has it.
        self._pending = running
        self._pending_until = time.monotonic() + const.PENDING_STATE_SECONDS
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the Minecraft server."""
        await self._send("start_server", True)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the Minecraft server."""
        await self._send("stop_server", False)
