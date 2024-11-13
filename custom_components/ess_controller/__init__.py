"""Custom component to manage a photovoltaic installation."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .coordinator import PVControllerUpdateCoordinator as Coordinator
from .const import DOMAIN

# Define constants
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER]
# PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT, Platform.BINARY_SENSOR, Platform.BUTTON]

# Define _LOGGER
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the pv_controller component from config entry."""
    _LOGGER.debug("Starting async_setup_entry")

    # Create the coordinator
    coordinator = Coordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Save the coordinator in the data dictionary
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    # # Default values for input numbers
    # if "user_soc_safety_margin_initial_value" not in config_entry.data:
    #     new_data = {**config_entry.data, "user_soc_safety_margin_initial_value": 10}
    #     hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Load the platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Add update listener
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await coordinator.async_initialize() # Read user inputs from store    

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    # Combine the original data with the options (if any)
    entry_data = {**config_entry.data, **config_entry.options}

    # Force an immediate update
    hass.config_entries.async_update_entry(config_entry, data=entry_data)

    # Reload the integration
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    if coordinator:
        await coordinator.async_close()
    if unload_ok := await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
