from __future__ import annotations
import voluptuous as vol
from datetime import datetime, timedelta
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PIN, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

# Constants for the integration
DOMAIN = "ess_controller"
TITLE = "ESS Controller"

# Constants with default values renamed to uppercase
DEFAULT_BATTERY_CAPACITY_WH = 2560
DEFAULT_MAX_CHARGE_ENERGY_PER_PERIOD_WH = 1200
DEFAULT_MAX_DISCHARGE_ENERGY_PER_PERIOD_WH = 1200
DEFAULT_MAX_BUY_ENERGY_PER_PERIOD_WH = 1700
DEFAULT_CHARGE_EFFICIENCY = 0.9
DEFAULT_DISCHARGE_EFFICIENCY = 0.85
DEFAULT_MIN_SOC_PERCENT = 30
DEFAULT_PVPC_BUY_ENTITY = "sensor.esios_pvpc"
DEFAULT_PVPC_SELL_ENTITY = "sensor.esios_injection_price"
DEFAULT_INFLUX_DB_URL = "http://192.168.0.100:8086"
DEFAULT_INFLUX_DB_USER = "homeassistant"
DEFAULT_INFLUX_DB_PASS = "your_password"
DEFAULT_INFLUX_DB_DATABASE = "homeassistant"
DEFAULT_ACIN_TO_ACOUT_SENSOR = "sensor.victron_vebus_acin1toacout_228"
DEFAULT_INVERTER_TO_ACOUT_SENSOR = "sensor.victron_vebus_invertertoacout_228"
DEFAULT_BATTERY_SOC_SENSOR = "sensor.victron_system_battery_soc"
DEFAULT_BATTERY_MIN_SOC_OVERRIDES_SENSOR = "sensor.victron_settings_ess_batterylife_soclimit"
DEFAULT_SOLAR_PRODUCTION_SENSOR = "sensor.victron_solarcharger_yield_user_230"
DEFAULT_FORECAST_SOLAR_ENTITY = "sensor.energy_current_hour"
# Forecast.Solar API configuration
DEFAULT_FORECAST_SOLAR_API_BASE_URL = "https://api.forecast.solar/estimate/"
DEFAULT_FORECAST_SOLAR_LATITUDE = 41.619
DEFAULT_FORECAST_SOLAR_LONGITUDE = -0.924
DEFAULT_FORECAST_SOLAR_PEAK_POWER = 1.65
DEFAULT_FORECAST_SOLAR_DECLINATION = 10
DEFAULT_FORECAST_SOLAR_AZIMUTH = 218
COORDINATOR_UPDATE_INTERVAL = timedelta(seconds=30)  # Coordinator update interval
FORECAST_UPDATE_INTERVAL = timedelta(hours=1)
RETRY_AFTER_429 = timedelta(hours=1)  # Wait after a 429 error
INFLUX_UPDATE_INTERVAL = timedelta(minutes=15)  # InfluxDB update interval
TARGET_SOC_UPDATE_INTERVAL = timedelta(minutes=20)  # Target SoC update interval
SOC_PERCENT_DEVIATION_FORCE_RECALC = 2  # Percentage deviation to force recalculation
HISTORY_SOLAR_MAX_DAYS = 7  # Maximum number of days of solar history to query
# Not used, take all the available data to train the model
# HISTORY_DEMAND_MAX_DAYS = 7  # Maximum number of days of demand history to query 

# Constants for the Prophet InfluxDB Addon
DEFAULT_PROPHET_INFLUXDB_ADDON_URL = "http://localhost:5000"

STORE_FORECAST_SOLAR_GLOBAL_KEY="ess_controller_forecast_solar"
STORE_USER_INPUT_GLOBAL_KEY="ess_controller_user_inputs"


def get_existing_or_default(config_entry, key, default):
    """Get the existing configuration value or the default value."""
    if config_entry is None:
        return default
    else:
        return config_entry.options.get(key, config_entry.data.get(key, default))
    
def create_step_one_schema(config_entry=None):
    return vol.Schema({
        vol.Required("battery_capacity_Wh", default=get_existing_or_default(config_entry, "battery_capacity_Wh", DEFAULT_BATTERY_CAPACITY_WH)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, msg="The value must be a positive integer")
        ),
        vol.Required("max_charge_energy_per_period_Wh", default=get_existing_or_default(config_entry, "max_charge_energy_per_period_Wh", DEFAULT_MAX_CHARGE_ENERGY_PER_PERIOD_WH)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, msg="The value must be a positive integer")
        ),
        vol.Required("max_discharge_energy_per_period_Wh", default=get_existing_or_default(config_entry, "max_discharge_energy_per_period_Wh", DEFAULT_MAX_DISCHARGE_ENERGY_PER_PERIOD_WH)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, msg="The value must be a positive integer")
        ),
        vol.Required("max_buy_energy_per_period_Wh", default=get_existing_or_default(config_entry, "max_buy_energy_per_period_Wh", DEFAULT_MAX_BUY_ENERGY_PER_PERIOD_WH)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, msg="The value must be a positive integer")
        ),
        vol.Required("charge_efficiency", default=get_existing_or_default(config_entry, "charge_efficiency", DEFAULT_CHARGE_EFFICIENCY)): vol.All(
            vol.Coerce(float),
            vol.Range(min=0, max=1, msg="The value must be between 0 and 1.")
        ),
        vol.Required("discharge_efficiency", default=get_existing_or_default(config_entry, "discharge_efficiency", DEFAULT_DISCHARGE_EFFICIENCY)): vol.All(
            vol.Coerce(float),
            vol.Range(min=0, max=1, msg="The value must be between 0 and 1.")
        ),
        vol.Required("min_soc_percent", default=get_existing_or_default(config_entry, "min_soc_percent", DEFAULT_MIN_SOC_PERCENT)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=100, msg="The value must be between 1 and 100")
        ),
        vol.Required("battery_purchase_price", default=get_existing_or_default(config_entry, "battery_purchase_price", 0)): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, msg="The value must be a positive integer")
        )             
    })

