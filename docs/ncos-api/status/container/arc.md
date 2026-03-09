# status/container – arc

<!-- path: status/container/arc -->
<!-- type: status -->

[status](../) / [container](../container.md) / arc

---

ARC container info and stats (depth 3). Per-container `info.arc[]` and `stats.arc[]`.

### info.arc[]

| Field | Type | Description |
|-------|------|-------------|
| `Id` | string | Container ID |
| `Created` | string | Creation timestamp |
| `Path` | string | Entrypoint path |
| `Args` | array | Args |
| `State` | object | See sub-table |

**info.arc[].State**

| Field | Type | Description |
|-------|------|-------------|
| `Status` | string | exited, running, etc. |
| `Running` | boolean | Running |
| `Paused` | boolean | Paused |
| `Restarting` | boolean | Restarting |
| `OOMKilled` | boolean | OOM killed |
| `Dead` | boolean | Dead |
| `Pid` | number | PID |
| `ExitCode` | number | Exit code |
| `Error` | string | Error message |

### stats.arc[]

| Field | Type | Description |
|-------|------|-------------|
| `read` | string | Read timestamp |
| `preread` | string | Pre-read timestamp |
| `pids_stats` | object | PID stats |
| `blkio_stats` | object | Block I/O stats |
| `num_procs` | number | Process count |
| *(varies)* | * | Other stats |
