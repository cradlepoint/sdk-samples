# Container Management

Cradlepoint routers support Docker containers via a custom runtime (not standard Docker Engine). Containers are managed through:
1. **REST API** — deploy, configure, enable/disable projects
2. **SSH CLI** — list, start, stop, pull, exec, logs
3. **Status API** — monitor running container state

## Prerequisites

- NCOS 7.2.20+
- Advanced license on the router
- Supported routers: AER2200, IBR1700 (ARMv7); E300, E3000, R920, R980, R1900, R2100 (ARMv8/ARM64)
- Internet connectivity to pull images from Docker Hub (or private registry)

---

## REST API (Config)

### Deploy a Container Project

```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/projects/" \
  -d 'data={"name":"myproject","config":"version: \"2.4\"\nservices:\n  myapp:\n    image: redis:alpine\n    restart: unless-stopped\n    ports:\n      - \"6379:6379\"","enabled":true,"update_interval":0}'
```

**CRITICAL**: Use form-encoded `data=` parameter with a JSON string value. Do NOT use `Content-Type: application/json` with a raw JSON body — it returns `{"success": false, "data": {"exception": "key", "key": "data"}}`.

### Project Schema (`config/container/projects`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Project name (unique) |
| `config` | string | docker-compose YAML as a single escaped string |
| `enabled` | boolean | Whether the project is active (default: true) |
| `update_interval` | u32 | Image update check interval in seconds (0 = no auto-updates) |
| `_id_` | uuid | Auto-generated project ID |

### List Projects

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/config/container/projects/"
# Response: {"success": true, "data": [{"_id_": "uuid", "name": "...", "config": "...", "enabled": true, "update_interval": 0}]}
```

### Delete a Project

```bash
# Delete by index (0-based)
curl -s -k -u admin:pass -X DELETE "https://ROUTER_IP/api/config/container/projects/0"
```

### Enable/Disable a Project

```bash
# Using the project's _id_
curl -s -k -u admin:pass -X PUT "https://ROUTER_IP/api/config/container/projects/UUID/enabled" \
  -d 'data=true'
```

### Container Daemon Config

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/config/container"
# Response: {"success": true, "data": {"daemon_opts": {"bip": "172.17.0.1/16"}, "projects": [...], "registry": [...]}}
```

The `daemon_opts.bip` controls the Docker bridge IP subnet (default: `172.17.0.1/16`).

### Registry Configuration

```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/registry/" \
  -d 'data={"server":"registry.example.com","username":"user","password":"pass"}'
```

| Field | Type | Description |
|-------|------|-------------|
| `server` | string | Registry URL |
| `username` | string | Registry username |
| `password` | string | Registry password (encrypted at rest) |
| `ca_uuid` | uuid | Optional CA certificate UUID |
| `cert_uuid` | uuid | Optional client certificate UUID |

---

## SSH CLI Commands

Access via SSH: `ssh admin@ROUTER_IP` (or `sshpass -p 'pass' ssh -o StrictHostKeyChecking=no admin@ROUTER_IP "command"`)

### container list

Lists all running containers.

```
container list
```

Returns empty output if no containers are running.

### container logs CONTAINER_NAME

View logs for a running container. Requires `logging: {driver: json-file}` in the compose YAML.

```
container logs ntopng_ntopng_1
```

Note: Container names follow the pattern `{project}_{service}_{instance}`.

### container start PROJECT_NAME

Start a stopped project (pulls image if not present).

```
container start ntopng
```

### container stop PROJECT_NAME

Stop a running project (containers remain and can be restarted).

```
container stop ntopng
```

### container kill PROJECT_NAME

Force-kill a project's containers.

```
container kill ntopng
```

### container pull PROJECT_NAME

Pull latest images for a project without starting it.

```
container pull ntopng
```

### container exec CONTAINER_NAME [CMD]

Execute a command in a running container. Default CMD is `/bin/bash`.

```
container exec ntopng_ntopng_1 sh
container exec ntopng_ntopng_1 ls /var/lib/ntopng
```

**IMPORTANT**: `container exec` does NOT return stdout to the SSH session for non-interactive commands. Use it primarily for interactive shell access (`sh` or `bash`).

---

## Status API

### Check Container Status

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/status/container/PROJECT_NAME"
```

Returns `null` when:
- No containers are running
- Image is still being pulled
- Project doesn't exist

When running, returns state, info, and stats per container.

### System Logs for Container Events

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/status/log"
```

Container-related log entries use facilities: `containers`, `cpcontainer`. Filter by these to see pull progress, errors, and lifecycle events.

Log entry format: `[timestamp, facility, level, message, null]`

Common log patterns:
- `"Trying to pull IMAGE from https://registry-1.docker.io v2"` — pull starting
- `"Project NAME pull failure"` — image pull failed (wrong arch, tag not found, etc.)
- `"No matching registry auth information for url ..."` — registry auth issue (usually harmless for Docker Hub public images)

---

## Control API

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/control/container"
# Response: {"success": true, "data": {"debug": false, "action": {}, "test": {}, "client_timeout": 8}}
```

The control tree for containers is minimal — most management is done via config API (deploy/enable/disable) or SSH CLI (start/stop/logs).

---

## Docker-Compose Requirements

### Version and Restart Policy
```yaml
version: "2.4"                    # REQUIRED — not v3
services:
  myservice:
    image: myimage:tag
    restart: unless-stopped       # REQUIRED — "always" is rejected
