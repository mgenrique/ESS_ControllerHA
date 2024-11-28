# Prophet InfluxDB Addon

This addon allows running a forecasting script using Prophet and data from InfluxDB.
This addon has been created as a solution to the installation limitations of the custom component [ESS Controller](https://github.com/mgenrique/ESS_ControllerHA) in Home Assistant OS.

The Home Assistant Core container in Home Assistant OS is based on a minimal operating system image based on the Alpine Linux distribution. It is a distribution known for being lightweight, secure, and fast. It is specifically designed for containerized environments, such as Docker, as it is small in size and consumes few resources. However, this is where the limitation comes in that we cannot run Prophet directly in the container that runs Home Assistant core.
Prophet requires specific libraries and dependencies such as pystan and gcc to compile C++ code. Alpine Linux uses musl libc instead of glibc, which is the cause of incompatibilities in many Python libraries, including Prophet, which depend on glibc to properly run the compiler and underlying libraries. Including Prophet in this container would significantly increase its size and complexity, as well as potentially cause compatibility issues in future Home Assistant OS updates.
Therefore this plugin has been created to allow the use of Prophet within the Home Assistant environment.

## Configuration

You can configure the following options from the Home Assistant UI:

- `INFLUXDB_HOST`: InfluxDB host, InfluxAddon host_name or external IP, examples: a0d7b954-influxdb or 192.168.0.100
- `INFLUXDB_PORT`: InfluxDB port
- `INFLUXDB_USER`: InfluxDB user
- `INFLUXDB_PASSWORD`: InfluxDB password
- `INFLUXDB_DBNAME`: InfluxDB database name

## Description
This addon use the Docker image in:
https://hub.docker.com/repository/docker/mgenrique/prophet-influx/general

A Docker image based on python:3.11-slim that contains precompiled libraries necessary to use Prophet in Python and connect to the InfluxDB client.

The Add-on build a lightweight Docker container based in that image and implements a REST API based on FastAPI for time series forecasting using Meta's (formerly Facebook) Prophet model, enabling easy forecasting based on historical data. [Prophet](https://facebook.github.io/prophet/).
Ideal for generating real-time predictions within Home Assistant. Use it inside your Python code in you own custom component.

It also uses the InfluxDB database that can be installed with the official Addon at [InfluxDB addon](https://github.com/hassio-addons/addon-influxdb)
To date, this addon runs version 1.8 of Influx, so the recommended query format is InfluxQL.
The use of Flux-type queries specific to InfluxDB V2 has not been tested, although it is possible to use them in the Chronograph interface of the Addon. InfluxDB 2's token-based authentication processes are not supported.

The plugin can work without problems even if InfluxDB is not installed. In this case, only the forecast endpoint can be used by sending the data for training in json format as can be seen in the examples.

## Features
- **REST API**: Receives JSON-formatted data and returns predictions in JSON.
- **Prophet Model**: Utilizes Prophet, a robust and accurate time series model, ideal for trend and seasonality-based data.
- **ISO Date Format**: Returns dates in ISO format to ensure compatibility.

## Usage
1. **Requests endpoint /forecast**: Send data in JSON format to receive forecasts.
2. **Requests endpoint /query**: Send InfluxQL query to receive forecasts.
3. **Requests endpoint /energy_queries**: special endpoint to send InfluxQL energy queries to receive forecast.

### Basic example endpoint `forecast`
Send a POST request to the API `forecast` endpoint with date and value data in the following format:
```bash
curl -X POST "http://localhost:5000/forecast" -H "Content-Type: application/json" -d 'json_string'
```
```python
import requests
import json

# API URL
url = "http://localhost:5000/forecast"

# Sample data (dates and values)
data = {
    "data": [
        {"ds": "2024-01-01", "y": 10},
        {"ds": "2024-01-02", "y": 15},
        {"ds": "2024-01-03", "y": 13},
        {"ds": "2024-01-04", "y": 18}
    ],
    "numPeriods": 30
}

# Make the POST request
response = requests.post(url, json=data)

# Check the response
if response.status_code == 200:
    forecast = response.json()
    print("Forecast:")
    print(json.dumps(forecast, indent=2))
else:
    print("Error:", response.status_code)
    print(response.text)
```
The API will return a forecast of future values.
If `numPeriods` is not specified, it returns the forecast for 30 periods.

#### Example endpoint `query`
Send a POST request to the API `query` endpoint with a InfluxDB InfluxQL query (parameters for InfluxDB are not needed if they are set in the UI):
```bash
curl -X POST "http://localhost:5000/query" -H "Content-Type: application/json" -d 'json_string'
```

```python
import requests
import json

# API URL
url = "http://localhost:5000/query"

# Query request data
data = {
    "str_query": "SELECT * FROM your_measurement WHERE time > now() - 1d",
    "user": "your_user",
    "password": "your_password",
    "dbname": "your_dbname",
    "numPeriods": 30
}

# Make the POST request
response = requests.post(url, json=data)

# Check the response
if response.status_code == 200:
    forecast = response.json()
    print("Forecast:")
    print(json.dumps(forecast, indent=2))
else:
    print("Error:", response.status_code)
    print(response.text)
```
The API will return a forecast of future values training Prophet with the InfluxDB query results
If `numPeriods` is not specified, it returns the forecast for 30 periods.

## All in one test example
The following test code makes use of the 3 endpoints consecutively
Configure base_url to then url of your Home Assistant if you test it outside the HA machine.
```python
import requests
from datetime import datetime, timedelta
import pandas as pd
import pytz

influx_pass="your_influx_pass"

# Container-API-Addon URL base
base_url = "http://localhost:5000"

# Sample data endpoint /forecast
forecast_data = {
    "data": [
        {"ds": "2023-01-01", "y": 10},
        {"ds": "2023-01-02", "y": 15},
        {"ds": "2023-01-03", "y": 20}
    ],
    "futurePeriods": 10
}

# Send POST request to the /forecast endpoint
response = requests.post(f"{base_url}/forecast", json=forecast_data)
print("\nForecast response:", response.json())

# Functions to make InfluxDB queries in /query endpoint and /energy_queries endpoint
class_local_timezone=pytz.timezone('Europe/Madrid')

def format_date_for_influxdb( date) -> str:
    """
    Return a date and time with timezone information in the format '2024-10-01T00:00:00Z' (UTC timezone).
    """
    date = pd.to_datetime(date)
    # Check if date has a localized time
    if date.tzinfo is None:
        if class_local_timezone is None:
            date_tz = 'Europe/Madrid'        
            date = date.tz_localize(date_tz)
        else:
            date = date.tz_localize(class_local_timezone)
    # Localize the date and time to the UTC timezone
    # date = await asyncio.to_thread(date.tz_convert, 'UTC')
    date = date.tz_convert('UTC')
    # Format the date in ISO 8601 format
    date = date.strftime('%Y-%m-%dT%H:%M:%SZ')
    return date

def energy_query_string(entity_id, start: str | None = None, end: str | None = None) -> str:
    """Create the SQL query string for energy data."""
    if start is not None:
        # start = await self.format_date_for_influxdb(start)
        start = format_date_for_influxdb(start)
    if end is not None:
        # end = await self.format_date_for_influxdb(end)
        end = format_date_for_influxdb(end)
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


# Sample data for endpoint /query
end=datetime.now()
start=end-timedelta(days=10)
entity_id1 = "energy_current_hour"
str_query = energy_query_string(entity_id1, start=start, end=end)
query_data = {
    "str_query": str_query,
    "influx_host": "192.168.0.100",
    "influx_port": 8086,
    "influx_user": "homeassistant",
    "influx_password": influx_pass,
    "influx_dbname": "homeassistant",
    "futurePeriods": 10
}

# Send request POST endpoint /query
response = requests.post(f"{base_url}/query", json=query_data)
if response.status_code == 200:
    try:
        print("\nQuery response:", response.json())
        cc_response = {str(k): v for k, v in response.json().items()}
        cc_response = {pd.to_datetime(k).tz_convert(class_local_timezone)\
                       .strftime('%Y-%m-%dT%H:%M:%S'): v for k, v in cc_response.items()}
        print()
        print("\nQuery response local timezone:", cc_response)        
    except requests.exceptions.JSONDecodeError:
        print("Failed to decode JSON response")
else:
    print(f"Request failed with status code {response.status_code}")


# Prepare data for the /energy_queries endpoint

end=datetime.now()
start=end-timedelta(days=10)
entity_id1 = "victron_vebus_acin1toacout_228"
str_query1 = energy_query_string(entity_id1, start=None, end=end)
entity_id2 = "victron_vebus_invertertoacout_228"
str_query2 = energy_query_string(entity_id2, start=None, end=end)
energy_query_data = {
    "str_query1": str_query1,
    "str_query2": str_query2,
    "influx_host": "192.168.0.100",
    "influx_port": 8086,
    "influx_user": "homeassistant",
    "influx_password": influx_pass,
    "influx_dbname": "homeassistant",
    "futurePeriods": 12
}

# Send Request POST endpoint /energy_queries
response = requests.post(f"{base_url}/energy_queries", json=energy_query_data)
if response.status_code == 200:
    try:
        print("\nEnergy Queries response:", response.json())
        cc_response = {str(k): v for k, v in response.json().items()}
        cc_response = {pd.to_datetime(k).tz_convert(class_local_timezone)\
                       .strftime('%Y-%m-%dT%H:%M:%S'): v for k, v in cc_response.items()}
        print("\nEnergy Queries response local timezone:", cc_response)
    except requests.exceptions.JSONDecodeError:
        print("Failed to decode JSON response")
else:
    print(f"Request failed with status code {response.status_code}")
```

