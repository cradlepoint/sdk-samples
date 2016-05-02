# Router App/SDK sample application design tools.

## File Make.py

This is the main build tool - see <http://wikis.iatips.com/> for how-to-use
documentation.

## Directory config

Hold various shared configuration files, plus the default main.py

## Directory cp_lib

Common library modules. Most are designed to work on the Cradlepoint router,
although most can run on either a router or (for testing) on a PC

## Directory data - SAMPLES

Code Sample related to 'data' usage and movement.
* json_settings - simple JSON server on TCP port 9901, which allows
a JSON RPC client to query the CradlepointAppBase 'settings' data

## Directory demo - SAMPLES

Larger code applications related to customer demos.
* gpio_power_loss - monitor the IBR11X0 2x2 power connector input to detect
power loss. Email an alert when power is lost or restored.
* hoops_counter - run both a JSON RPC server and web server.
They share a counter value (app_base.data["counter"]).
JSON RPC server assumes a remote client puts (writes) new counter values.
The web server shows as 5 large graphic digits on a page.

## Directory gpio - SAMPLES

Code Samples related to router input/output pins:
* power - read the 2x2 power connector gpio on the IBR11X0
* serial_gpio - read 3 inputs on the IBR11X0's RS-232 port

## Directory gps - SAMPLES

Code Samples related to router GPS:
* probe_gps - query the router STATUS tree, showing if the router supports
GPS, and if any active modems show GPS data

## Directory network - SAMPLES

Code Samples related to common TCP/IP network tasks:
* **warning: any 'server function' requires the router firewall to be
correctly changed to allow client access to the router.**
* digit_web - display a web page of a 5-digit number, as JPG images per digit.
This demonstrates support for a simple web page with embedded objects, \
which means the remote browser makes multiple requests.
* send_email - send a single email to GMAIL with SSL/TLS
* send_ping - use Router API control tree to send a ping.
Sadly, is fixed to 40 pings, so takes about 40 seconds!
* simple_web - display a web page with a short text message.
* tcp_echo - accept a raw client, echoing back (repeating) any text received.

## Directory serial_port - SAMPLES

Code Samples related to common TCP/IP network tasks:
* list_port - tests ports on IBR11X0 - firmware does NOT yet support
* serial_echo - open IBR11X0 RS-232 port, echo by bytes received
- firmware does NOT yet support properly

## Directory simple - SAMPLES

Code Samples related to common tasks:
* hello_world - single python file running, sending text message to Syslog.
Naming the code file 'main.py'
prevents make.py from including the default main.py and many cplib files.
* hello_world_1task - send text message to Syslog, but creates 1 sub-task
to do the sending. On a PC, a KeyboardInterrupt shows how to gracefully
stop children tasks.
* hello_world_2task - send 3 text messages to Syslog, by creating 3 sub-tasks
to do the sending. 2 sub-tasks run forever, while the third exists frequently
and is restarted.
* hello_world-app - send a text message to Syslog. uses the CradlepointAppBase.
* send_alert - send an ECM alert.

## Directory test

Unittest scripts

## Directory tools

Shared modules NEVER designed to run on the router.
Most of the tools here are used by MAKE.PY
