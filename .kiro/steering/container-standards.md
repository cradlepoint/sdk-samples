---
inclusion: manual
description: "Docker/container development standards for Cradlepoint routers"
---
# Docker / Container Development

### When to Use SDK Apps vs Containers

- **Prefer SDK apps** — they are smaller, use fewer resources, and are included with ALL device licenses (no extra cost)
- **Any pure-Python library can be pip-installed into an app folder** — needing a third-party Python module is NOT a reason to use a container. Only use a container when you need compiled (non-Python) software, root access, or LAN-client networking
- **NEVER deploy or build a container without explicit user confirmation** — containers require an Advanced license (extra cost) and have technical constraints. Always ask the user before choosing a container approach, even if the task seems to require one. The user may not have the license, may prefer an alternative, or may have technical reasons to avoid containers
- **Use containers when you need**:
  - Compiled Linux packages or applications that are NOT pure Python (e.g., ntopng, InfluxDB, nginx, PostgreSQL, Node.js)
  - Root access
  - The app to behave like a client device on a LAN IP address (going through the firewall)
- **Containers require an Advanced license** — this costs more than the standard license that includes SDK apps
- **Rule of thumb**: build it as an SDK app unless you need compiled binaries, root, or LAN-client networking — and even then, confirm with the user first

### Deployment

- **Deploy containers via REST API** - POST to `/api/config/container/projects/` with **form-encoded data** (NOT JSON body). Use `-d 'data={"name":"...","config":"...","enabled":true,"update_interval":0}'`. Using `Content-Type: application/json` fails with `{"exception": "key", "key": "data"}`
- **Container project schema** (`config/container/projects`):
  - `name` (string) — project name
  - `config` (string) — docker-compose YAML as a single escaped string
  - `enabled` (boolean) — whether the project is active
  - `update_interval` (integer) — update check interval in seconds (0 = no auto-updates)
- **Named volumes MUST have `driver: local`** - Cradlepoint's container runtime requires explicit `driver: local` on all named volumes in docker-compose files. Without it, volume creation fails
- **Use alpine-based images** - prefer `-alpine` image variants to reduce size and RAM usage on the router's limited resources
- **Expect ~200-300MB RAM for InfluxDB** - monitor system metrics when running databases in containers alongside SDK apps
- **Container status API** - `status/container/{name}` shows state, info, and stats per container. Returns `null` when pulling, failed, or non-existent — check system logs for pull errors
- **Many Docker Hub images are amd64-only** — always verify ARM64 support before deploying. Use `docker buildx build --platform linux/arm64` to cross-build your own if needed. See `docs/ncos-api/control/container.md` for the full workflow
- **Full container docs**: See `docs/ncos-api/control/container.md` for REST API, SSH CLI, building custom images, and troubleshooting

### SSH Container CLI

Access via: `sshpass -p 'pass' ssh admin@ROUTER_IP "container COMMAND"`

| Command | Description |
|---------|-------------|
| `container list` | List running containers |
| `container logs CONTAINER_NAME` | View logs (needs `logging: {driver: json-file}`) |
| `container start PROJECT_NAME` | Start a project |
| `container stop PROJECT_NAME` | Stop a project |
| `container kill PROJECT_NAME` | Force-kill a project |
| `container pull PROJECT_NAME` | Pull latest images |
| `container exec CONTAINER_NAME [CMD]` | Shell into container (default: /bin/bash) |

