# simple_web_server
Demonstrates a very basic web server using the `http` library which is included in NCOS.

## Setup

Port 9001 will need to be opened in the device firewall for access:

```
SECURITY > Zone Firewall > Zone Forwarding > Add >
  Source = Primary LAN Zone,
  Destination = Router,
  Filter Policy = Default Allow All > Save
```

## Expected Output

Message `Hello World from Cradlepoint router!` will be returned when the server receives a GET request.
