# Reproducir el proceso que genera el contenedor cuando se instala como Addon de Home Assistant
Basandonos en la imagen en https://hub.docker.com/repository/docker/mgenrique/prophet-influx/general
vamos a crear en Ubuntu localmente una imagen identica a la que creará HA al instalar el contenedor

Copiamos el contenido de https://github.com/mgenrique/hassos_prophet_addon/tree/main/prophet-influx-multi-addon
Y editamos el Dockerfile localmente para cambiarlo por
```Dockerfile
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

# NUEVO PARA DESARROLLAR LOCALMENTE
COPY options.json /data/options.json

# Comando de arranque
CMD ["/app/run.sh"]
```

En este caso tenemos ya creado el archivo `options.json` en el mismo directorio donde se encuentra el Dockerfile donde habremos ajustado los parametros tal como se haría en la UI de HA.

Tambien podemos aprovechar para cambiar el código en main.py

Y ahora ejecutamos
```bash
docker build -t prophet-influx .
```

Y finalmente iniciamos el contenedor localmente:
```bash
docker run -p 5000:5000 prophet-influx
```
# Opción para trabajar con variables de entorno en lugar de con options.json

El fichero old_main.py es identico al fichero main.py excepto que en lugar de coger los datos de configuración de options.json los lee de las variables de entorno.
Renombrarlo main.py y construir el contenedor igual que antes con
```bash
docker build -t prophet-influx .
```

En este caso, al arrancar el contenedor podemos pasar las variables de entorno en la llamada

```bash
docker run -d --name prophet-influx -p 5000:5000 \
    -e INFLUXDB_HOST=192.168.0.100 \
    -e INFLUXDB_PORT=8086 \
    -e INFLUXDB_USER=homeassistant \
    -e INFLUXDB_PASSWORD=xxx \
    -e INFLUXDB_DBNAME=homeassistant \
    -e PORT=5000 \
    mgenrique/prophet-influx:local
```

