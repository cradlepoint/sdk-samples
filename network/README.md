# Router App/SDK sample applications.

Remember - for any network 'server' application, you will need to go into
the router's Zone Firewall configuration and enable the appropriate traffic
to reach your router. By default, all incoming client packets will be
discarded.

## Directory simple\_web

A very basic web server - a "Hello World" by web, 
using the standard Python 3 "http.server" module.

_Note: requires Router Zone Firewall Changes_

## Directory digit\_web

A more complex basic web server, using the standard Python 3 "http.server"
module. It returns a slightly dynamic page of 5 'digit' images, representing
a 'counter'. In the sample, the digits are fixed at "00310", but a richer
design could allow new numbers to be used.

_Note: requires Router Zone Firewall Changes_

## Directory send\_ping

Uses the router API 'control' tree to issue a raw Ethernet ping.

## Directory send\_email

Sends a fixed email to gmail.com, using TTL/SSL. If you don't have a gmail
account, you can set up a free one. It can also send to other SMTP servers,
but you may need to change the way the SSL works, TCP ports used, etc.

## Directory tcp\_echo

binds on a TCP port, returning (echoing) any data received.

_Note: requires Router Zone Firewall Changes_
