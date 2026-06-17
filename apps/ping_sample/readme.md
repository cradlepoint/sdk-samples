# ping_sample
Contains a ping function and example usage.

## API

```python
def ping(host, **kwargs):
    """
    :param host: string - destination IP address to ping
    :param kwargs:
        "num": number of pings to send. Default is 4
        "srcaddr": source IP address. If blank NCOS uses primary WAN.
    :return: dict {
        "tx": int - number of pings transmitted
        "rx": int - number of pings received
        "loss": float - percentage of lost pings (e.g. "25.0")
        "min": float - minimum round trip time in milliseconds
        "max": float - maximum round trip time in milliseconds
        "avg": float - average round trip time in milliseconds
        "error": string - error message if not successful
    }
    """
```

## Requirements

- `cp` — SDK CS Client (e.g. `CSClient()` or `EventingCSClient()`)

## Expected Output

Ping output to 8.8.8.8.
