FROM mgenrique/prophet-influx:1.0

# Copia el archivo main.py al contenedor
COPY main.py /app/main.py

# Copia el script de arranque
COPY run.sh /app/run.sh

# Da permisos de ejecución al script de arranque
RUN chmod +x /app/run.sh

# Fundamental crear la carpeta data para que HA pueda generar el archivo /data/options.json 
# Este archivo contiene las opciones configuradas por el usuario y será leído en main.py
WORKDIR /data

# Comando de arranque
CMD ["/app/run.sh"]