def create_step_two_schema(config_entry=None):
    return vol.Schema({
        vol.Required("acin_to_acout_sensor", default=get_existing_or_default(config_entry, "acin_to_acout_sensor", DEFAULT_ACIN_TO_ACOUT_SENSOR)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required("inverter_to_acout_sensor", default=get_existing_or_default(config_entry, "inverter_to_acout_sensor", DEFAULT_INVERTER_TO_ACOUT_SENSOR)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required("battery_soc_sensor", default=get_existing_or_default(config_entry, "battery_soc_sensor", DEFAULT_BATTERY_SOC_SENSOR)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        #vol.Required("battery_min_soc_overrides_sensor", default=get_existing_or_default(config_entry, "battery_min_soc_overrides_sensor", DEFAULT_BATTERY_MIN_SOC_OVERRIDES_SENSOR)): str,
        vol.Optional("battery_min_soc_overrides_sensor", default=get_existing_or_default(config_entry, "battery_min_soc_overrides_sensor", DEFAULT_BATTERY_MIN_SOC_OVERRIDES_SENSOR)): \
            selector.EntitySelector(selector.EntitySelectorConfig()),
        vol.Required("solar_production_sensor", default=get_existing_or_default(config_entry, "solar_production_sensor", DEFAULT_SOLAR_PRODUCTION_SENSOR)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required("pvpc_buy_entity", default=get_existing_or_default(config_entry, "pvpc_buy_entity", DEFAULT_PVPC_BUY_ENTITY)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required("pvpc_sell_entity", default=get_existing_or_default(config_entry, "pvpc_sell_entity", DEFAULT_PVPC_SELL_ENTITY)): \
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required("sell_allowed", default=get_existing_or_default(config_entry, "sell_allowed", False)): bool
    })

def create_step_three_schema(config_entry=None):
    return vol.Schema({
        vol.Required("forecast_solar_entity", default=get_existing_or_default(config_entry, "forecast_solar_entity", DEFAULT_FORECAST_SOLAR_ENTITY)): str,
        vol.Required("forecast_solar_latitude", default=get_existing_or_default(config_entry, "forecast_solar_latitude", DEFAULT_FORECAST_SOLAR_LATITUDE)): vol.Coerce(float),
        vol.Required("forecast_solar_longitude", default=get_existing_or_default(config_entry, "forecast_solar_longitude", DEFAULT_FORECAST_SOLAR_LONGITUDE)): vol.Coerce(float),
        vol.Required("forecast_solar_peak_power", default=get_existing_or_default(config_entry, "forecast_solar_peak_power", DEFAULT_FORECAST_SOLAR_PEAK_POWER)): vol.Coerce(float),
        vol.Required("forecast_solar_declination", default=get_existing_or_default(config_entry, "forecast_solar_declination", DEFAULT_FORECAST_SOLAR_DECLINATION)): vol.Coerce(int),
        vol.Required("forecast_solar_azimuth", default=get_existing_or_default(config_entry, "forecast_solar_azimuth", DEFAULT_FORECAST_SOLAR_AZIMUTH)): vol.Coerce(int),
        vol.Required("enable_fore_to_real_correction", default=get_existing_or_default(config_entry, "enable_fore_to_real_correction", False)): bool
    })

def create_step_four_schema(config_entry=None):
    return vol.Schema({
        vol.Required("forecast_solar_api_base_url", default=get_existing_or_default(config_entry, "forecast_solar_api_base_url", DEFAULT_FORECAST_SOLAR_API_BASE_URL)): str,
        vol.Required("influx_db_url", default=get_existing_or_default(config_entry, "influx_db_url", DEFAULT_INFLUX_DB_URL)): str,
        vol.Required("influx_db_user", default=get_existing_or_default(config_entry, "influx_db_user", DEFAULT_INFLUX_DB_USER)): str,
        vol.Required("influx_db_pass", default=get_existing_or_default(config_entry, "influx_db_pass", DEFAULT_INFLUX_DB_PASS)): str,
        vol.Required("influx_db_database", default=get_existing_or_default(config_entry, "influx_db_database", DEFAULT_INFLUX_DB_DATABASE)): str,        
        vol.Required("prophet_influxdb_addon_url", default=get_existing_or_default(config_entry, "prophet_influxdb_addon_url", DEFAULT_PROPHET_INFLUXDB_ADDON_URL)): str
    })