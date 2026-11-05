"""Switch platform: one on/off switch per Crafty server."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import ERRORS
from .coordinator import CraftyConfigEntry
from .entity import CraftyEntity, async_add_servers


async def async_setup_entry(hass: HomeAssistant, entry: CraftyConfigEntry, async_add_entities) -> None:
    """Create a switch for every server (and for servers that appear later)."""
    async_add_servers(entry, async_add_entities, CraftySwitch)


class CraftySwitch(CraftyEntity, SwitchEntity):
    """ON while the Minecraft server is running. Toggling starts or stops it."""

    _key = "power"  # part of the unique ID; never change
    _attr_name = None  # no suffix: the switch is named after the server itself

    @property
    def is_on(self) -> bool:
        """On while Crafty reports the server process running."""
        return self.server.get("running", False)

    async def _send(self, action: str, running: bool) -> None:
        """Send a Crafty action ("start_server" / "stop_server") and update the state."""
        try:
            await self.coordinator.call("POST", f"/servers/{self.server_id}/action/{action}")
        except ERRORS as err:
            # Surface a readable error in the UI and leave the state unchanged.
            raise HomeAssistantError(f"Crafty {action} failed: {err}") from err
        # Optimistic update: show the new state immediately instead of waiting for the
        # next poll (which could still report the old state for a moment and make the
        # switch flicker back). The next poll confirms or corrects it.
        self.server["running"] = running
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Start the Minecraft server."""
        await self._send("start_server", True)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the Minecraft server."""
        await self._send("stop_server", False)
