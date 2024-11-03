from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from .const import DOMAIN, TITLE

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the custom clock switch based on config entry."""
    activation_time = config_entry.options.get("activation_time", config_entry.data.get("activation_time"))

    # Assuming the sensor has an entity_id like "sensor.my_clock_sensor_entity"
    sensor_entity_id = "sensor.custom_clock"

    # Add the switch with the `config_entry` and the `entity_id` of the sensor
    async_add_entities([ClockSwitch(config_entry.title, activation_time, sensor_entity_id, config_entry)])


class ClockSwitch(SwitchEntity):
    """Representation of the clock switch."""
    
    def __init__(self, name, activation_time, sensor_entity_id, config_entry):
        """Initialize the clock switch."""
        self._attr_name = name or "pv_controller_switch"
        self._state = False
        self._activation_time = config_entry.options.get("activation_time", activation_time)  # Use the updated value
        self._sensor_entity_id = sensor_entity_id  # Store the entity_id of the sensor
        self._config_entry = config_entry

    @property
    def unique_id(self):
        """Return a unique ID for this switch."""
        return f"{self._config_entry.entry_id}_unique_id"

    @property
    def device_info(self):
        """Return device information to link the entity to the config entry."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": f"{TITLE}",
            "manufacturer": "EMG",
            "model": f"{TITLE} Switch",
        }        

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.schedule_update_ha_state()

    async def async_update(self):
        """Fetch new state data for the switch."""
        # Get the updated options from the config_entry
        self._activation_time = self._config_entry.options.get("activation_time", "12:00")
        sensor = self.hass.states.get(self._sensor_entity_id)
        if sensor and sensor.state >= self._activation_time:
            self._state = True
        else:
            self._state = False