```

### Resource Limits (Compose v2.4 syntax)
```yaml
services:
  myservice:
    image: myimage
    mem_limit: 512m               # Memory limit
    cpus: 2                       # CPU cores
    shm_size: "1gb"               # Shared memory (for DBs, browsers)
```

Do NOT use `deploy.resources.limits` — that's v3 Swarm syntax.

### Networking
```yaml
services:
  myservice:
    image: myimage
    ports:
      - "8080:80"                 # Publish ports (no host networking)
```

- `network_mode: host` is NOT supported
- Default bridge networking only
- Published ports accessible on router IP from LAN (requires zone forwarding)

### Volumes
```yaml
services:
  myservice:
    volumes:
      - mydata:/data

volumes:
  mydata:
    driver: local                 # REQUIRED on all named volumes
```

### Logging
```yaml
services:
  myservice:
    logging:
      driver: json-file           # Required for "container logs" to work
```

---

## Building Custom ARM64 Images

Many Docker Hub images only provide amd64 builds. For ARM64 routers (E300, E3000, R920, R980, R1900, R2100), you may need to build your own.

### Known amd64-Only Images (Do NOT Use on ARM64 Routers)
- `ntop/ntopng` — only `latest` tag exists, amd64 only
- Many niche/community images

### Cross-Build Workflow (from macOS/x86)

1. Create a Dockerfile targeting ARM64 packages:

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends mypackage && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
EXPOSE 8080
CMD ["mycommand"]
```

2. Build for linux/arm64 with buildx:

```bash
# Build and load locally (for testing)
docker buildx build --platform linux/arm64 -t myimage:arm64 --load .

# Build and push to Docker Hub
docker buildx build --platform linux/arm64 -t username/myimage:arm64 --push .
```

3. Deploy to router using your registry image name in the compose config.

### ntopng ARM64 Example

See `docker/ntopng-arm64/Dockerfile` in this repo. Uses the official ntop apt repository which provides aarch64 packages.

```bash
docker buildx build --platform linux/arm64 \
  -t yourusername/ntopng:arm64 --push docker/ntopng-arm64/
```

Then deploy:
```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/projects/" \
  -d 'data={"name":"ntopng","config":"version: \"2.4\"\nservices:\n  ntopng:\n    image: yourusername/ntopng:arm64\n    restart: unless-stopped\n    mem_limit: 512m\n    ports:\n      - \"3000:3000\"\n    volumes:\n      - ntopng-data:/var/lib/ntopng\n    logging:\n      driver: json-file\nvolumes:\n  ntopng-data:\n    driver: local","enabled":true,"update_interval":0}'
```

---

## Full Deployment Workflow

### 1. Deploy via REST

```bash
curl -s -k -u admin:pass -X POST "https://ROUTER_IP/api/config/container/projects/" \
  -d 'data={"name":"PROJECT","config":"COMPOSE_YAML_STRING","enabled":true,"update_interval":0}'
```

### 2. Monitor Pull Progress

```bash
# Check logs for pull status
curl -s -k -u admin:pass "https://ROUTER_IP/api/status/log" | \
  python3 -c "import json,sys; [print(e[3]) for e in json.load(sys.stdin)['data'] if 'container' in str(e[1]).lower()]"
```

Or via SSH:
```bash
sshpass -p 'pass' ssh admin@ROUTER_IP "container list"
```

### 3. Verify Running

```bash
curl -s -k -u admin:pass "https://ROUTER_IP/api/status/container/PROJECT"
```

### 4. View Logs

```bash
sshpass -p 'pass' ssh admin@ROUTER_IP "container logs PROJECT_SERVICE_1"
```

### 5. Troubleshoot Pull Failures

Common causes:
- **"manifest unknown"** — image tag doesn't exist for the target architecture
- **"No matching registry auth"** — usually harmless for public images
- **Timeout** — router has limited bandwidth, large images take time

Check architecture compatibility:
```bash
# From your dev machine
curl -s "https://hub.docker.com/v2/repositories/NAMESPACE/IMAGE/tags?page_size=20" | \
  python3 -c "import json,sys; [print(f\"{t['name']}: {[i['architecture'] for i in t['images']]}\") for t in json.load(sys.stdin)['results']]"
```

### 6. Remove a Project

```bash
curl -s -k -u admin:pass -X DELETE "https://ROUTER_IP/api/config/container/projects/0"
```

---

## Gotchas

- **REST API format for config POST** — use `data=JSON_STRING` form encoding, NOT `Content-Type: application/json`
- **Pull failures are silent in status API** — `status/container/PROJECT` returns `null` whether pulling, failed, or non-existent. Check system logs for pull errors
- **Container names** — follow `{project}_{service}_{instance}` pattern (e.g., `ntopng_ntopng_1`)
- **Image architecture must match router** — ARM64 routers cannot run amd64 images. The pull will fail with "manifest unknown" or similar
- **`container exec` stdout** — does not return to SSH session for non-interactive commands
- **Zone forwarding required for LAN access** — published container ports on the router IP require firewall zone forwarding from LAN Zone to Router Zone
- **Volume driver: local is mandatory** — all named volumes must explicitly declare `driver: local`
- **No host filesystem mounts** — containers can only use Docker volumes between each other
- **First pull is slow** — router WAN bandwidth is often limited; large images (>100MB) may take minutes
