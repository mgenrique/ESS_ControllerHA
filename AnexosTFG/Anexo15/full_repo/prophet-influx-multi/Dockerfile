# Etapa de construcción
FROM python:3.11-slim AS build

# Construcción multiplataforma y subida a DockerHub con el comando siguiente
# docker buildx build --platform linux/amd64,linux/arm64 -t mgenrique/prophet-influx:1.0 --push .
# Instala dependencias del sistema necesarias para Prophet
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgomp1 build-essential python3-dev cmake ninja-build && \
    rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia solo los archivos necesarios para instalar las dependencias
COPY requirements.txt ./

# Actualiza pip e instala las dependencias de la aplicación
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Etapa final
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia las dependencias instaladas desde la etapa de construcción
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

