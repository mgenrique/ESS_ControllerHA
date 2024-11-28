#!/bin/bash

echo "Starting addon Prophet InfluxDB..."

# Execute main application
exec python /app/main.py

echo "Addon Prophet InfluxDB finished."