- Container names follow `{project}_{service}_{instance}` pattern (e.g., `ntopng_ntopng_1`)
- `container exec` does NOT return stdout for non-interactive commands — use for interactive shell only
- **Resource limits ARE supported** — use `mem_limit` and `cpus` at the service level (Compose v2.4 syntax). Do NOT use `deploy.resources.limits` (that's v3 Swarm syntax)
- **`mem_limit`** — e.g. `mem_limit: 512m` (megabytes) or `mem_limit: 1g` (gigabytes)
- **`cpus`** — e.g. `cpus: 2` (number of CPU cores allocated)
- **`shm_size`** — e.g. `shm_size: "1gb"` for services needing more than 64MB shared memory
- **Use Compose version "2.4"** - Cradlepoint's container runtime uses Compose v2.4, not v3. Always set `version: "2.4"` in docker-compose files
- **Use `restart: unless-stopped`** - Cradlepoint does not allow `restart: always`. Use `unless-stopped` instead
- **NO `network_mode: host`** - Cradlepoint's container runtime only supports bridged networking. Use `ports:` to publish ports instead of `network_mode: host`
- **Set shared memory with `shm_size`** - some services (e.g. databases, browsers) need more than the default 64MB `/dev/shm`. Set `shm_size: '1gb'` (or appropriate size) at the service level in docker-compose

### Minimum Requirements
- **NCOS 7.2.20+** required for container support
- **Advanced license** required on the router
- **Supported routers**: AER2200, IBR1700 (ARMv7 32-bit); E300, E3000, R920, R980, R1900, R2100 (ARMv8 64-bit)
- **Container images MUST match router architecture** — use ARM32 images for AER2200/IBR1700, ARM64 for E300/E3000/R920/R980/R1900/R2100

### Memory Available for Containers (by router model)
| Router | All services disabled | All services enabled |
|--------|----------------------|---------------------|
| AER2200/IBR1700 | 460 MB | 135 MB |
| E300/R920/R980 | 921 MB | 371 MB |
| E3000 | 1.84 GB | 1.29 GB |
| R1900/R2100 | 1.80 GB | 1.45 GB |

- Disable Wi-Fi (all radios) and/or IDS/IPS to free memory for containers
- Flash storage: 6 GB (AER2200, IBR1700, E300, R1900), 8 GB (R2100, R920, R980), 14 GB (E3000)

### Networking
- Default Docker subnet starts at 172.17.0.2. Custom subnets configurable via NCM Local IP Networks
- DHCP or static IP assignable to container interfaces (NCOS 7.2.50+)
- Use `network_mode: bridge` (default) — host mode not supported
- **To put a container on a router LAN network** (e.g. Primary LAN), use `driver_opts` with `com.cradlepoint.network.bridge.uuid` set to the LAN's UUID from `config/lan/*/_id_`:

```yaml
version: "2.4"
services:
  myapp:
    image: redis:alpine
    restart: unless-stopped
    networks:
      lannet:
        ipv4_address: 192.168.0.200
networks:
  lannet:
    driver: bridge
    driver_opts:
      com.cradlepoint.network.bridge.uuid: 00000000-0d93-319d-8220-4a1fb0372b51
    ipam:
      driver: default
      config:
        - subnet: 192.168.0.0/24
          gateway: 192.168.0.1
```

- The UUID comes from `cp.get('config/lan/0/_id_')` (Primary LAN) or whichever LAN index you want
- The container gets a real IP on that LAN and goes through the firewall like a client device
- Set a static `ipv4_address` within the subnet and reserve it in DHCP to avoid conflicts

### Volumes and Storage
- **Containers cannot mount the host filesystem** — only Docker volumes between containers
- **Volume data NOT updated on image change** — must create a new project to get fresh volume data
- **Docker volumes cannot be pruned** on routers
- **USB storage** supported (NCOS 7.23.20+) — mounted at `/var/media` in containers
- USB storage: FAT32 only, max partition 32 GB, max file 4 GB, one device at a time
- **Config Store access (`$CONFIG_STORE`)**: use the special volume `$CONFIG_STORE` in the service's volumes list to mount `/var/tmp/cs.sock` — this gives the container access to NCOS config store for SDK-style API operations
- USB plug/unplug restarts affected containers (all containers in project if multiple use USB, just that container if only one)

#### Named volumes example:
```yaml
volumes:
  - etc:/etc
  - usr:/usr
  - db:/data/db
```
Top-level volume declarations require `driver: local`:
```yaml
volumes:
  etc:
    driver: local
  usr:
    driver: local
  db:
    driver: local
```

#### Config Store volume (SDK access from container):
```yaml
version: '2.4'
services:
  ext:
    image: 'cpcontainer/extensibility'
    volumes:
      - $CONFIG_STORE
      - 'shared-data:/home/jovyan'
    networks:
      lannet:
        ipv4_address: 192.168.0.2
volumes:
  shared-data:
    driver: local
networks:
  lannet:
    driver: bridge
    driver_opts:
      com.cradlepoint.network.bridge.uuid: 00000000-0d93-319d-8220-4a1fb0372b51
    ipam:
      driver: default
      config:
        - subnet: 192.168.0.0/24
          gateway: 192.168.0.1
```

- `$CONFIG_STORE` maps to `/var/tmp/cs.sock` inside the container
- Enables Python SDK operations (cp.get/put/post/delete) from within the container
- Use the `cpcontainer/extensibility` image or any image with the SDK installed

### USB Audio (NCOS 7.25.20+)
- Map USB audio devices to containers via `devices: ["/dev/snd:/dev/snd"]` in compose YAML
- Requires `alsa-utils` or equivalent in the container image
- Same plug/unplug restart behavior as USB storage

### USB Serial (OOBM)
- Map USB serial ports via the Volumes & Devices > Devices section in NCM
- Select the USB Serial Port from the Device drop-down

### Health Checks
- Configure via compose `healthcheck` or NCM UI (Test command, Interval, Retries, Timeout)
- Non-zero exit from test command = unhealthy; container restarts per configured condition

### Container Registry
- Docker Hub is the default registry
- Custom registries configurable via NCM: SYSTEM > Containers > Registry
- For Amazon ECR: username is "AWS", password is the auth token from GetAuthorizationToken API

### File Ownership Gotcha
- Replacing a file from the base image changes ownership to `nobody:nobody` (due to user namespace remapping)
- Workaround: copy the file, modify the copy, then `mv` the copy over the original

### Troubleshooting
- `container list` — view installed containers
- `container logs <container_name>` — view logs (requires `logging: {driver: json-file}` in compose)
- `container exec <name> sh` — shell access (use `sh` if `bash` not available)
- `cat /status/container/<project>/info` — view container info from CLI

Example deploy via curl:
```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/projects/" \
  -d 'data={"name":"myproject","config":"version: \"2.4\"\nservices:\n  myapp:\n    image: redis:alpine\n    restart: unless-stopped\n    ports:\n      - \"6379:6379\"\n    logging:\n      driver: json-file","enabled":true,"update_interval":0}'
```

Example with resource limits:
```yaml
version: "2.4"
services:
  edge-ai:
    image: jongaudu/edge-ai:latest
    restart: unless-stopped
    mem_limit: 512m
    cpus: 2

  myservice:
    image: myimage
    shm_size: "1gb"
```

Example volume declaration:
```yaml
volumes:
  my-data:
    driver: local
```
