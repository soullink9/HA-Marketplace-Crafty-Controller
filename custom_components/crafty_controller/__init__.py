"""Crafty Controller: start/stop Minecraft servers from Home Assistant and see their status.

Set-up overview (see CONTRIBUTING.md for the full tour):
    config_flow.py  asks for the Crafty URL + API token
    coordinator.py  polls Crafty every 30 s and holds the data
    entity.py       base entity + helper that creates entities per server
    switch.py       on/off switch per server
    binary_sensor.py online/offline status per server
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import CraftyConfigEntry, CraftyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: CraftyConfigEntry) -> bool:
    """Create the coordinator, do the first poll, then set up the platforms."""
    entry.runtime_data = CraftyCoordinator(hass, entry)
    # Raises ConfigEntryNotReady (HA retries automatically) if Crafty is unreachable.
    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CraftyConfigEntry) -> bool:
    """Unload the platforms; the coordinator is discarded with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
