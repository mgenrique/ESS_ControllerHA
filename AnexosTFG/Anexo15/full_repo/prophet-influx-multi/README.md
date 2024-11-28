# Steps to create the Docker image in Docker Hub
https://hub.docker.com/repository/docker/mgenrique/prophet-influx/general

## In summary
The image was built from Ubuntu where Docker Desktop was installed. Start Docker Desktop and in a terminal...
```bash
cd prophet-influx multi
docker login
docker buildx build --platform linux/amd64,linux/arm64 -t mgenrique/prophet-influx:1.0 --push .
```

When the build is finished, the image is registered in Docker Hub at:
https://hub.docker.com/repository/docker/mgenrique/prophet-influx/general

## General steps
We will create a directory with the Dockerfile and run the entire process using the following lines, which once the creation of the multiplatform image is finished, will upload it to the Docker Hub repository where it will be publicly accessible.
Once we have opened Docker Desktop in a terminal:
```bash
docker login
docker buildx build --platform linux/amd64,linux/arm64 -t user/image:tag --push --load .
```

## Particular configuration for this project
We create the directory `prophet-influx-multi` with the two files and in a terminal we position ourselves inside the directory
```bash
prophet-influx-multi
├── Dockerfile
└── requirements.txt
```
File `requirements.txt`
```plaintext
fastapi
pydantic
prophet
numpy
pandas
influxdb
uvicorn
```

The justification for the need for these libraries will be seen when we see the Python application that will run in the container.

`Dockerfile` file
```bash
# Build stage
FROM python:3.11-slim AS build

# Cross-platform build and push to DockerHub with the following command
# docker buildx build --platform linux/amd64,linux/arm64 -t mgenrique/prophet-influx:1.0 --push .

# Install system dependencies required by Prophet
RUN apt-get update && \
apt-get install -y --no-install-recommends \
libgomp1 build-essential python3-dev cmake ninja-build && \
rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only files needed to install dependencies
COPY requirements.txt ./

# Upgrade pip and install application dependencies
RUN pip install --upgrade pip && \
pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies installed from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
```

Command to start the process
```bash
docker login
docker buildx build --platform linux/amd64,linux/arm64 -t mgenrique/prophet-influx:1.0 --push .
```

After the process is complete, we verify in the Docker Hub account that the image was uploaded correctly and that it has support for both architectures (Docker Hub shows the details of the supported architectures on the image page).

### Dockerfile Explanation
Here is a brief explanation of each line in the provided Dockerfile:

```dockerfile
# Build Stage
FROM python:3.11-slim AS build
```
- `FROM python:3.11-slim AS build`: Defines a Python 3.11 base image in its `slim` version, which is a lightweight and optimized variant. By tagging it as `build`, a build stage is created that allows dependencies to be installed without including them in the final image, reducing the size of the image.

```dockerfile
# Installs required system dependencies for Prophet
RUN apt-get update && \
apt-get install -y --no-install-recommends \
libgomp1 build-essential python3-dev cmake ninja-build && \
rm -rf /var/lib/apt/lists/*
```
- `RUN apt-get update ...`: Installs required system dependencies (such as `build-essential` and `cmake`) to build and run Prophet. Removes the `apt` cache at the end (`rm -rf /var/lib/apt/lists/*`) to reduce the image size.

```dockerfile
# Sets the working directory
WORKDIR /app
```
- `WORKDIR /app`: Changes the current working directory to `/app`, where the application files will be copied and the following commands will be run.

```dockerfile
# Copy only the files needed to install the dependencies
COPY requirements.txt ./
```
- `COPY requirements.txt ./`: Copy the `requirements.txt` file (list of Python dependencies) from the local directory to the working directory in the container (`/app`).

```dockerfile
# Upgrade pip and install the application dependencies
RUN pip install --upgrade pip && \
pip install --no-cache-dir -r requirements.txt
```
- `RUN pip install ...`: Upgrade `pip` and then install the Python dependencies listed in `requirements.txt` without cache (`--no-cache-dir`) to reduce the image size.

```dockerfile
# Final stage
FROM python:3.11-slim
```
- `FROM python:3.11-slim`: Defines a second stage of the final image, again starting from the lightweight Python 3.11 image (`slim`). This approach allows for a smaller final image by copying only the installed dependencies, without including build tools.

```dockerfile
# Sets the working directory
WORKDIR /app
```
- `WORKDIR /app`: Defines the working directory `/app` again in the final stage, ensuring that it is located in the same directory where dependencies and code are copied.

```dockerfile
# Copies installed dependencies from the build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/s
