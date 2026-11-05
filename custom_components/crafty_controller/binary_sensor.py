"""Binary sensor platform: an online/offline status sensor per Crafty server."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from .coordinator import CraftyConfigEntry
from .entity import CraftyEntity, async_add_servers


async def async_setup_entry(hass: HomeAssistant, entry: CraftyConfigEntry, async_add_entities) -> None:
    """Create a status sensor for every server (and for servers that appear later)."""
    async_add_servers(entry, async_add_entities, CraftyStatus)


class CraftyStatus(CraftyEntity, BinarySensorEntity):
    """ON when the server answers Crafty's ping (players can connect).

    This differs from the switch: while a server is still starting, the switch is
    already ON (process running) but this sensor stays OFF until it is reachable.
    """

    _key = "status"  # part of the unique ID; never change
    _attr_name = "Status"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Online once Crafty's ping gets an answer, i.e. players can join (still off while the server starts)."""
        return self.server.get("online", False)
