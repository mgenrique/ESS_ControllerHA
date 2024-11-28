import logging
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prophet import Prophet
import numpy as np
import pandas as pd
from influxdb import InfluxDBClient

# Set logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


app = FastAPI()

class ForecastRequest(BaseModel):
    data: list
    futurePeriods: int = 30
    futureFreq: str = "h"

class QueryRequest(BaseModel):
    str_query: str
    influx_host: str = os.getenv("INFLUXDB_HOST", "localhost")
    influx_port: int = int(os.getenv("INFLUXDB_PORT", 8086))
    influx_user: str = os.getenv("INFLUXDB_USER", "homeassistant")
    influx_password: str = os.getenv("INFLUXDB_PASSWORD", "")
    influx_dbname: str = os.getenv("INFLUXDB_DBNAME", "homeassistant")
    futurePeriods: int = 30
    futureFreq: str = "h"

class EnergyQueryRequest(BaseModel):
    str_query1: str
    str_query2: str = None
    influx_host: str = os.getenv("INFLUXDB_HOST", "localhost")
    influx_port: int = int(os.getenv("INFLUXDB_PORT", 8086))
    influx_user: str = os.getenv("INFLUXDB_USER", "homeassistant")
    influx_password: str = os.getenv("INFLUXDB_PASSWORD", "")
    influx_dbname: str = os.getenv("INFLUXDB_DBNAME", "homeassistant")
    futurePeriods: int = 30
    futureFreq: str = "h"

@app.post("/forecast")
async def forecast(request: ForecastRequest):
    data = request.data
    futurePeriods = request.futurePeriods
    futureFreq = request.futureFreq

    # Check that data is not empty
    if not data:
        logger.error("No data provided for forecasting")
        raise HTTPException(status_code=400, detail="No data provided")

    # Create the DataFrame with the received data
    df = pd.DataFrame(data)

    # Validate that the DataFrame has exactly two columns
    if df.shape[1] != 2:
        logger.error("Data must have exactly two columns: 'ds' and 'y'")
        raise HTTPException(status_code=400, detail="Expected two columns 'ds' and 'y'")

    # Assign names to the columns
    df.columns = ['ds', 'y']

    # Delocalize the dates
    df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None)

    # Configure and train the Prophet model
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=futurePeriods, freq=futureFreq)
    forecast = model.predict(future)
    forecast = forecast[['ds', 'yhat']].tail(futurePeriods)
    
    # Convert dates to ISO format without timezone and create the output dictionary    
    forecast['ds'] = forecast['ds'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    forecast = forecast.set_index('ds')
    response = forecast.to_dict()['yhat']
 
    return response

@app.post("/query")
async def query(request: QueryRequest):
    str_query = request.str_query
    host=request.influx_host
    port=request.influx_port
    user = request.influx_user
    password = request.influx_password
    dbname = request.influx_dbname
    futurePeriods = request.futurePeriods
    futureFreq = request.futureFreq
    try:
        # Connect to InfluxDB
        logger.info(f"Executing query: {str_query}")
        client = InfluxDBClient(host=host, port=port, username=user, password=password, database=dbname)
        logger.debug("Connected to InfluxDB")

        # Execute the query
        result = client.query(str_query)
        logger.debug("Query executed successfully")

        # Convert the result to a DataFrame
        points = list(result.get_points())
        if not points:
            logger.error("No data returned from query")
            raise HTTPException(status_code=400, detail="No data returned from query")

        df = pd.DataFrame(points) # Get dates in UTC
        logger.debug("DataFrame created successfully")

        # Validate that the DataFrame has exactly two columns
        if df.shape[1] != 2:
            logger.error("Data must have exactly two columns: 'ds' and 'y'")
            raise HTTPException(status_code=400, detail="Expected two columns 'time' and the query value")

        # Assign names to the columns
        df.columns = ['ds', 'y']

        # Delocalize the dates
        df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None)

        # Configure and train the Prophet model
        model = Prophet()
        model.fit(df)
        future = model.make_future_dataframe(periods=futurePeriods, freq=futureFreq)
        forecast = model.predict(future)
        forecast=forecast.tail(futurePeriods)

        forecast['ds'] = pd.to_datetime(forecast['ds']).dt.tz_localize('UTC')
        forecast = forecast.set_index('ds')
        response = forecast.to_dict()['yhat']        

        return response
    
    except ConnectionError:
        logger.error("Failed to connect to InfluxDB")
        raise HTTPException(status_code=500, detail="Failed to connect to InfluxDB")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def delta_energy_dataframe(points) -> pd.DataFrame:
    """ The query must have GROUP BY time('time(1h)'). Normally h but can be changed to other time intervals.
    points come in UTC timezone.
    """
    try:
        df = pd.DataFrame(points)
        
        if 'time' not in df.columns:
            logger.error("No 'time' column in the data")
            raise ValueError("Column 'time' not found in the input data")
        
        df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None) # Eliminate the timezone for Prophet
        
        # Convert time to the index of the DataFrame
        df.set_index('time', inplace=True)
        
        if df.empty:
            raise ValueError("DataFrame is empty after setting 'time' as index")
        
        # Create a new column that calculates the hourly energy difference
        df['delta_energy'] = df.iloc[:,0].diff() # Calculate the difference between consecutive values
        df = df.drop(df.index[0]) # Remove the first row of the DataFrame (the hourly difference of the first record does not make sense)
        df = df.drop(df.index[-1]) # Remove the last row of the DataFrame (there isn´t enough data yet in the last hour)
                
        # If there has been any counter reset, the difference will be negative
        mask = df['delta_energy'] < 0
        # The next line is replaced because Prophet can manage perfectly the NaN values
        # df.loc[mask, 'delta_energy'] = 0 # In those cases, set the difference to 0
        df.loc[mask, 'delta_energy'] = np.nan # In those cases, set the difference to NaN
        
        return df
    
    except Exception as e:
        logger.error(f"Error processing delta_energy_dataframe: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/energy_queries")
