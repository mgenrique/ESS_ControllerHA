import logging
import pytz
import asyncio
from datetime import datetime, timedelta
import aiohttp
import pandas as pd
import pulp
from .const import INFLUX_UPDATE_INTERVAL, SOC_PERCENT_DEVIATION_FORCE_RECALC, \
    TARGET_SOC_UPDATE_INTERVAL, HISTORY_SOLAR_MAX_DAYS

_LOGGER = logging.getLogger(__name__)

class PVContollerAPI:
    def __init__(self,
                 prophet_influxdb_addon_url: str | None = None,
                 influx_db_url: str | None = None,
                 influx_db_user: str | None = None,
                 influx_db_pass: str | None = None,
                 influx_db_database: str | None = None,
                 acin_to_acout_sensor: str | None = None,
                 inverter_to_acout_sensor: str | None = None,
                 solar_production_sensor: str | None = None,
                 hystory_forecast_solar_sensor: str | None = None,
                 battery_capacity_Wh: int | None = None,
                 max_charge_energy_per_period_Wh: int | None = None,
                 max_discharge_energy_per_period_Wh: int | None = None,
                 max_buy_energy_per_period_Wh: int | None = None,
                 charge_efficiency: float | None = None,
                 discharge_efficiency: float | None = None,
                 battery_purchase_price: float | None = 0,
                 str_local_timezone: str | None = None,
                 enable_fore_to_real_correction: bool | None = False,
                 sell_allowed: bool | None = False
                ) -> None:
        
        """Initialize the API."""
        # Initialize the client for InfluxDB queries
        self._session = aiohttp.ClientSession()

        # Set the local timezone
        # Note: Calls to df.index = df.index.tz_convert(tz) can be made using strings like 'Europe/Madrid'
        # However, it is preferred to use a pytz.timezone object which is more efficient
        # since the df_from_influxdb function makes intensive use of timezone conversion
        # Note: pytz is not compatible with asyncio, so it must be executed in a separate thread
        self.class_local_timezone = None
        asyncio.create_task(self.set_class_local_timezone(str_local_timezone))        

        # Register initialization parameters
        # Prophet Addon
        self._prophet_influxdb_addon_url = prophet_influxdb_addon_url

        # InfluxDB
        #self._influx_db_url='http://192.168.0.100:8086/query'
        # Ensure the InfluxDB URL ends with /query
        if influx_db_url is not None and not influx_db_url.endswith('/query'):
            influx_db_url = f"{influx_db_url.rstrip('/')}/query"

        self._influx_db_url = influx_db_url
        self._influx_db_user = influx_db_user
        self._influx_db_pass = influx_db_pass
        self._influx_db_database = influx_db_database
        self._acin_to_acout_sensor = acin_to_acout_sensor
        self._solar_production_sensor = solar_production_sensor
        self._hystory_forecast_solar_sensor = hystory_forecast_solar_sensor
        self._inverter_to_acout_sensor = inverter_to_acout_sensor

        
        # Photovoltaic installation values
        self._battery_capacity_Wh = battery_capacity_Wh
        self._max_charge_energy_per_period_Wh = max_charge_energy_per_period_Wh
        self._max_discharge_energy_per_period_Wh = max_discharge_energy_per_period_Wh
        self._max_buy_energy_per_period_Wh = max_buy_energy_per_period_Wh
        self._charge_efficiency = charge_efficiency
        self._discharge_efficiency = discharge_efficiency
        self.battery_purchase_price = battery_purchase_price

        # Define internal class values that are calculated        
        self._data_source = "TFG EMG"

        # Electricity prices
        self._dict_pvpc_buy_prices = None
        self._dict_pvpc_sell_prices = None
        self.sell_allowed = sell_allowed

        # Solar production forecasts
        self._dict_forecast_solar = None
        self._dict_forecast_solar_last_update = None
        self.dict_effective_forecast_solar = None
        self._dict_effective_forecast_solar_last_update = None

        # Historical data of total consumption and solar production obtained from InfluxDB
        self.influx_last_update = None
        self.df_history_solar_production = pd.DataFrame() # return an empty DataFrame
        self.history_solar_production_last_day_Wh = None

        # Historical data of solar production forecasts made by Forecast.Solar
        self.df_hystory_forecast_solar = pd.DataFrame() # return an empty DataFrame 
        self.hystory_forecast_solar_last_day_Wh = None
        self.fore_to_real_df = pd.DataFrame() # return an empty DataFrame
        self.fore_to_real_dict = None
        self.enable_fore_to_real_correction = enable_fore_to_real_correction

        self.last_history_solar_production_update = None  

        # Consumption and solar production forecasts from Prophet
        self._prophet_last_update = None
        self.dict_demand_prophet_predictions = None
        self.demand_prophet_current_hour_prediction = None
        self.demand_prophet_next_hour_prediction = None

        # SoC data
        self._current_initial_soc_Wh = None
        self._current_min_soc_Wh = None
        self._test_min_soc_Wh = None

        # Optimization results        
        self._target_socs_last_update = None
        self._last_calc_initial_soc_Wh = None
        self.dict_target_socs = None
        self.target_soc_current_hour = None
        self.pulp_json_results = None # for sensor.ess_controller_pulp_results
        self.pulp_parameters = None # for sensor.ess_controller_pulp_parameters

        # Lists for the SoC calculation algorithm
        self._list_buy_prices = None
        self._list_sell_prices = None
        self._list_solar_production = None
        self._list_demand = None


    async def async_close(self):
        """Close the aiohttp session."""
        await self._session.close()

    async def set_class_local_timezone(self, str_timezone):
        """Set the local timezone for the class."""
        if str_timezone is None:
            str_timezone = "Europe/Madrid"
        self.class_local_timezone = await asyncio.to_thread(pytz.timezone, str_timezone)        
    
    # Create set methods to update dict_pvpc_buy_prices, dict_pvpc_sell_prices, and dict_forecast_solar
    async def set_dict_pvpc_buy_prices(self, dict_pvpc_buy_prices: dict[str, float]) -> None:
        """Set dict_pvpc_buy_prices."""
        if dict_pvpc_buy_prices != self._dict_pvpc_buy_prices:
            self._dict_pvpc_buy_prices = dict_pvpc_buy_prices

    async def set_dict_pvpc_sell_prices(self, dict_pvpc_sell_prices: dict[str, float]) -> None:
        """Set dict_pvpc_sell_prices."""
        if dict_pvpc_sell_prices != self._dict_pvpc_sell_prices:
            self._dict_pvpc_sell_prices = dict_pvpc_sell_prices

    async def set_dict_forecast_solar(self, dict_forecast_solar: dict[str, float]) -> None:
        """Set dict_forecast_solar."""
        if dict_forecast_solar != self._dict_forecast_solar:
            self._dict_forecast_solar = dict_forecast_solar
            self._dict_forecast_solar_last_update = datetime.now()

    # Create set method for self._current_initial_soc_Wh
    async def set_current_initial_soc(self, soc_percent: float) -> None:
        """Set current_initial_soc_Wh."""
        if soc_percent is not None:
            self._current_initial_soc_Wh = soc_percent * self._battery_capacity_Wh / 100
        else:
            self._current_initial_soc_Wh = None

    # Create set method for self._current_min_soc_Wh
    async def set_current_min_soc(self, soc_percent: float) -> None:
        """Set current_min_soc_Wh."""
        if soc_percent is not None:
            self._current_min_soc_Wh = soc_percent * self._battery_capacity_Wh / 100
        else:
            self._current_min_soc_Wh = None

    async def format_date_for_influxdb(self, date) -> str:
        """
        Return a date and time with timezone information in the format '2024-10-01T00:00:00Z' (UTC timezone).
        """
        date = pd.to_datetime(date)
        # Check if date has a localized time
        if date.tzinfo is None:
            if self.class_local_timezone is None:
                date_tz = 'Europe/Madrid'        
                # date = date.tz_localize(date_tz)
                date = await asyncio.to_thread(date.tz_localize, date_tz)
            else:
                # date = date.tz_localize(self.class_local_timezone)
                date = await asyncio.to_thread(date.tz_localize, self.class_local_timezone)
        # Localize the date and time to the UTC timezone
        date = await asyncio.to_thread(date.tz_convert, 'UTC')
        # Format the date in ISO 8601 format
        date = date.strftime('%Y-%m-%dT%H:%M:%SZ')
        return date

    async def energy_query_string(self, entity_id, start: str | None = None, end: str | None = None) -> str:
        """Create the SQL query string for energy data."""
        if start is not None:
            start = await self.format_date_for_influxdb(start)
        if end is not None:
            end = await self.format_date_for_influxdb(end)
        # If start and end are not specified, return all data
        if start is None and end is None:
            query = """SELECT last("value") AS "energy_kWh" FROM "kWh" WHERE "entity_id"='{}' GROUP BY time(1h) fill(previous)""".format(entity_id)
        elif start is None:
            query = """SELECT last("value") AS "energy_kWh" FROM "kWh" WHERE (time <= '{}') AND "entity_id"='{}' GROUP BY time(1h) fill(previous)""".format(end, entity_id) 
        elif end is None:
            query = """SELECT last("value") AS "energy_kWh" FROM "kWh" WHERE (time >= '{}') AND "entity_id"='{}' GROUP BY time(1h) fill(previous)""".format(start, entity_id)   
        else:
            query = """SELECT last("value") AS "energy_kWh" FROM "kWh" WHERE (time >= '{}') AND (time <= '{}') AND "entity_id"='{}' GROUP BY time(1h) fill(previous)""".format(start, end, entity_id)
        return query                         

    async def df_from_influxdb(self, query: str) -> pd.DataFrame:
        """
        Function to read data from InfluxDB using the InfluxDB API with aiohttp.
        """
        try:
            #_LOGGER.debug("Starting df_from_influxdb")
            params = {
                'db': self._influx_db_database,
                'q': query
            }
            auth = (self._influx_db_user, self._influx_db_pass)
            async with self._session.get(self._influx_db_url, params=params, auth=aiohttp.BasicAuth(auth[0], auth[1])) as response:
                if response.status != 200:
                    response.raise_for_status()
                data = await response.json()
            if 'results' not in data or not data['results'] or 'series' not in data['results'][0] or not data['results'][0]['series']:
                raise ValueError("No data returned from InfluxDB")                    
            
            #_LOGGER.debug("Data available. Starting conversion to DataFrame")
            data = data['results'][0]['series'][0]
            columns = data['columns']
            values = data['values']
            
            df = pd.DataFrame(values, columns=columns)
            # Convert the time column to the DataFrame index
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            # InfluxDB returns dates in UTC, convert them to the local timezone and delocalize them
            # Perform the timezone conversion in a separate thread
            df.index = await asyncio.to_thread(df.index.tz_convert, self.class_local_timezone)
            # Delocalize the dates in a separate thread
            df.index = await asyncio.to_thread(df.index.tz_localize, None)
                     
            #_LOGGER.debug(f"Conversion to DataFrame completed, query: {query}")
            return df
        except Exception as e:
            _LOGGER.debug(f"Error fetching data from InfluxDB: {e}. Query={query}")
            return pd.DataFrame() # return an empty DataFrame

    async def hourly_delta_energy_dataframe(self, entity_id, start=None, end=None) -> pd.DataFrame:
        """Create a DataFrame with hourly energy deltas."""
        # Create the SQL query to get the energy data. NaN values are filled with the last known value
        query = await self.energy_query_string(entity_id, start, end)

        # Create a DataFrame with the energy data obtained from InfluxDB
        df = await self.df_from_influxdb(query)

        # If no data was obtained, return an empty DataFrame
        # Even if the connection is successful and the query is correct, if there is no data in the specified range
        # an empty DataFrame is returned
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Handle NaN values that may appear as a result of 
        # a date range wider than the available data
        # first_index = df.iloc[:, 1].first_valid_index() # first index where the value is not NaN
        # first_value = df.iloc[first_index, 1]
        # mask = df.index < first_index # records before the first non-NaN value
        # df.loc[mask, df.columns[1]] = first_value  # Fill NaN values with first_value
        first_index = df['energy_kWh'].first_valid_index() # first index where the value is not NaN
        first_value = df.loc[first_index, 'energy_kWh'] # first value that is not NaN
        mask = df.index < first_index # records before the first non-NaN value
        df.loc[mask, 'energy_kWh'] = first_value # Fill NaN values with first_value

        # Create a new column that calculates the hourly energy difference
        # df['delta_energy'] = df.iloc[:, 1].diff()
        df['delta_energy'] = df['energy_kWh'].diff()

        # Remove the first row of the DataFrame (the hourly difference of the first record does not make sense)
        #df = df.iloc[1:]
        df = df.dropna()

        # If there has been any counter reset, the difference will be negative
        mask = df['delta_energy'] < 0
        df.loc[mask, 'delta_energy'] = 0 # In those cases, set the difference to 0

        return df


    async def hourly_energy_dataframe(self, entity_id, start=None, end=None) -> pd.DataFrame:
        """Create a DataFrame with hourly energy data."""
        # Create the SQL query to get the energy data. NaN values are filled with the last known value
        query = await self.energy_query_string(entity_id, start, end)

        # Create a DataFrame with the energy data obtained from InfluxDB
        df = await self.df_from_influxdb(query)

        # If no data was obtained, return an empty DataFrame
        if df is None or df.empty:
            return pd.DataFrame()  
        
        # Rename the column energy_kWh to delta_energy
        df.rename(columns={'energy_kWh': 'delta_energy'}, inplace=True)

        # Handle NaN values that may appear as a result of 
        # a date range wider than the available data
        df.fillna(0, inplace=True)  # Fill NaN values with 0

        return df
    
    async def energy_total_in_df_by_date(self, df, selected_date) -> float:
        """Return the total energy consumed in a DataFrame for a selected date."""
        if df is None or df.empty:
            return 0.0
        
        # Create the start and end date for the selection
        start = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = selected_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
        # Select the energy data for the selected date
        df = df[start:end]
        
        # If no data was obtained, return 0.0
        if df is None or df.empty:
            return 0.0
        else:
            return df['delta_energy'].sum() 

    
    async def get_history_solar_production_df(self, start=None, end=None) -> pd.DataFrame:
        """Get the historical solar production DataFrame."""
        # Get the name for the query from self._solar_production_sensor
        entity_id = self._solar_production_sensor.split('.')[1]
        df_solar_production = await self.hourly_delta_energy_dataframe(entity_id, start=start, end=end)
        
        if df_solar_production.empty:
            # If no data was obtained, generate a DataFrame with 0 values
            end_datetime = datetime.now() if end is None else pd.to_datetime(end)
            start_datetime = end_datetime - timedelta(days=HISTORY_SOLAR_MAX_DAYS) if start is None else pd.to_datetime(start)
            
            # Create a DataFrame with 0 values                
            df_solar_production = await self.make_hourly_df_between_dates(start_datetime, end_datetime, 0.0)
            df_solar_production.rename(columns={'value': 'delta_energy'}, inplace=True)
            
            return df_solar_production
        
        return pd.DataFrame(df_solar_production, columns=['delta_energy']) 

    async def get_history_forecast_solar_df(self, start=None, end=None) -> pd.DataFrame:
        """Get the historical solar forecast DataFrame."""
        # Get the name for the query from self._hystory_forecast_solar_sensor
        entity_id = self._hystory_forecast_solar_sensor.split('.')[1]
        df_forecast_solar = await self.hourly_energy_dataframe(entity_id, start=start, end=end)
        
        if df_forecast_solar.empty: 
            # If no data was obtained, generate a DataFrame with 0 values
            end_datetime = datetime.now() if end is None else pd.to_datetime(end)
            start_datetime = end_datetime - timedelta(days=HISTORY_SOLAR_MAX_DAYS) if start is None else pd.to_datetime(start)
            
            # Create a DataFrame with 0 values                
            df_forecast_solar = await self.make_hourly_df_between_dates(start_datetime, end_datetime, 0.0)
            df_forecast_solar.rename(columns={'value': 'delta_energy'}, inplace=True)
            
            return df_forecast_solar
        
        return pd.DataFrame(df_forecast_solar, columns=['delta_energy'])    
    
    async def update_influxdb(self, start=None, end=None, force_update: bool = False) -> bool:
        """Update InfluxDB data."""
        # Check if more than INFLUX_UPDATE_INTERVAL has passed since the last update
        if self.influx_last_update is not None \
            and (datetime.now() - self.influx_last_update < INFLUX_UPDATE_INTERVAL) \
            and not force_update:
            _LOGGER.debug("InfluxDB data is still valid") 
            return True
        
        _LOGGER.debug("InfluxDB data needs to be updated") 
        
        current_datetime = datetime.now()
        success=True # This check comes from the original code. It is not clear if it is necessary
        
        # Update historical solar production data only once a day
        if self.last_history_solar_production_update is None \
            or (current_datetime.date() - self.last_history_solar_production_update.date() > timedelta(days=1)): 
            previous_day = current_datetime - timedelta(days=1)
            solar_start = previous_day - timedelta(days=HISTORY_SOLAR_MAX_DAYS)
            
            # Update historical solar production data
            self.df_history_solar_production = await self.get_history_solar_production_df(start=solar_start, end=previous_day)
            
            # Update historical solar forecast data
            self.df_hystory_forecast_solar = await self.get_history_forecast_solar_df(start=solar_start, end=previous_day)
            
            # Get the solar production of the last day
            self.history_solar_production_last_day_Wh = await self.energy_total_in_df_by_date(self.df_history_solar_production, previous_day)
            self.history_solar_production_last_day_Wh *= 1000  # Convert from kWh to Wh
            
            # Get the solar forecast of the last day
            self.hystory_forecast_solar_last_day_Wh = await self.energy_total_in_df_by_date(self.df_hystory_forecast_solar, previous_day)
            self.hystory_forecast_solar_last_day_Wh *= 1000  # Convert from kWh to Wh
            
            await self.compare_solar_production_forecast()
            self.last_history_solar_production_update = current_datetime

            success = len(self.df_history_solar_production) > 0 and len(self.df_hystory_forecast_solar) > 0

        if success:
            self.influx_last_update = datetime.now()
            _LOGGER.debug("Solar production data updated at {} from InfluxDB".format(self.influx_last_update))
            _LOGGER.debug(f"history_solar_production_last_day Wh: {self.history_solar_production_last_day_Wh}")
            _LOGGER.debug(f"hystory_forecast_solar_last_day Wh: {self.hystory_forecast_solar_last_day_Wh}")

            return True            
        else:
            _LOGGER.debug("Failed to obtain data from InfluxDB")
            return False            

    # async def read_soc_from_influxdb(self) -> float:
    #     """Read the state of charge (SoC) from InfluxDB."""
    #     # Get the name for the query from self._battery_soc_sensor
    #     entity_id = self._battery_soc_sensor.split('.')[1]
        
    #     # Create the SQL query to get the last soc value
    #     query = """SELECT last("value") AS "soc" FROM "homeassistant"."autogen"."%" WHERE "entity_id"='{}'""".format(entity_id)

    #     # Create a DataFrame with the energy data obtained from InfluxDB
    #     df = await self.df_from_influxdb(query)
        
    #     # If the DataFrame is empty, return None
    #     if df.empty:
    #         return None
    #     else:
    #         # Return the soc value
    #         return df['soc'].iloc[0]
        
    # async def read_minsoc_from_influxdb(self) -> float:
    #     """Read the minimum state of charge (minSoC) from InfluxDB."""
    #     # Get the name for the query from self._battery_min_soc_overrides_sensor
    #     entity_id = self._battery_min_soc_overrides_sensor.split('.')[1]
        
    #     # Create the SQL query to get the last minSoC value
    #     query = """SELECT last("value") AS "minsoc" FROM "homeassistant"."autogen"."%" WHERE "entity_id"='{}'""".format(entity_id)

    #     # Create a DataFrame with the energy data obtained from InfluxDB
    #     df = await self.df_from_influxdb(query)
        
    #     # If the DataFrame is empty, return None
    #     if df.empty:
    #         return 0
    #     else:
    #         # Return the minSoC value
    #         return df['minsoc'].iloc[0]

    async def post_energy_query(self, base_url, energy_query_data):
        try:
            async with self._session.post(f"{base_url}/energy_queries", json=energy_query_data) as response:
                if response.status != 200:
                    response.raise_for_status()
                data = await response.json()
            # Check if data is empty
            if not data:
                raise ValueError("No data returned from Addon API")
            return data              

        except Exception as e:
            _LOGGER.error(f"Error posting energy query: {e}")
            return None
        
        async with self._session as session:
            async with session.post(f"{base_url}/energy_queries", json=energy_query_data) as response:
                return await response.json()
        
    async def make_predictions(self, current_datetime: datetime, force_update: bool = False) -> bool:
        """Make energy consumption predictions using Prophet."""
        # If the InfluxDB update date is more recent than the Prophet update date, recalculate predictions
        if self._prophet_last_update is not None \
            and self.influx_last_update is not None \
            and self._prophet_last_update > self.influx_last_update \
            and not force_update:
            _LOGGER.debug("Prophet data is still valid") 
            return True
        

        _LOGGER.debug("Prophet data needs to be updated")
        # Show the start time of the prediction process
        _LOGGER.debug(f"Prophet predictions started at {datetime.now()}")     

        try:

            # Create current_date from current_datetime without minutes and seconds
            current_date = current_datetime.replace(minute=0, second=0, microsecond=0)

            # Get the name for the query from self._acin_to_acout_sensor
            entity_id = self._acin_to_acout_sensor.split('.')[1]
            str_query1 = await self.energy_query_string(entity_id, start=None, end=current_date)
            
            # Get the name for the query from self._inverter_to_acout_sensor
            entity_id = self._inverter_to_acout_sensor.split('.')[1]
            str_query2 = await self.energy_query_string(entity_id, start=None, end=current_date) 

            energy_query_data = {
                "str_query1": str_query1,
                "str_query2": str_query2,
                "futurePeriods": 30,
                "futureFreq": "h"
            }
            # base_url = "http://192.168.0.100:5000" # Raspeberry Pi (HA OS) runs the container with the API
            # base_url = "http://localhost:5000" # Raspeberry Pi (HA OS) runs the container with the API
            base_url = self._prophet_influxdb_addon_url
            _LOGGER.info(f"base url for addon: {base_url}")            

            response = await self.post_energy_query(base_url, energy_query_data)
            if response is None:
                raise ValueError("No data returned from Addon API") 
                
            _LOGGER.debug("Energy Queries response:", response)
            cc_response = {str(k): v for k, v in response.items()}
            # Convert the dates to the local timezone
            # Convert predictions to integers and Wh
            cc_response = {pd.to_datetime(k).tz_convert(self.class_local_timezone)\
                            .strftime('%Y-%m-%dT%H:%M:%S'): int(v * 1000) \
                            for k, v in cc_response.items()}
            _LOGGER.debug(f"\nEnergy Queries response local timezone: {cc_response}")

            # Store values locally
            self.dict_demand_prophet_predictions = cc_response        

            # Store the prediction for this hour and the next hour
            # Note: the current hour is index 0. The next hour is index 1
            self.demand_prophet_current_hour_prediction = cc_response[list(cc_response.keys())[0]]
            self.demand_prophet_next_hour_prediction = cc_response[list(cc_response.keys())[1]]          

            # Update the last Prophet update date
            self._prophet_last_update = datetime.now()

            # Show the end time of the prediction process
            _LOGGER.debug(f"Prophet demand predictions finished at {datetime.now()}")

            return True
        except Exception as e:
            _LOGGER.error(f"Error making demand predictions with Prophet: {e}")
            return False


    def need_new_target_socs(self):
        """Check if new target SoCs need to be calculated."""
        # Check if there is a significant deviation in the target SoCs values
        if self._last_calc_initial_soc_Wh is not None and self._current_initial_soc_Wh is not None:
            soc_deviation = 100 * abs(self._last_calc_initial_soc_Wh - self._current_initial_soc_Wh) / self._battery_capacity_Wh
            if soc_deviation > SOC_PERCENT_DEVIATION_FORCE_RECALC:
                _LOGGER.info("Target SoCs need to be recalculated due to SoC deviation of previous calcs: {:.2f}%".format(soc_deviation)) 
                return True

        # Check if more than TARGET_SOC_UPDATE_INTERVAL hours have passed since the last target SoCs update
        if self._target_socs_last_update is None:
            _LOGGER.debug("Target SoCs need to be updated")
            return True
        else:
            if datetime.now() - self._target_socs_last_update >= TARGET_SOC_UPDATE_INTERVAL:
                _LOGGER.debug("Target SoCs need to be updated")
                return True
            else:
                _LOGGER.debug("Target SoCs are still valid") 
                return False

    def check_data_ready(self):
        """Check if all necessary data is available."""
        # Check if electricity price data is available
        if self._dict_pvpc_buy_prices is None or self._dict_pvpc_sell_prices is None:
            _LOGGER.debug("No electricity price data available")
            return False

        # Check if solar forecast data is available
        if self._dict_forecast_solar is None:
            _LOGGER.debug("No solar forecast data available")
            return False
        
        # Check if corrected solar forecast data is available
        if self.dict_effective_forecast_solar is None:
            _LOGGER.debug("No effective solar forecast data available")
            return False       
        
        # Check if we have a value for the current SoC
        if self._current_initial_soc_Wh is None:
            _LOGGER.debug("No SoC data available")
            return False

        # Check if photovoltaic installation data is available
        if self._battery_capacity_Wh is None or self._max_charge_energy_per_period_Wh is None \
            or self._max_discharge_energy_per_period_Wh is None or self._max_buy_energy_per_period_Wh is None \
            or self._charge_efficiency is None or self._discharge_efficiency is None \
            or self._current_min_soc_Wh is None or self._current_initial_soc_Wh is None:
            _LOGGER.debug("Some photovoltaic installation data is missing")
            return False

        return True

    async def prepare_lists_for_soc_calc(self, current_datetime: datetime) -> bool:
        """Prepare lists for SoC calculation."""
        # Set the calculation moment
        # current_datetime = datetime.now()

        # Create lists of electricity prices and solar forecast
        if self._dict_pvpc_buy_prices is not None:
            buy_prices = await self.pvpc_dict_to_list(self._dict_pvpc_buy_prices, current_datetime)
        else:
            _LOGGER.debug("No electricity buy price data available")
            return False
        
        if self._dict_pvpc_sell_prices is not None:
            sell_prices = await self.pvpc_dict_to_list(self._dict_pvpc_sell_prices, current_datetime)
            if self.sell_allowed is False:
                sell_prices = [0.0] * len(sell_prices)
        else:
            _LOGGER.debug("No electricity sell price data available")
            return False
        
        if self.dict_effective_forecast_solar is not None:
            forecast_solar = await self.forecast_solar_dict_to_list(self.dict_effective_forecast_solar, current_datetime)
        else:
            _LOGGER.debug("No solar forecast data available")
            return False               
        
        if self.dict_demand_prophet_predictions is None:
            _LOGGER.debug("No electricity consumption data available")
            return False

        # Create the list with Prophet consumption forecasts
        current_date = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        demand_dict = self.dict_demand_prophet_predictions
        demand_dict = {k: v for k, v in demand_dict.items() if datetime.fromisoformat(k) >= current_date}
        demand = list(demand_dict.values())

        max_i_buy = len(buy_prices)
        max_i_sell = len(sell_prices)
        max_i_solar = len(forecast_solar)
        max_i_demand = len(demand)
        # Log the lengths of the lists
        _LOGGER.debug(f"Length of buy prices list: {max_i_buy}")
        _LOGGER.debug(f"Length of sell prices list: {max_i_sell}")
        _LOGGER.debug(f"Length of solar production list: {max_i_solar}")
        _LOGGER.debug(f"Length of demand list: {max_i_demand}")

        # Log the lists
        _LOGGER.debug(f"Buy prices list: {buy_prices}")
        _LOGGER.debug(f"Sell prices list: {sell_prices}")
        _LOGGER.debug(f"Solar production list: {forecast_solar}")
        _LOGGER.debug(f"Demand list: {demand}")

        max_index = min(max_i_buy, max_i_sell, max_i_solar, max_i_demand)
        if max_index <= 1:
            _LOGGER.debug("Not enough data for SoC calculation")
            return False

        _LOGGER.info(f"Optimization will be performed for {max_index} periods")   

        self._list_buy_prices = buy_prices[0:max_index]
        self._list_sell_prices = sell_prices[0:max_index]
        self._list_solar_production = forecast_solar[0:max_index]
        self._list_demand = demand[0:max_index]
        return True        

                                                
    async def pvpc_dict_to_list(self, dict_pvpc: dict[str, float], current_datetime: datetime) -> list[float]:
        """Convert an electricity price dictionary into a list of floats."""
        # The electricity price dictionary must be formatted by the coordinator to make it continuous
        # using the utils.pvpc_raw_to_useful_dict function
        # it has date_hours as keys in str format, e.g., '2024-10-28 07:00:00'        

        # If the dictionary is empty, return an empty list
        if not dict_pvpc:
            return []

        # Get a datetime with the current date removing minutes and seconds
        current_date = current_datetime.replace(minute=0, second=0, microsecond=0) 

        df = pd.DataFrame(dict_pvpc.items(), columns=['date', 'value'])

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # Remove values earlier than current_date
        df = df[df.index >= current_date]
        # If df is empty, return an empty list
        if df.empty:
            return []
        
        return df['value'].tolist()  
     

    async def forecast_solar_dict_to_list(self, dict_forecast_solar: dict[str, float], current_datetime: datetime) -> list[float]:
        """Convert a solar forecast dictionary into a list of floats."""
        # The solar forecast dictionary must be formatted by the coordinator to make it continuous
        # using the utils.get_forecast_solar_dict function
        # it has date_hours as keys in str format, e.g., '2024-10-28 07:00:00'

        # If the dictionary is empty, return an empty list
        if not dict_forecast_solar:
            return []
        
        # Get a datetime with the current date removing minutes and seconds
        current_date = current_datetime.replace(minute=0, second=0, microsecond=0) 

        df = pd.DataFrame(dict_forecast_solar.items(), columns=['date', 'value'])

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # Remove values earlier than current_date
        df = df[df.index >= current_date]
        # If df is empty, return an empty list
        if df.empty:
            return []
        
        return df['value'].tolist()

    
    async def make_target_socs(self, current_datetime: datetime, force_update: bool = False) -> bool:
        """
        Calculate the target SoCs for as many periods as we have available information.
        """
        # Check if the necessary data is available
        if not self.check_data_ready():
            return False

        # Check if it is necessary to recalculate the target SoCs
        if not self.need_new_target_socs() and not force_update:
            return True

        _LOGGER.debug("Calculating target SoCs")

        # Prepare the lists for SoC calculation
        if not await self.prepare_lists_for_soc_calc(current_datetime):
            _LOGGER.debug("Failed to load lists")
            return False

        # Calculate the target SoCs
        _LOGGER.debug(f"Starting PuLP: {datetime.now()}")
        # Log the buy prices
        for i in range(len(self._list_buy_prices)-1):
            _LOGGER.debug(f"Price {i}:{self._list_buy_prices[i]} €/kWh")
            if self._list_buy_prices[i] < self._list_buy_prices[i+1]:
                _LOGGER.debug(f"Price {i} is lower than {i+1}: {self._list_buy_prices[i]} < {self._list_buy_prices[i+1]}")
            else:
                _LOGGER.debug(f"Price {i} is greater than {i+1}: {self._list_buy_prices[i]} > {self._list_buy_prices[i+1]}")        

        # We can iterate and test diferents min_soc values
        self._test_min_soc_Wh = self._current_min_soc_Wh
        result,objetive = await self.pulp_calculations(current_datetime)

        soc = result['SoC(%)']
        soc_len = len(soc)
        current_date = current_datetime.replace(minute=0, second=0, microsecond=0)
        date_list = [(current_date + timedelta(hours=x)).isoformat() for x in range(soc_len)]
        self.dict_target_socs = dict(zip(date_list, soc))

        self.target_soc_current_hour = result['SoC(%)'][0]
        _LOGGER.debug(f"Finishing PuLP: {datetime.now()} with result: {result} and objetive: {objetive}")

        # When the target SoCs calculation starts, the value of current_initial_soc_Wh provided
        # by the coordinator is used to perform the calculation and is stored in _last_calc_initial_soc_Wh
        # to compare if it is necessary to recalculate the target SoCs when the difference between them is large
        # This check is performed in need_new_target_socs
 
        self._last_calc_initial_soc_Wh = self._current_initial_soc_Wh
        self._target_socs_last_update = datetime.now()
        return True
    

    async def pulp_calculations(self,current_datetime: datetime) -> dict:
        """
        Solve the optimization problem with PuLP.
        """
        # Lists of demand, solar production, buy and sell prices
        demand = self._list_demand  # Demand in Wh per hour
        solar_production = self._list_solar_production  # Solar production in Wh per hour
        buy_prices = self._list_buy_prices  # Buy prices in €/kWh
        sell_prices = self._list_sell_prices  # Sell prices in €/kWh

        # Read the current SoC
        initial_soc = self._current_initial_soc_Wh  # Initial state of charge of the battery (Wh)

        # Use a test min_soc value for the optimization
        min_soc = self._test_min_soc_Wh # self._current_min_soc_Wh  # Minimum allowed SoC (Wh)

        # Photovoltaic installation parameters
        battery_capacity = self._battery_capacity_Wh  # Maximum battery capacity (Wh)
        max_charge_energy_per_period = self._max_charge_energy_per_period_Wh  # (Wh), due to the maximum charging power max_charge_power(W)
        max_discharge_energy_per_period = self._max_discharge_energy_per_period_Wh  # (Wh), due to the maximum discharging power max_discharge_power(W)
        max_buy_energy_per_period = self._max_buy_energy_per_period_Wh  # (Wh), due to the maximum contracted power with the grid max_grid_power(W)
        charge_efficiency = self._charge_efficiency  # Battery charging efficiency (AC-DC conversion efficiency)
        discharge_efficiency = self._discharge_efficiency  # Battery discharging efficiency (DC-AC conversion efficiency)

        # Take into account the time remaining until the end of the current hour
        max_charge_energy_first_period = max_charge_energy_per_period - (current_datetime.minute * max_charge_energy_per_period / 60)
        max_discharge_energy_first_period = max_discharge_energy_per_period - (current_datetime.minute * max_discharge_energy_per_period / 60)
        max_buy_energy_first_period = max_buy_energy_per_period - (current_datetime.minute * max_buy_energy_per_period / 60)
        demand[0] = demand[0] - (current_datetime.minute * demand[0] / 60)
        solar_production[0] = solar_production[0] - (current_datetime.minute * solar_production[0] / 60)

        # Battery cost parameters
        battery_purchase_price = self.battery_purchase_price  # 1000€ ?
        battery_eol_cycles_if_min_soc_20 = 2500  # cycles
        battery_eol_cycles_if_min_soc_50 = 5000  # cycles
        min_soc_percent= min_soc / battery_capacity *100 # %
        # Linear interpolation between 20% and 50% to estimate the battery lifetime at min_soc_percent
        battery_eol_cycles_current_min_soc = battery_eol_cycles_if_min_soc_20 + \
            (battery_eol_cycles_if_min_soc_50 - battery_eol_cycles_if_min_soc_20) * (min_soc_percent - 20) / 30  # cycles

        # Battery energy cost. Only considered when discharging the battery
        # In its lifetime, the battery can provide:
        all_live_energy= (battery_eol_cycles_current_min_soc*battery_capacity*(100-min_soc_percent)/100)/1000 # kWh of energy
        # Therefore, the cost of the energy from battery is battery_purchase_price / all_live_energy €/kWh
        battery_energy_price = battery_purchase_price / all_live_energy  # €/kWh

        # Number of hours to consider       
        num_hours = min(len(demand), len(solar_production), len(buy_prices), len(sell_prices))

        # Sum of demand and solar production
        total_demand = sum(demand)
        total_solar_production = sum(solar_production)
        # Coste bruto de la demanda
        gross_demand_cost = sum([demand[i]*buy_prices[i] for i in range(num_hours)]) / 1000
        # Average electricity price
        average_price = sum(buy_prices) / num_hours

        # Max electricity price
        max_price = max(buy_prices)
        # Min electricity price
        min_price = min(buy_prices)
        # get hour at min price
        min_price_hour = buy_prices.index(min_price)       

        # Set the weight we will give in the objective function to maximize the final SoC versus minimizing the cost of purchased energy
        # When solar production is greater than demand, maximizing the SoC will be prioritized
        if total_solar_production >= total_demand:
            w = 2 * average_price / 1000
            # w = 2 * max_price / 1000
            _LOGGER.debug(f"Solar production covers all demand! w={w}")
        else:
            w = average_price / 1000
            # w = max_price / 1000
            _LOGGER.debug(f"Solar production does not cover all demand! w={w}")

        # NOTE: THE PROBLEM IS SOLVED CORRECTLY EVEN IF initial_soc < min_soc

        # Create the optimization problem
        problem = pulp.LpProblem("Optimal_SOC_with_Cost_Minimization", pulp.LpMinimize)

        # Decision variables: energies and SoC of the battery at each hour
        energy_from_grid = [pulp.LpVariable(f'f_grid_{i}', lowBound=0, upBound=max_buy_energy_per_period) for i in range(num_hours)]
        energy_to_grid = [pulp.LpVariable(f't_grid_{i}', lowBound=0) for i in range(num_hours)]
        soc = [pulp.LpVariable(f'soc_{i}', lowBound=0, upBound=battery_capacity) for i in range(num_hours)]
        energy_to_battery = [pulp.LpVariable(f'charge_{i}', lowBound=0, upBound=max_charge_energy_per_period) for i in range(num_hours)]
        energy_from_battery = [pulp.LpVariable(f'discharge_{i}', lowBound=0, upBound=max_discharge_energy_per_period) for i in range(num_hours)]

        # Objective function: minimize the cost of energy and maximize the SoC
        energy_cost = pulp.lpSum([(energy_from_grid[i] * buy_prices[i] + \
                                energy_from_battery[i] * battery_energy_price - \
                                energy_to_grid[i] * sell_prices[i] - \
                                energy_to_battery[i] * battery_energy_price \
                                )*(1/1000) \
                                for i in range(num_hours)])  # Convert prices to €/Wh        
        final_soc = soc[-1]  # The state of charge in the last period
        problem += energy_cost - w * final_soc

        # CONSTRAINTS
        # Require that the SoC at the last period is greater than the initial SoC.
        # The final SoC could have been set as an input parameter. Consider this in future versions
        problem += soc[-1] >= initial_soc
        for i in range(num_hours):
            if i == 0:
                # In the first hour, start from initial_soc and balance
                problem += soc[i] == initial_soc + energy_to_battery[i] - energy_from_battery[i]
                # Limit the energy that can enter the battery due to the maximum charging power in first period
                problem += energy_to_battery[i] <= max_charge_energy_first_period
                problem += energy_from_battery[i] <= max_discharge_energy_first_period
                problem += energy_from_grid[i] <= max_buy_energy_first_period
                # How much energy can be sent to the battery in the first period if the initial SoC is less than min_soc?
                max_energy_available = max(max_buy_energy_first_period + solar_production[0] - demand[0],0)
                max_energy_to_battery = min(max_charge_energy_first_period, max_energy_available*charge_efficiency)
                # Try to recover the SoC as quickly as possible if it is below min_soc
                if initial_soc < min_soc:
                    problem += soc[i] >= initial_soc + max_energy_to_battery
                else:
                    # Require that the SoC does not fall below the minimum allowed
                    problem += soc[i] >= min_soc      
            else:
                # In the following hours, the SoC depends on the previous state
                problem += soc[i] == soc[i - 1] + energy_to_battery[i] - energy_from_battery[i]
                # Require that the SoC does not fall below the minimum allowed
                problem += soc[i] >= min_soc        

            # Global energy balance
            problem += demand[i] + pulp.lpSum(energy_to_battery[i])/charge_efficiency + energy_to_grid[i] == \
                energy_from_grid[i] + solar_production[i] + pulp.lpSum(energy_from_battery[i]) * discharge_efficiency                  
        try:
            # Run problem.solve() in a separate thread
            await asyncio.to_thread(problem.solve)
        except pulp.PulpSolverError as e:
            _LOGGER.error(f"Error running the PuLP solver: {e}")
            # raise UpdateFailed(f"Error running the PuLP solver: {e}")
            return None, None

        # Check the solution status
        status = pulp.LpStatus[problem.status]
        _LOGGER.info(f"PuLP solution status: {status}")

        if status != 'Optimal':
            return None, None

        _LOGGER.info(f"Objective function: {pulp.value(problem.objective):.2f} €")

        # Results
        total_grid_cost = 0
        for i in range(num_hours):
            total_grid_cost += energy_from_grid[i].varValue * buy_prices[i] \
                                - energy_to_grid[i].varValue * sell_prices[i]
        total_grid_cost = total_grid_cost / 1000  # Convert to € (price is in €/kWh and energy in Wh)
        total_battery_cost = 0
        for i in range(num_hours):
            total_battery_cost += energy_from_battery[i].varValue * battery_energy_price \
                                - energy_to_battery[i].varValue * battery_energy_price
        total_battery_cost = total_battery_cost / 1000  # Convert to € (price is in €/kWh and energy in Wh)

        # Create a dictionary with the results
        current_date = current_datetime.replace(minute=0, second=0, microsecond=0)
        results = {
            "Hour": [i for i in range(1, num_hours + 1)],
            "System Time": [(current_date + timedelta(hours=i)).strftime("%H:%M") for i in range(num_hours)],
            "buy_price(€/kWh)": buy_prices,
            "sell_price(€/kWh)": sell_prices,
            "Demand(Wh)": [round(demand[i]) for i in range(num_hours)], 
            "from_solar(Wh)": [round(solar_production[i]) for i in range(num_hours)],
            "from_grid(Wh)": [round(energy_from_grid[i].varValue) for i in range(num_hours)],
            "to_grid(Wh)": [round(energy_to_grid[i].varValue) for i in range(num_hours)],
            "to_battery(Wh)": [round(energy_to_battery[i].varValue) for i in range(num_hours)],
            "from_battery(Wh)": [round(energy_from_battery[i].varValue) for i in range(num_hours)],
            "SoC(Wh)": [round(soc[i].varValue) for i in range(num_hours)],
            "SoC(%)": [round(soc[i].varValue / battery_capacity * 100) for i in range(num_hours)]
        }
        results['System Time'][0] = current_datetime.strftime("%H:%M")
        self.pulp_json_results = results

        # Log the results
        _LOGGER.info(f"Results: {results}")

        # Make a dictionary with other optimization data for the frontend
        self.pulp_parameters = {"Status": pulp.LpStatus[problem.status],
                                "Objective function": pulp.value(problem.objective),
                                "w": w,
                                "gross_demand_cost": gross_demand_cost,
                                "total_grid_cost": total_grid_cost,
                                "total_battery_cost": total_battery_cost,
                                "total_cost": total_grid_cost + total_battery_cost,
                                "total_demand": total_demand,
                                "total_solar_production": total_solar_production,
                                "average_price": average_price,
                                "max_price": max_price,
                                "min_price": min_price,
                                "min_price_hour": min_price_hour+1,
                                "battery_energy_price €/kWh": battery_energy_price, # €/kWh
                                "initial_soc": initial_soc, 
                                "min_soc": min_soc, 
                                "demand": self._list_demand, 
                                "solar_production": self._list_solar_production, 
                                "buy_prices": buy_prices, 
                                "sell_prices": sell_prices
                                }


        return results, pulp.value(problem.objective)
        
    async def make_hourly_df_between_dates(self, start, end, value) -> pd.DataFrame:
        """
        Create a DataFrame with hourly values between two dates.
        """
        # Convert start and end to datetime objects
        start = pd.to_datetime(start).replace(minute=0, second=0, microsecond=0)
        end = pd.to_datetime(end).replace(minute=0, second=0, microsecond=0)

        # Create a date range with hourly frequency between start and end
        date_range = pd.date_range(start=start, end=end, freq='H')
        # Create a DataFrame with the values and the date range
        df = pd.DataFrame(data=value, index=date_range, columns=['value'])
        df.index.name = 'time'
        return df

    async def compare_solar_production_forecast(self) -> bool:
        """
        Compare historical solar production with solar forecast.
        """
        # Check if the necessary data is available
        if self.df_history_solar_production is None or self.df_hystory_forecast_solar is None:
            return False

        # Create a DataFrame with solar production grouped by hours with the mean of the data
        production_df = self.df_history_solar_production.copy()
        forecast_df = self.df_hystory_forecast_solar.copy()
        # Create a new field 'hour' extracting the hour from the DataFrame index
        production_df['hour'] = production_df.index.hour
        forecast_df['hour'] = forecast_df.index.hour

        # Calculate the mean for each hour of the day
        production_df = production_df.groupby('hour')['delta_energy'].mean().reset_index()
        forecast_df = forecast_df.groupby('hour')['delta_energy'].mean().reset_index()

        # Set 'hour' as the index
        production_df.set_index('hour', inplace=True)
        forecast_df.set_index('hour', inplace=True)

        # Create a DataFrame with solar production and solar forecast
        df = pd.concat([production_df, forecast_df], axis=1)
        df.columns = ['real_energy', 'forecast_energy']
        df.dropna(inplace=True)

        # Add the column 'fore_to_real' to df initialized to 1.0
        df['fore_to_real'] = 1.0

        # Create a mask for the values of forecast_energy that are != 0
        mask = df['forecast_energy'] != 0
        # Calculate the ratio between forecast_energy and real_energy
        df.loc[mask, 'fore_to_real'] = df['real_energy'] / df['forecast_energy']

        # Limit abnormally high values
        mask = df['fore_to_real'] > 2.0  
        df.loc[mask, 'fore_to_real'] = 2.0
        self.fore_to_real_df = df
        # Convert the columns real_energy and forecast_energy to Wh
        df['real_energy'] = round(df['real_energy'] * 1000, 0)
        # Rename the column to real_energy_Wh
        df.rename(columns={'real_energy': 'real_energy_Wh'}, inplace=True)
        df['forecast_energy'] = round(df['forecast_energy'] * 1000, 0)
        # Rename the column to forecast_energy_Wh
        df.rename(columns={'forecast_energy': 'forecast_energy_Wh'}, inplace=True)
        self.fore_to_real_dict = df.to_dict(orient='index')
        # Log the DataFrame
        _LOGGER.debug(f"Comparison of solar production and solar forecast for the last {HISTORY_SOLAR_MAX_DAYS} days: {df}")
        return True
    
    async def make_effective_forecast_solar(self):
        """
        Calculate the corrected solar forecast with the ratio between solar production and solar forecast.
        """
        # Check if it is necessary to update the corrected solar forecast
        if self._dict_effective_forecast_solar_last_update is not None \
            and self.last_history_solar_production_update is not None \
            and self._dict_forecast_solar_last_update is not None:
            most_recent_update = max(self.last_history_solar_production_update, self._dict_forecast_solar_last_update)
            if most_recent_update < self._dict_effective_forecast_solar_last_update:
                _LOGGER.debug("The corrected solar forecast is still valid")
                return True

        if (self._dict_forecast_solar is not None) and (not self.enable_fore_to_real_correction):
            self.dict_effective_forecast_solar = self._dict_forecast_solar
            self._dict_effective_forecast_solar_last_update = datetime.now()
            return True

        # Check if the necessary data is available
        if self._dict_forecast_solar is None or self.fore_to_real_df is None:
            return False
        try:
            # Create a dictionary with the corrected solar forecast
            dict_effective_forecast_solar = self._dict_forecast_solar.copy()
            for key, value in dict_effective_forecast_solar.items():
                # Get the hour of the day
                hour = pd.to_datetime(key).hour
                # Get the fore_to_real value for the corresponding hour
                fore_to_real = self.fore_to_real_df.loc[hour, 'fore_to_real']
                # Correct the solar forecast value
                dict_effective_forecast_solar[key] = value * fore_to_real

            self._dict_effective_forecast_solar_last_update = datetime.now()
            self.dict_effective_forecast_solar = dict_effective_forecast_solar
            # Log the dictionary
            _LOGGER.debug(f"Corrected solar forecast: {dict_effective_forecast_solar}")
            return True
        except Exception as e:
            _LOGGER.error(f"Error calculating the corrected solar forecast: {e}")
            return False        
        
        
