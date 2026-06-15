# cli_sample
Includes a `csterm.py` library that uses csclient control tree access to local CLI to send commands and return output. Example sends "arpdump".

## Expected Output

```
09:22:40 AM INFO cli_sample Output:
    Type     Interface   State     Link Address      IP Address
    ethernet primarylan1 REACHABLE 14:b1:c8:01:59:09 192.168.0.93
    ethernet primarylan1 FAILED    0/0/0             192.168.0.134
    ethernet primarylan1 FAILED    0/0/0             fe80::311b:39e5:8306:d926
    ethernet primarylan1 STALE     14:b1:c8:01:59:09 fe80::1cd1:9ffa:135:3ed4
    ethernet primarylan1 STALE     14:b1:c8:01:59:09 fe80::18d5:408e:d760:2e39
```

## Notes

`csterm.py` is a useful utility for interacting with the NCOS CLI. Usage is straightforward:

**Run a single command:**

```python
c = EventingCSClient('cli_sample')
ct = CSTerm(c)
ct.exec("arpdump")
```

**Run multiple commands by passing a list:**

```python
ct.exec(["clients", "arpdump"])
```

An instance of CSTerm invokes a single CLI session, similar to SSHing into the device. Besides sending a list of commands into exec, you can execute exec multiple times to send multiple commands:

```python
ct.exec("clients")
ct.exec("wan")
ct.exec("arpdump")
```

**Example workflow using NCOS ssh client:**

```python
ct.exec(["ssh user@host",  # ssh into host
         "yes",            # respond 'yes' to accept host key
         "password",       # respond with password
         "cd workflow",    # change directory
         "ls",            # list files
         "exit"])          # exit ssh session
```

**Adjusting timers:**

```python
ct = CSTerm(c, timeout=10, soft_timeout=5)
```

- `timeout` — absolute timeout when running a command (default: 10 seconds)
- `soft_timeout` — timeout for sending ctrl+c to terminate a running command (default: 5 seconds)
