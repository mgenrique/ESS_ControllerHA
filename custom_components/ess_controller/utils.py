import logging
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
import pandas as pd
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

def get_entity_description(hass: HomeAssistant, entity_name: str):
    """Get the entity description from Home Assistant."""
    entity_component = hass.data["entity_components"].get("sensor")

    if entity_component:
        # Find the entity in the entity component
        entity = entity_component.get_entity(entity_name)
        
        if entity and hasattr(entity, "entity_description"):
            return entity.entity_description  # Return the entity description
        
    _LOGGER.warning("Could not access 'entity_description' of entity %s", entity_name)
    return None

def get_coordinator_from_entity_name(hass: HomeAssistant, entity_name: str):
    """Get the coordinator from the entity name."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.entities.get(entity_name)
    entity_domain = None
    if entity_entry:
        # Access the config_entry_id of the sensor
        config_entry_id = entity_entry.config_entry_id
        if config_entry_id:
            config_entry = hass.config_entries.async_get_entry(config_entry_id)
            if config_entry:
                entity_domain = config_entry.domain

        if entity_domain:
            # Get the coordinator from hass.data, assuming the domain is "pvpc_hourly_pricing"
            coordinator = hass.data[entity_domain].get(config_entry_id)
            if coordinator:
                _LOGGER.debug("Coordinator found: %s", coordinator)
                return coordinator
            else:
                _LOGGER.warning("Coordinator not found for entity '%s'", entity_name)  
                return None
        else:
            _LOGGER.warning("Domain not found for entity '%s'", entity_name)  
            return None
    else:
        _LOGGER.warning("Entity '%s' not found", entity_name)  
        return None

async def forecast_solar_api_to_dict(forecast_solar_api_data: dict[str, float], current_datetime: datetime) -> dict[str, float]:
    """
    Convert a solar forecast dictionary as downloaded from the Forecast.Solar API
    into a continuous dictionary with data starting from current_datetime.
    The download is a dictionary of the type {'2024-10-28 07:31:26': 0.0, '2024-10-28 08:31:26': 0.0, ...}
    """
    # The solar forecast dictionary has date_times as keys in str format, e.g., '2024-10-28 07:31:26'
    # Forecast.Solar returns date times in the local timezone of the request user
    # There may be gaps in the date_times
    # There may be more than one prediction for the same date_time as they are delta values
    # Sometimes values for the night are not reported

    df = pd.DataFrame(forecast_solar_api_data.items(), columns=['date', 'value'])

    # Group the values by hours calculating the sum of each hour
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.resample('h').sum()  # Sum the values of each hour

    # Find the last date in df
    last_date = df.index[-1]

    # Remove the minutes and seconds from the date to create 1-hour intervals
    current_date = current_datetime.replace(minute=0, second=0, microsecond=0)

    # Calculate the number of periods remaining from current_date to last_date
    periods = (last_date - current_date).days * 24 + (last_date - current_date).seconds // 3600

    continuous_df = pd.DataFrame({'date': pd.date_range(start=current_date, periods=periods, freq='h'), 'value': 0})

    # Set date as the index to be able to dump the values from df into continuous_df
    continuous_df = continuous_df.set_index('date')

    # Dump the values from df into continuous_df where the indices (date) match
    continuous_df.update(df)

    # Store the first value of the series in a variable
    first_value = continuous_df.iloc[0]['value']

    # Modify the index directly to use isoformat date format for the dictionary keys
    continuous_df.index = continuous_df.index.map(lambda x: x.isoformat())

    # Convert the DataFrame to a dictionary and return it
    return continuous_df.to_dict()['value'], first_value 

async def pvpc_raw_to_useful_dict(dict_pvpc: dict[str, float], current_datetime: datetime) -> list[float]:
    """
    Convert a dictionary of electricity prices as obtained from the attributes of
    the ESIOS integration sensor into a continuous dictionary with data starting from current_datetime.
    The sensor has a dictionary of the type {'price_00h': 0.1178, 'price_01h': 0.11417, ...}
    Sometimes it also has keys for the next day, such as 'price_00h_next_day': 0.1178
    """
    df = pd.DataFrame(dict_pvpc.items(), columns=['oldKey', 'value'])

    # Create a new column with the hour
    df['hour'] = df['oldKey'].str.extract(r'(\d+)').astype(int)

    current_date = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    # Create a new column with the date that has current_date + delta hours indicated in the hour column
    df['date'] = current_date + pd.to_timedelta(df['hour'], unit='h')

    # In the columns where oldKey contains 'next_day', add one day to the date
    df.loc[df['oldKey'].str.contains('next_day'), 'date'] = df['date'] + pd.to_timedelta(1, unit='d')

    # Drop the oldKey and hour columns
    df = df.drop(columns=['oldKey', 'hour'])

    # Set the date column as the index of the DataFrame
    df = df.set_index('date')

    # Remove minutes and seconds from current_datetime to compare with the dates in df
    current_datetime = current_datetime.replace(minute=0, second=0, microsecond=0)

    # Remove rows from df that have a date earlier than current_datetime
    df = df[df.index >= current_datetime]
    # If it is empty, end the function
    if df.empty:
        return None, None
    # Store the first value of the series in a variable
    first_value = float(df.iloc[0]['value'])
    
    # Find the length of df
    largo_df = len(df)

    # At the end of the evening, there is very little information about electricity prices
    # We can assume that the price at 23h will be similar to that at 00h and 01h
    if largo_df < 6:
        # Repeat the last value until there are 6 values
        last_value = df['value'].iloc[-1]
        last_date = df.index[-1]      
        for i in range(6 - largo_df):
            last_date = last_date + timedelta(hours=1)
            df.loc[last_date] = last_value

    # Modify the index directly to use isoformat date format for the dictionary keys
    df.index = df.index.map(lambda x: x.isoformat())

    # Convert the DataFrame to a dictionary and return it
    return df.to_dict()['value'], first_value