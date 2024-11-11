from datetime import datetime, timedelta
import pytz
import time
import logging
from zoneinfo import ZoneInfo
import asyncio
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorDeviceClass
from .utils import dict_to_markdown_table

from .const import DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""    
    # Get the coordinator from the config_entry
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add PVPC_Buy_Sensor
    name = config_entry.title + " PVPC Buy"
    async_add_entities([PVPC_Buy_Sensor(coordinator, name, config_entry)])

    # Add PVPC_Sell_Sensor
    name = config_entry.title + " PVPC Sell"
    async_add_entities([PVPC_Sell_Sensor(coordinator, name, config_entry)])   

    # Add ForecastSolar_Sensor
    name = config_entry.title + " Solar Forecast"
    async_add_entities([ForecastSolar_Sensor(coordinator, name, config_entry)])

    # Add ForecastDemand_Sensor
    name = config_entry.title + " Demand Forecast"
    async_add_entities([ForecastDemand_Sensor(coordinator, name, config_entry)]) 

    # Add TargetSoC_Sensor
    name = config_entry.title + " SoC Target"
    async_add_entities([TargetSoC_Sensor(coordinator, name, config_entry)])

    # Add CurrentSoC_Sensor 
    name = config_entry.title + " SoC Current"
    async_add_entities([CurrentSoC_Sensor(coordinator, name, config_entry)])

    # Add MinSoC_Sensor
    name = config_entry.title + " SoC Min"
    async_add_entities([MinSoC_Sensor(coordinator, name, config_entry)])

    # Add UpdateTime_Sensor for the last time optimization took place
    name = config_entry.title + " UT SoC Target"
    coordinator_param = "target_socs_last_update"
    async_add_entities([UpdateTime_Sensor(coordinator, name, coordinator_param, config_entry)])

    # Add UpdateTime_Sensor for the last read time to ForecastSolar
    name = config_entry.title + " UT Solar Forecast"
    coordinator_param = "forecast_solar_last_update"
    async_add_entities([UpdateTime_Sensor(coordinator, name, coordinator_param, config_entry)])

    # Add UpdateTime_Sensor for the last read time of the forecast demand history
    name = config_entry.title + " UT Influx History"
    coordinator_param = "influx_last_update"
    async_add_entities([UpdateTime_Sensor(coordinator, name, coordinator_param, config_entry)])

    # Add EffectiveForecastSolar_Sensor
    name = config_entry.title + " Solar Effective Forecast"             
    async_add_entities([EffectiveForecastSolar_Sensor(coordinator, name, config_entry)])

    # Add SolarForeToReal_Sensor
    name = config_entry.title + " Solar Fore to Real"
    async_add_entities([SolarForeToReal_Sensor(coordinator, name, config_entry)])

    # Add PulpResultsTextSensor
    name = config_entry.title + " Pulp Results"
    async_add_entities([PulpResultsTextSensor(coordinator, name, config_entry)])

    # Add SetPoint_Sensor
    name = config_entry.title + " Proposed SetPoint"
    async_add_entities([SetPoint_Sensor(coordinator, name, config_entry)])
    
def get_device_info(config_entry):
    """Return device information to link the entity to a device."""
    return {
        "identifiers": {(DOMAIN, config_entry.entry_id)},
        "name": f"{TITLE}",
        "manufacturer": "EMG",
        "model": f"{TITLE} Sensor",
    }       

# Classes linked to the coordinator
class PVPC_Buy_Sensor(SensorEntity):
    """Representation of a PVPC Buy Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the PVPC Buy Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:currency-eur"
        self._attr_unit_of_measurement = "€/kWh"
        self._state = None
        self._attr_extra_state_attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property    
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.buy_prices_useful_dict:
            attributes.update({str(k): v for k, v in self._coordinator.buy_prices_useful_dict.items()})
        return attributes  
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.current_buy_price
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)     

class PVPC_Sell_Sensor(SensorEntity):
    """Representation of a PVPC Sell Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the PVPC Sell Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:currency-eur"
        self._attr_unit_of_measurement = "€/kWh"
        self._state = None
        self._attr_extra_state_attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
     
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property    
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.sell_prices_useful_dict:
            attributes.update({str(k): v for k, v in self._coordinator.sell_prices_useful_dict.items()})
        return attributes 
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.current_sell_price
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)     

class ForecastSolar_Sensor(SensorEntity):
    """Representation of a Forecast Solar Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Forecast Solar Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:flash"
        self._attr_unit_of_measurement = "Wh"
        self._attr_device_class = "energy"
        self._state = None
        self._attr_extra_state_attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
 
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.forecast_solar_useful_dict:
            attributes.update({str(k): v for k, v in self._coordinator.forecast_solar_useful_dict.items()})
        return attributes
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.forecast_solar_energy_next_hour
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class ForecastDemand_Sensor(SensorEntity):
    """Representation of a Forecast Demand Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Forecast Demand Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:flash"
        self._attr_unit_of_measurement = "Wh"
        self._attr_device_class = "energy"
        self._state = None
        self._attr_extra_state_attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.predicted_demand:
            attributes.update({str(k): v for k, v in self._coordinator.predicted_demand.items()})
        return attributes

    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.predicted_demand_current_hour
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class TargetSoC_Sensor(SensorEntity):
    """Representation of a Target SoC Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Target SoC Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:battery-50"
        self._attr_unit_of_measurement = "%"
        self._state = None
        self._attr_extra_state_attributes = None
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.target_socs:
            attributes.update({str(k): v for k, v in self._coordinator.target_socs.items()})
        return attributes
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        if self._coordinator.target_soc_current_hour is not None:
            self._state = round(self._coordinator.target_soc_current_hour, 1)
        else:
            self._state = None
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class CurrentSoC_Sensor(SensorEntity):
    """Representation of a Current SoC Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Current SoC Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:battery-50"
        self._attr_unit_of_measurement = "%"
        self._state = None
        self._attr_extra_state_attributes = None
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.current_soc
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state) 

