# Comandos útiles desde el shell
- Mostrar contenedores en ejecución
```bash
docker ps
```
- Mostrar todos los contenedores
```bash
docker ps -a
```

- Mostrar imagenes
```bash
docker images -a
```
- Borrar un contenedor
```bash
docker rm <container ID>
```
- Borrar una imagen
```bash
docker rmi <image ID>
```
- Ejecutar un contenedor
```bash
docker run <container ID>
```
- Entrar en el shell de un contenedor en ejecución
```bash
docker exec -it <container ID> /bin/bash
```
- Salir del shell de un contenedor
```bash
exit
```
- Construir un contenedor
Desde una carpeta que contenga un archivo Dockerfile
```bash
docker build -t image_name .
```
- Ejecutar el contenedor recien creado
```bash
sudo docker run -p 5000:5000 image_name
```
- Crear archivos si nano o vi no están disponibles
```bash
echo '{' > options.json
echo '  "INFLUXDB_HOST": "a0d7b954-influxdb",' >> options.json
echo '  "INFLUXDB_PORT": 8086,' >> options.json
echo '  "INFLUXDB_USER": "homeassistant",' >> options.json
echo '  "INFLUXDB_PASSWORD": "xxx",' >> options.json
echo '  "INFLUXDB_DBNAME": "homeassistant"' >> options.json
echo '}' >> options.json
```
- Instalar nano
Primero entrar en el shell del contenedor y luego
Instalar nano para poder editar archivos
```bash
apt-get update && apt-get install -y nano
```

Crear o modificar archivos como /data/options.json o /app/main.py
```bash
nano /app/main.py
```

- Hacer login para subir o bajar imagenes de Docker Hub
```bash
docker login
```
- Etiquetar una imagen para subirla a Docker Hub
```bash
docker tag image_name mgenrique/image_name:1.0
```
- Subir la imagen a Docker Hub
```bash
docker push mgenrique/image_name:1.0
```
- Descargar una imagen de Docker Hub
```bash
docker pull mgenrique/image_name:1.0
```




