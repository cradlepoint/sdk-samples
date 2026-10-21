# Running an NCOS SDK Application in a Container

## 1. Add a Dockerfile to your app folder

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
CMD ["python", "-u", "my_app.py"]
```

Swap `my_app.py` for your app's entry point.

## 2. Build and push to Docker Hub

Replace `username` with your Docker Hub account and `my_app` with your image name:

```bash
docker build --platform linux/arm64 -t username/my_app --push .
```

## 3. Compose for the router

Pick one. Ports expose the app on all router interfaces; a LAN IP instead puts the
container on a LAN network, where firewall and routing rules apply.

Option A — expose ports:

```yaml
version: '3'
services:
  my_app:
    image: username/my_app
    restart: unless-stopped
    # Optional ports exposed on all interfaces
    ports:
      - '8000:8000'
    # Add the config store volume for SDK
    volumes:
      - $CONFIG_STORE
```

Option B — give the container a LAN IP:

```yaml
version: '3'
services:
  my_app:
    image: username/my_app
    # Instead of mapping ports you can give the container a LAN IP address.
    # This supports firewall and routing functions.
    networks:
      lannet:
        ipv4_address: 192.168.0.2
    volumes:
      - $CONFIG_STORE
networks:
  lannet:
    driver: bridge
    driver_opts:
      # Use your router's own LAN UUID from NCM config summary
      com.cradlepoint.network.bridge.uuid: 00000000-0d93-319d-8220-4a1fb0372b51
    ipam:
      driver: default
      config:
        - subnet: 192.168.0.0/24
```

To keep app data across reboots, add a named volume: map it into the service and declare
it at the top level with `driver: local`.

```yaml
version: '3'
services:
  my_app:
    image: username/my_app
    # Instead of mapping ports you can give the container a LAN IP address.
    # This supports firewall and routing functions.
    networks:
      lannet:
        ipv4_address: 192.168.0.2
    volumes:
      - $CONFIG_STORE
      # Persist app data across reboots
      - my_app_data:/app/data
volumes:
  my_app_data:
    driver: local
networks:
  lannet:
    driver: bridge
    driver_opts:
      # Use your router's own LAN UUID from NCM config summary
      com.cradlepoint.network.bridge.uuid: 00000000-0d93-319d-8220-4a1fb0372b51
    ipam:
      driver: default
      config:
        - subnet: 192.168.0.0/24
```