class MinSoC_Sensor(SensorEntity):
    """Representation of a Minimum SoC Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Minimum SoC Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:battery-50"
        self._attr_unit_of_measurement = "%"
        self._state = None
        self._attr_extra_state_attributes = None
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        self._state = self._coordinator.current_min_soc
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class UpdateTime_Sensor(SensorEntity):
    """Representation of an Update Time Sensor."""

    def __init__(self, coordinator, name, coordinator_param, config_entry):
        """Initialize the Update Time Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:clock"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._state = None
        self._attr_extra_state_attributes = None
        self.coordinator_param = coordinator_param
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        # Get the value of the coordinator variable using the variable name
        value = getattr(self._coordinator, self.coordinator_param, None)

        if isinstance(value, datetime):
            # Get the Home Assistant timezone
            if value.tzinfo is None:
                # Assign timezone if missing
                value = self._coordinator.class_local_timezone.localize(value)
            else:
                # Convert to the Home Assistant timezone
                value = value.astimezone(self._coordinator.class_local_timezone)
        self._state = value
        _LOGGER.debug(f"UpdateTime_Sensor: {self.coordinator_param}={self._state}")
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self.async_write_ha_state))
        await self.async_update()

class EffectiveForecastSolar_Sensor(SensorEntity):
    """Representation of an Effective Forecast Solar Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Effective Forecast Solar Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:flash"
        self._attr_unit_of_measurement = "Wh"
        self._attr_device_class = "energy"
        self._state = None
        self._attr_extra_state_attributes = None
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.effective_forecast_solar_useful_dict:
            attributes.update({str(k): v for k, v in self._coordinator.effective_forecast_solar_useful_dict.items()})
        return attributes
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        if self._coordinator.effective_forecast_solar_useful_dict:
            # Extract the value where the key is current_datetime, keys in iso format '2024-11-02T22:00:00'
            current_datetime = datetime.now().replace(minute=0, second=0, microsecond=0)
            current_datetime = current_datetime.isoformat()
            value = self._coordinator.effective_forecast_solar_useful_dict.get(current_datetime)
        else:
            value = None
        self._state = value
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class SolarForeToReal_Sensor(SensorEntity):
    """Representation of a Solar Forecast to Real Sensor."""

    def __init__(self, coordinator, name, config_entry):
        """Initialize the Solar Forecast to Real Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:percent"
        self._attr_unit_of_measurement = "%"
        self._state = None
        self._attr_extra_state_attributes = None
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        attributes['unit_of_measurement'] = self._attr_unit_of_measurement
        if self._coordinator.fore_to_real_dict:
            attributes.update({str(k): v for k, v in self._coordinator.fore_to_real_dict.items()})
        return attributes
    
    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
        if self._coordinator.fore_to_real_dict:
            # Extract the value where the key matches the hour of datetime.now()
            value = self._coordinator.fore_to_real_dict.get(datetime.now().hour).get('fore_to_real')
        else:
            value = None
        if value is not None:
            value = round(100 * value, 1)
        self._state = value
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

class PulpResultsTextSensor(SensorEntity):
    def __init__(self, coordinator, name, config_entry):
        """Initialize the PulpResultsTextSensor Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:information"
        self._state = None
        self._attr_extra_state_attributes = None
    
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)        

    @property
    def state(self):
        return self._state
    
    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        if self._coordinator.pulp_json_results is not None:
            txt= str(self._coordinator.pulp_json_results)
            attributes['results'] = txt.replace("'", '"')
            attributes['md_table'] = dict_to_markdown_table(self._coordinator.pulp_json_results)
        else:
            attributes['results'] = "No data available"
        return attributes    

    def update(self):
        if self._coordinator.pulp_json_results is not None:
            # Trim lengthy results
            txt= str(self._coordinator.pulp_json_results)
            if len(txt) > 20:
                txt= txt[:20] + "..."
        else:
            txt = "No data available"
        self._state = txt.replace("'", '"')

class SetPoint_Sensor(SensorEntity):
    """
    SetPoint Sensor:
    This sensor is used to expose to external automations the value 
    that the user has configured for the maximum power that can be 
    purchased from the electrical grid in Watts.
    """

    def __init__(self, coordinator, name, config_entry):
        """Initialize the SetPoint Sensor."""
        self._coordinator = coordinator
        self._attr_name = name
        self._config_entry = config_entry
        self._attr_unique_id = f"{coordinator.unique_id}_{name}"
        self._attr_icon = "mdi:flash"
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._state = None
        self._attr_extra_state_attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link the entity to a device."""
        return get_device_info(self._config_entry)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._attr_unit_of_measurement

    async def async_update(self):
        """Update the sensor."""
        self._state = self._coordinator.proposed_setpoint_W 
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._coordinator.async_add_listener(self.async_write_ha_state)        