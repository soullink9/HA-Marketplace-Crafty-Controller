"""Base entity shared by the switch and the status sensor, plus a set-up helper."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CraftyConfigEntry, CraftyCoordinator


class CraftyEntity(CoordinatorEntity[CraftyCoordinator]):
    """One entity belonging to one Crafty server.

    Every Crafty server becomes a Home Assistant *device*; the switch and the status
    sensor are entities on that device. Subclasses set `_key` (used in the unique ID,
    so do not change it once released or existing entities will be orphaned).
    """

    _attr_has_entity_name = True
    _key: str

    def __init__(self, coordinator: CraftyCoordinator, server_id: str) -> None:
        """Attach the entity to its server's device. The unique ID is the server ID plus `_key`."""
        super().__init__(coordinator)
        self.server_id = server_id
        self._attr_unique_id = f"{server_id}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server_id)},
            name=coordinator.data[server_id]["name"],
        )

    @property
    def server(self) -> dict:
        """This server's latest record, or {} if Crafty no longer reports it."""
        return (self.coordinator.data or {}).get(self.server_id, {})

    @property
    def available(self) -> bool:
        """Unavailable if the last poll failed, or this server dropped out of the data (removed in Crafty, or its
        stats request failed)."""
        return super().available and self.server_id in (self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict:
        """The server's port, shown as an attribute on every entity of the server."""
        return {"port": self.server.get("port")}


def async_add_servers(
    entry: CraftyConfigEntry,
    async_add_entities: Callable,
    entity_class: Callable[[CraftyCoordinator, str], CraftyEntity],
) -> None:
    """Create `entity_class(coordinator, server_id)` for every server.

    Runs once at set-up, and again after every poll so that servers added in Crafty
    later get their entities without reloading the integration.
    """
    coordinator = entry.runtime_data
    known: set[str] = set()  # server IDs that already have an entity

    @callback
    def _add_new() -> None:
        """Add entities for servers that don't have them yet (called at set-up and after every poll)."""
        new = set(coordinator.data or {}) - known
        known.update(new)
        async_add_entities([entity_class(coordinator, sid) for sid in sorted(new)])

    # Re-check after each poll; the listener is removed automatically on unload.
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
    _add_new()
