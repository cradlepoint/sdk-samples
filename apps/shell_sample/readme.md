# shell_sample
Demonstrates how to execute Linux shell commands from a Python SDK app and capture the output. Provides a reusable `shell()` function that runs any command and returns its stdout.

## How It Works

The app defines a `shell(cmd)` helper function that:
1. Splits the command string into arguments
2. Launches the command using `subprocess.Popen`
3. Reads stdout line by line
4. Returns the complete output as a string

The demo runs `ls -al` and logs the output.

## The shell() Function

```python
def shell(cmd):
    from subprocess import Popen, PIPE
    output = ''
    cmd = cmd.split(' ')
    tail = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    for line in iter(tail.stdout.readline, ''):
        if tail.returncode:
            break
        if line:
            output += line
    return output
```

Use it for any shell command:
```python
shell('ls -al')
shell('ifconfig')
shell('cat /proc/uptime')
```

## Sample Output

```
Starting...
Output:
    drwxr-xr-x    4 cpshell  cpshell        736 May 11 09:19 .
    drwx------    3 cpshell  cpshell        232 May 11 09:19 ..
    drwxr-xr-x    2 cpshell  cpshell        304 May 11 09:19 METADATA
    drwxr-xr-x    2 cpshell  cpshell        248 May 11 09:19 __pycache__
    -rwxr-xr-x    1 cpshell  cpshell      21156 Jan 27 11:51 csclient.py
    -rwxr-xr-x    1 cpshell  cpshell        271 Jan 24 18:26 package.ini
    -rwxr-xr-x    1 cpshell  cpshell        731 May 11 09:19 shell_sample.py
    -rwxr-xr-x    1 cpshell  cpshell         36 Jan 24 18:26 start.sh
```

## Use Cases

- Run diagnostic commands (`ifconfig`, `route`, `arp`, `netstat`)
- Check system state (`cat /proc/uptime`, `free`, `df`)
- Execute bundled binaries
- Interact with hardware devices

## Limitations

- Commands run as the `cpshell` user (limited permissions)
- Cannot run interactive commands that require stdin input
- Command string is split on spaces — does not handle quoted arguments
- No shell features (pipes, redirects, globbing) — these require `shell=True`

## Requirements

- Router firmware 7.26 or later
- The command must exist in the router's filesystem
