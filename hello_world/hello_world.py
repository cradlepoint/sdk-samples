# hello_world - log "Hello World!"
from csclient import EventingCSClient

cp = EventingCSClient("hello_world")
cp.log("Hello World!")