async def query(request: EnergyQueryRequest):
    """ Post a query to the InfluxDB database for cumulatively accounted energy 
    and return the forecast results using Prophet."""
    str_query1 = request.str_query1
    str_query2 = request.str_query2
    host = request.influx_host
    port = request.influx_port
    user = request.influx_user
    password = request.influx_password
    dbname = request.influx_dbname
    futurePeriods = request.futurePeriods
    futureFreq = request.futureFreq

    # Check that the query has the groupby('time(1h)') clause
    if 'GROUP BY TIME(' not in str_query1.upper():
        logger.error("The query must have GROUP BY time('time(1h)')")
        raise HTTPException(status_code=400, detail="The query must have GROUP BY time('time(1h)')")
    if str_query2 is not None and 'GROUP BY TIME(' not in str_query2.upper():
        logger.error("The query must have GROUP BY time('time(1h)')")
        raise HTTPException(status_code=400, detail="The query must have GROUP BY time('time(1h)')")
    try:
        # Connect to InfluxDB
        client = InfluxDBClient(host=host, port=port, username=user, password=password, database=dbname)
        logger.debug("Connected to InfluxDB step 1")

    except Exception as e:
        logger.error("Failed to connect to InfluxDB")
        raise HTTPException(status_code=400, detail=f"Error connecting to InfluxDB step 1: {str(e)}")
    
    try:
        # Execute the query
        result = client.query(str_query1)
        logger.debug("Query_1 executed successfully")
        # Convert the result to a DataFrame
        points = list(result.get_points()) # Get dates in UTC
    except Exception as e:
        logger.error("Failed to connect to InfluxDB")
        raise HTTPException(status_code=400, detail=f"Error executing query1: {str(e)}")

    
    if not points:
        logger.error("No data returned from query1")
        raise HTTPException(status_code=400, detail="No data returned from query1")
    try:
        df1 = await delta_energy_dataframe(points)
        logger.debug("Query_1 delta_energy_dataframe executed successfully")               
    except:
        logger.error("Error processing dataframes in query1")
        raise HTTPException(status_code=400, detail="Error processing query1")    
    # Optional second query
    if str_query2 is not None:
        result = client.query(str_query2)
        logger.debug("Query_2 executed successfully")

        # Convert the result to a DataFrame
        points = list(result.get_points())
        if not points:
            # raise HTTPException(status_code=400, detail="No data returned from query2")
            logger.warning("Query_2 has not points")
            df = df1
            df.reset_index(inplace=True)
        else:
            logger.debug("Query_2 has points")
            try:
                df2 = await delta_energy_dataframe(points)
                logger.debug("Query_2 delta_energy_dataframe executed successfully")
                # Merge DataFrames
                df = pd.merge(df1, df2, left_index=True, right_index=True, how='outer')
                logger.debug("df = pd.merge(df1, df2, left_index=True, right_index=True, how='outer') OK")
                # The next line is replaced because Prophet can manage perfectly the NaN values
                # df['delta_energy'] = df['delta_energy_x'].fillna(0) + df['delta_energy_y'].fillna(0) # Sum the columns and fill NaN with the present values
                df['delta_energy'] = df['delta_energy_x'] + df['delta_energy_y'] # Sum the columns
                df.reset_index(inplace=True)             
                df = df[['time', 'delta_energy']]
                logger.debug("df = df[['time', 'delta_energy']] OK")
            except Exception as e:
                logger.error(f"Error processing dataframes in query2: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error processing query2: {str(e)}")             
    else:
        df = df1
        df.reset_index(inplace=True)
    # Validate that the DataFrame is not empty
    if df is None or df.empty:
        logger.error("Error processing dataframes")
        raise HTTPException(status_code=400, detail="Error processing dataframes")
    
    # Validate that the DataFrame has exactly two columns
    if df.shape[1] != 2:
        logger.error("Expected two columns 'time' and the query value")
        raise HTTPException(status_code=400, detail="Expected two columns 'time' and the query value")

    try:
        # Assign names to the columns
        df.columns = ['ds', 'y']

        # Delocalize the dates
        # df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None) # Se ha hecho en delta_energy_dataframe

        # Configure and train the Prophet model
        model = Prophet()
        model.fit(df)
        future = model.make_future_dataframe(periods=futurePeriods, freq=futureFreq)
        forecast = model.predict(future)
        forecast=forecast.tail(futurePeriods)

        # Convert dates to ISO format with timezone and create the output dictionary
        forecast['ds'] = pd.to_datetime(forecast['ds']).dt.tz_localize('UTC')
        forecast = forecast.set_index('ds')
        response = forecast.to_dict()['yhat'] 

        return response
    except Exception as e:
        logger.error(f"Error processing Prophet model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    str_port=os.getenv("PORT", "5000")
    # check if str_port is a number
    if not str_port.isdigit():
        logger.error("The PORT environment variable must be a number. Setting default port to 5000")
        port = 5000
    else:
        port = int(str_port)
    str_env_var = os.getenv("INFLUXDB_DBNAME", "Variable de entorno no definida")

    logger.info(f"Starting the FastAPI server on port {port}...")
    logger.info(f"Información de variables de entorno: {str_env_var}")
    uvicorn.run(app, host='0.0.0.0', port=port)
    logger.info("FastAPI server started successfully.")    