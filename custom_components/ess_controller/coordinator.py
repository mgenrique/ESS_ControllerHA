import asyncio
from datetime import datetime, timedelta
import pytz
import logging
import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.const import CONF_NAME

from .api import PVContollerAPI
from .utils import forecast_solar_api_to_dict, pvpc_raw_to_useful_dict, async_get_value_from_store
from .const import DOMAIN, FORECAST_UPDATE_INTERVAL, COORDINATOR_UPDATE_INTERVAL, \
    STORE_USER_INPUT_GLOBAL_KEY, STORE_FORECAST_SOLAR_GLOBAL_KEY

_LOGGER = logging.getLogger(__name__)


class PVControllerUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the energy device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Update Coordinator."""
        self._skip_update = 0
        self._hass = hass
        self._entry = entry
        self._attr_name = DOMAIN  # Create a unique name for the coordinator
        self._attr_should_poll = True  # Enable polling
        self.pvpc_buy_entity = entry.data["pvpc_buy_entity"]
        self.pvpc_sell_entity = entry.data["pvpc_sell_entity"]
        self.forecast_solar_entity = entry.data["forecast_solar_entity"]
        self.user_min_soc = entry.data["min_soc_percent"]  # In %, the minimum SoC value chosen by the user
        self.enable_fore_to_real_correction = entry.data["enable_fore_to_real_correction"]
        self.sell_allowed = entry.data["sell_allowed"]
        self.battery_soc_sensor=entry.data["battery_soc_sensor"]
        self.security_min_soc_sensor=entry.data["battery_min_soc_overrides_sensor"]

        self.data = None
        self.buy_prices_rawdata = None
        self.sell_prices_rawdata = None
        self.buy_prices_useful_dict = None
        self.sell_prices_useful_dict = None        

        self.current_buy_price = None
        self.current_sell_price = None

        self.forecast_solar_energy_next_hour = None
        self.forecast_solar_rawdata = None  # Downloaded data from Forecast.Solar of estimated solar production (not continuous)
        self.forecast_solar_useful_dict = None  # Useful data of estimated solar production by Forecast.Solar (continuous)
        self.effective_forecast_solar_useful_dict = None  # Corrected estimated solar production data for scheduling calculation
        self.fore_to_real_dict = None  # Coefficients for correcting the solar forecast with historical data

        self.predicted_demand = None
        self.predicted_demand_current_hour = None
        self.predicted_demand_next_hour = None
        self.target_socs = None
        self.target_soc_current_hour = None
        self.pulp_json_results = None
        self.pulp_parameters = None
        self.current_soc = None
        self.current_security_min_soc = 0  # In %, the minimum security SoC read from inverter
        self.current_min_soc = None  # In %, the true minimum SoC to be used in the calculation
        self.used_last_target_soc = False

        # The true minimum SoC to be used in the calculation is calculated as the maximum between 
        # the security SoC and the user SoC with the safety margin applied

        # Temporary values of last updates
        self.forecast_solar_last_update = None
        self.predicted_demand_last_update = None

        # Temporary values read from the API to expose in the sensors
        self.target_socs_last_update = None

        # Initialize the coordinator
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=COORDINATOR_UPDATE_INTERVAL)
        self.logger.debug("The coordinator has been initialized")        

        # Get the Home Assistant timezone
        str_hass_timezone = self._hass.config.time_zone
        self.str_local_timezone = str_hass_timezone
        self.class_local_timezone = None
        asyncio.create_task(self.set_class_local_timezone(str_hass_timezone))

        # Initialize storage for estimated solar production data
        self.store = Store(hass, version=1, key=STORE_FORECAST_SOLAR_GLOBAL_KEY)

        # Initialize storage for user inputs
        self.store_user_inputs = Store(hass, version=1, key=STORE_USER_INPUT_GLOBAL_KEY)  

        # Initialize aiohttp session
        self._session = aiohttp.ClientSession()

        # Number to do cascading force update the predictions and the target SoC
        self.force_updates_step = 0


        # Inputs from UI (inputs numbers) updates from store in async_initialize
        self.soc_safety_margin = 10 # Default value 

        # Make public for sensors the set point in calcs
        # Since the period is one hour, the energy changes to power directly.
        self.max_setpoint_W=int(entry.data["max_buy_energy_per_period_Wh"])
        self.proposed_setpoint_W = self.max_setpoint_W

        influx_db_pass = None
        if entry.data.get("influx_db_pass", False):
            # For sensitive data, such as the InfluxDB password, it is recommended
            influx_db_pass = entry.data.get("influx_db_pass")       
        
        # Initialize the PVController API
        self.api = PVContollerAPI(
            prophet_influxdb_addon_url=entry.data.get("prophet_influxdb_addon_url", None),
            influx_db_url=entry.data["influx_db_url"], 
            influx_db_user=entry.data["influx_db_user"], 
            influx_db_pass=influx_db_pass, 
            influx_db_database=entry.data["influx_db_database"], 
            acin_to_acout_sensor=entry.data["acin_to_acout_sensor"],
            inverter_to_acout_sensor=entry.data["inverter_to_acout_sensor"],
            solar_production_sensor=entry.data["solar_production_sensor"],
            hystory_forecast_solar_sensor=entry.data["forecast_solar_entity"],
            battery_capacity_Wh=entry.data["battery_capacity_Wh"],
            max_charge_energy_per_period_Wh=entry.data["max_charge_energy_per_period_Wh"],
            max_discharge_energy_per_period_Wh=entry.data["max_discharge_energy_per_period_Wh"],
            max_buy_energy_per_period_Wh=entry.data["max_buy_energy_per_period_Wh"],
            charge_efficiency=entry.data["charge_efficiency"],
            discharge_efficiency=entry.data["discharge_efficiency"],
            battery_purchase_price= entry.data["battery_purchase_price"],
            str_local_timezone=self.str_local_timezone,
            enable_fore_to_real_correction=self.enable_fore_to_real_correction,
            sell_allowed=self.sell_allowed)     

    async def async_close(self):
        """Close the aiohttp session and the API."""
        await self._session.close()
        await self.api.async_close()

    async def set_class_local_timezone(self, str_timezone):
        """Set the local timezone for the class."""
        if str_timezone is None:
            str_timezone = "Europe/Madrid"
        self.class_local_timezone = await asyncio.to_thread(pytz.timezone, str_timezone)

    async def async_initialize(self):
        self.soc_safety_margin = await async_get_value_from_store(
            self.store_user_inputs, "user_soc_safety_margin", 10)
        
        
    async def update_current_min_soc(self):
        """Update the current minimum SoC value."""
        if self.security_min_soc_sensor is not None:
            states=self._hass.states.get(self.security_min_soc_sensor)
            if states is not None:
                self.current_security_min_soc = float(states.state)
        if self.current_security_min_soc is None:
            self.current_security_min_soc = 0
        self.current_min_soc = max(self.current_security_min_soc, self.user_min_soc) \
                            + self.soc_safety_margin
        await self.api.set_current_min_soc(self.current_min_soc)            
        self.logger.debug(f"The current MinSoC is: {self.current_min_soc}%")

    async def _async_update_data(self) -> int:
        """Update data from various sources."""
        # Make the startup lighter by staggering costly processes
        if self._skip_update == 0:
            self._skip_update += 1
            return

        current_datetime = datetime.now()

        # Update the setpoint
        await self.update_proposed_setpoint()

        # Get the current SoC value
        await self.get_current_soc()

        # Get buy prices
        self.buy_prices_rawdata = await self.get_esios_sensor_dict(self.pvpc_buy_entity)      
        self.buy_prices_useful_dict, self.current_buy_price = \
            await pvpc_raw_to_useful_dict(self.buy_prices_rawdata, current_datetime) 
        if self.buy_prices_useful_dict is not None:
            await self.api.set_dict_pvpc_buy_prices(self.buy_prices_useful_dict)
        else:
            self.logger.warning("Buy prices could not be obtained")
        if self.current_buy_price is not None:
            self.logger.debug(f"The buy price is: {self.current_buy_price}")
        else:
            self.logger.warning("The buy price could not be obtained")
        
        # Get sell prices
        self.sell_prices_rawdata = await self.get_esios_sensor_dict(self.pvpc_sell_entity)      
        self.sell_prices_useful_dict, self.current_sell_price = \
            await pvpc_raw_to_useful_dict(self.sell_prices_rawdata, current_datetime)         
        if self.sell_prices_useful_dict is not None:
            await self.api.set_dict_pvpc_sell_prices(self.sell_prices_useful_dict)
        else:
            self.logger.warning("Sell prices could not be obtained")
        if self.current_sell_price is not None:
            self.logger.debug(f"The sell price is: {self.current_sell_price}")
        else:
            self.logger.warning("The sell price could not be obtained")

        # Make the startup lighter by staggering costly processes
        if self._skip_update == 1:
            self._skip_update += 1
            return

        # Get estimated solar production data for the next 12 hours
        self.forecast_solar_rawdata, self.forecast_solar_last_update = await self.fetch_forecast_solar_data()

        # Convert Forecast.Solar data to a continuous dictionary
        await self.make_forecast_solar_useful_dict(current_datetime)
        
        # Update the value in the API
        await self.api.set_dict_forecast_solar(self.forecast_solar_useful_dict)

        # In the first minute of the hour, start cascade update all the API data
        if current_datetime.minute == 0 and self.force_updates_step == 0:
            self.force_updates_step = 1
            self._skip_update += 2
            self.logger.debug(f"Force first minute update: {current_datetime}")
 
        # Request the API to get consumption data from InfluxDB
        if await self.api.update_influxdb(self.force_updates_step == 1):
            self.influx_last_update = self.api.influx_last_update
            if self.force_updates_step == 1:
                self.logger.debug(f"Force first minute update step: {self.force_updates_step}")
                self.force_updates_step = 2

        # Request the API to calculate self._dict_effective_forecast_solar
        if await self.api.make_effective_forecast_solar():
            self.effective_forecast_solar_useful_dict = self.api.dict_effective_forecast_solar
            self.fore_to_real_dict = self.api.fore_to_real_dict

        # # Get the SoC value from the API
        # soc = await self.api.read_soc_from_influxdb()
        # if soc is not None and self.current_soc != soc:
        #     # Update the SoC value
        #     self.current_soc = soc
        #     await self.api.set_current_initial_soc(soc) 
        #     self.logger.debug(f"The current SoC is: {self.current_soc}%")

        # # Get the Security minSoC value from the API
        # minsoc = await self.api.read_minsoc_from_influxdb()
        # if minsoc is not None and self.current_security_min_soc != minsoc:
        #     # Update the current_security_min_soc value
        #     self.current_security_min_soc = minsoc

        # Set the true minimum SoC to be used in the calculation
        await self.update_current_min_soc()
           

        # Make the startup lighter by staggering costly processes
        if self._skip_update == 2:
            self._skip_update += 1
            return

        # Request the API to make predictions
        if await self.api.make_predictions(current_datetime, self.force_updates_step == 2):
            if self.force_updates_step == 2:
                self.logger.debug(f"Force first minute update step: {self.force_updates_step}")
                self.force_updates_step = 3            
            # Update prediction values
            if self.predicted_demand != self.api.dict_demand_prophet_predictions:
                self.logger.debug("Predictions updated")
                self.predicted_demand = self.api.dict_demand_prophet_predictions
                self.predicted_demand_current_hour = self.api.demand_prophet_current_hour_prediction
                self.predicted_demand_next_hour = self.api.demand_prophet_next_hour_prediction    

        # Make the startup lighter by staggering costly processes
        if self._skip_update == 3:
            self._skip_update += 1
            return

        # Request the API to calculate target_socs
        if await self.api.make_target_socs(current_datetime, self.force_updates_step == 3):
            if self.force_updates_step == 3:
                self.logger.debug(f"Force make_target_socs, step: {self.force_updates_step}")
                self.force_updates_step = 4             
            # Update target_socs values
            if self.target_socs != self.api.dict_target_socs:
                self.target_socs = self.api.dict_target_socs
                self.target_soc_current_hour = self.api.target_soc_current_hour
                self.pulp_json_results= self.api.pulp_json_results
                self.pulp_parameters = self.api.pulp_parameters             
                self.used_last_target_soc = False

        if self.force_updates_step == 4 and current_datetime.minute != 0:
            self.force_updates_step = 0
            self.logger.debug(f"End of force first minute update: {current_datetime}")
        # Temporary values read from the API
        self.target_socs_last_update = self.api._target_socs_last_update                 

        
    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._entry.entry_id
    

    def get_entity_attributes(self, entity_id: str):
        """Return the attributes of a sensor with the given entity_id."""
        my_sensor = self._hass.states.get(entity_id)
        if my_sensor and my_sensor.attributes:
            return {**my_sensor.attributes}
        return None

    async def get_pvpc_buy_attributes(self):
        """Access all attributes of the ESIOS PVPC sensor."""
        pvpc_sensor = self._hass.states.get(self.pvpc_buy_entity)
        if pvpc_sensor and pvpc_sensor.attributes:
            # Return only the relevant attributes from the PVPC sensor
            return {key: pvpc_sensor.attributes[key] for key in pvpc_sensor.attributes}
        return None
    
    async def get_current_soc(self):
        """Return the current SoC value from self.battery_soc_sensor=entry.data["battery_soc_sensor"]."""    
        try:
            states= self._hass.states.get(self.battery_soc_sensor)
            self.logger.debug(f"states.state: {states.state}%")
            self.current_soc = float(states.state)
            await self.api.set_current_initial_soc(self.current_soc)
            self.logger.debug(f"Current Soc updated: {self.current_soc}%")
        except Exception as e:
            self.logger.debug(f"Error reading battery_soc_sensor: {e}")

        

    async def get_esios_sensor_dict(self, esios_sensor_name) -> dict | None:
        """
        Return today's and tomorrow's prices from the PVPC sensor with keys
        price_00h to price_23h and price_next_day_00h to price_next_day_23h.
        """
        esios_sensor = self._hass.states.get(esios_sensor_name)
        if esios_sensor and esios_sensor.attributes:
            # Load the desired keys
            desired_keys = await self.pvpc_desired_keys()

            # Filter the keys that are in desired_keys
            filtered_dict = {
                key: value for key, value in esios_sensor.attributes.items()
                if key in desired_keys
            }
            return filtered_dict
        return None

    async def pvpc_desired_keys(self) -> list:
        """Create a list of desired keys for PVPC prices."""
        # Step 1: Create desired_keys with keys from price_00h to price_23h
        desired_keys = [f"price_{str(hour).zfill(2)}h" for hour in range(24)]

        # Step 2: Add keys from price_next_day_00h to price_next_day_23h
        desired_keys.extend([f"price_next_day_{str(hour).zfill(2)}h" for hour in range(24)])
        return desired_keys

    async def get_url_forecast_solar(self):
        """Return the URL of the Forecast.Solar API."""
        lat = self._entry.data.get("latitude", 41.619)
        long = self._entry.data.get("longitude", -0.924)
        declination = self._entry.data.get("declination", 10)
        azimuth = self._entry.data.get("azimuth", 218)
        peak_pow = self._entry.data.get("peak_power", 1.65)

        return f"https://api.forecast.solar/estimate/{lat}/{long}/{declination}/{azimuth}/{peak_pow}"

    async def fetch_forecast_solar_data(self):
        """Fetch solar forecast data from Forecast.Solar API."""
        # Load data at startup
        last_request_time, forecast_data = await self.async_load_data()

        current_time = datetime.now()
        try:
            # Check if the minimum time between requests has passed
            if last_request_time and \
                (current_time - last_request_time <= FORECAST_UPDATE_INTERVAL):
                self.logger.debug("Skipping request to Forecast.Solar to avoid frequent reads")
                return forecast_data, last_request_time  # Avoid the call if the interval is less than the minimum allowed

            assert self._session is not None, "HTTP session is not initialized"
            url = await self.get_url_forecast_solar()

            self.logger.debug(f"Starting request to {url}")
        except Exception as e:
            self.logger.error(f"Error comparing times with Forecast.Solar: {e}")
            self.logger.error(f"Forecast.Solar Store last_request_time: {last_request_time}")
            self.logger.error(f"Forecast.Solar Store forecast_data: {forecast_data}")
            self.logger.error(f"fetch_forecast_solar_data current_time: {current_time}")
            last_request_time = current_time
            await self.async_save_data(current_time, forecast_data)
            return forecast_data, last_request_time

        try:
            # Set a timeout for the request
            async with async_timeout.timeout(10):
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Update the last request time
                        last_request_time = current_time
                        # Log the estimated production data
                        self.logger.debug("Newly downloaded ForeCastSolar data:")
                        forecast_data = data.get("result", {}).get("watt_hours_period", None)
                        # Save the data to persistent storage
                        await self.async_save_data(last_request_time, forecast_data)

                        return forecast_data, last_request_time  # Return the JSON data from the API
                    elif resp.status == 429:
                        self.logger.warning(f"Too many requests to Forecast.Solar, waiting {FORECAST_UPDATE_INTERVAL} h:m:s")
                        last_request_time = current_time
                        await self.async_save_data(current_time, forecast_data)
                        return forecast_data, last_request_time
                    else:
                        self.logger.warning(f"Error in Forecast.Solar API: Status {resp.status}")
                        return None, None

        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error with Forecast.Solar: {e}")
            return None, None
        except asyncio.TimeoutError:
            self.logger.error("Timeout while trying to connect to Forecast.Solar")
            return None, None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None, None

    async def async_load_data(self):
        """Load persistent data from storage."""
        data = await self.store.async_load()
        # Log the loaded data
        # self.logger.debug(f"Data loaded from StoreHA:")
        # self.logger.debug(data)

        # Check if there is data to load
        if data is None:
            return None, None

        # Load `last_request_time` and `forecast_data`
        last_request_time = datetime.fromisoformat(data["last_request_time"]) if data["last_request_time"] else None
        forecast_data = data.get("data", None)

        return last_request_time, forecast_data

    async def async_save_data(self, last_request_time, forecast_data):
        """Save persistent data to storage."""
        data = {
            "last_request_time": last_request_time.isoformat() if last_request_time else None,
            "data": forecast_data
        }

        await self.store.async_save(data)

    async def make_forecast_solar_useful_dict(self, current_datetime):
        """Convert Forecast.Solar data to a continuous dictionary starting at the current hour."""
        try:
            self.forecast_solar_useful_dict, self.forecast_solar_energy_next_hour = \
                await forecast_solar_api_to_dict(self.forecast_solar_rawdata, current_datetime)
            # Here we need to see how to use self.enable_fore_to_real_correction
            # When are the corrections applied? To display them directly in the UI or only in the API

            self.logger.debug(f"The estimated solar production for the next hour is: {self.forecast_solar_energy_next_hour}")
            return True
        except Exception as e:
            self.forecast_solar_useful_dict = None
            self.forecast_solar_energy_next_hour = None
            self.logger.error(f"Error converting Forecast.Solar data: {e}")
            return False
        
    async def update_proposed_setpoint(self):
        """
        Update the setpoint Sensor.
        Tenemos una programación para los target SoC que se ha calculado con los
        siguientes datos de partida
        self.api.demand_prophet_current_hour_prediction
        self.api._last_calc_initial_soc_Wh
        En principio el objetivo será que el
        En la API, mediante la función need_new_target_socs, se determina si es necesario
        actualizar los target SoC por existir una desviación superior a SOC_PERCENT_DEVIATION_FORCE_RECALC
        entre el valor actual del soc y el valor con el que se calculó el target SoC.
        Por tanto las comparaciones para determinar el setpoint_W se deben realizar con el 
        valor que existía en el momento de realizar el cálculo, y no con el valor actual del soc.
        De esta forma, si hay una desviación se recalculará inmediatamente y podremos establecer el
        setpoint_W con conocimiento de causa.
        """
        # Si hay algun problema de calculo al menos no descargaremos la batería indefinidamente
        if self.current_soc is None or self.target_soc_current_hour is None:
            self.proposed_setpoint_W = self.max_setpoint_W
            return
        
        if self.current_soc >= self.target_soc_current_hour:
            self.proposed_setpoint_W=10
        else:
            # Se pretende evitar comprar a la red hasta que se haga un nuevo calculo de target soc
            # Solo usar target soc recien calculados:
              if not self.used_last_target_soc:
                self.proposed_setpoint_W = self.max_setpoint_W
                self.used_last_target_soc = True
                
