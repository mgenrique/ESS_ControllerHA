from datetime import datetime, timedelta
import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfTime
)

from .const import DOMAIN, TITLE
from .utils import get_device_info, async_save_value_to_store

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the number platform."""    
    # Get the coordinator from the config_entry
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add SoC Safety Margin number
    name = config_entry.title + " minSoC Margin"
    async_add_entities([SocNumber(coordinator, name, config_entry, hass,\
                        min_value=-1, max_value=50, step=1)])


# def __init__(self, coordinator, name, config_entry):
class SocNumber(NumberEntity):
    def __init__(self, coordinator, name, config_entry, hass, min_value, max_value, step):
        """Initialize a SocNumber NumberEntity."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._hass = hass
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:battery-50"    
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_info = get_device_info(config_entry)
        self._attr_device_class = "battery"
        self._attr_mode="box"
        # Verifica si coordinator.data no es None antes de asignar el valor inicial
        #self._attr_native_value = coordinator.data.get("soc_safety_margin", 10) if coordinator.data else 10
        coordinator.async_add_listener(self.async_write_ha_state)       
       
    async def async_update(self):
        """Fetch new state data for the number entity from the coordinator."""
        # Actualiza el valor desde los datos del coordinador
        #self._attr_native_value = self._coordinator.data.get("soc_safety_margin", 10) if self._coordinator.data else 10
        self._attr_native_value = self._coordinator.soc_safety_margin if self._coordinator.soc_safety_margin else 10

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        self._attr_native_value = value
        await async_save_value_to_store(self._coordinator.store_user_inputs, "user_soc_safety_margin", value)
        self._coordinator.soc_safety_margin = value
        await self._coordinator.update_current_min_soc()
        self._coordinator.force_updates_step = 3  

        # Llama a una función del coordinador para gestionar el valor actualizado, si es necesario
        await self._coordinator.async_request_refresh()  # Opcional, si necesitas refrescar el coordinador
        self.async_write_ha_state()  # Actualiza el estado en Home Assistant

