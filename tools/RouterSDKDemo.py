"""Router SDK Demo Application."""

import json
import subprocess
import time


class CSClient(object):
    """A wrapper class for the csclient executable."""

    def get(self, path):
        """Formulate a get command for the csclient executable."""
        cmd = "csclient -m get -b {}".format(path)
        return self.dispatch(cmd)

    def put(self, path, data):
        """Formulate a put command for the csclient executable."""
        data = json.dumps(data).replace(' ', '')
        cmd = "csclient -m put -b {} -v {}".format(path, data)
        return self.dispatch(cmd)

    def append(self, path, data):
        """Formulate an append command for the csclient executable."""
        data = json.dumps(data).replace(' ', '')
        cmd = "csclient -m append -b {} -v {}".format(path, data)
        return self.dispatch(cmd)

    def delete(self, path, data):
        """Formulate a delete command for the csclient executable."""
        data = json.dumps(data).replace(' ', '')
        cmd = "csclient -m delete -b {} -v {}".format(path, data)
        return self.dispatch(cmd)

    def dispatch(self, cmd):
        """Dispatch the csclient executable command via the shell."""
        result, err = subprocess.Popen(cmd.split(' '),
                                       stdout=subprocess.PIPE).communicate()
        return result.decode()


class GPIO(object):
    """A class that represents a GPIO pin."""

    LOW = 0
    HIGH = 1

    def __init__(self, client, name, initial_state=LOW):
        """GPIO class initialization."""
        self.client = client
        self.name = name
        self.state = initial_state
        self.set(self.state)

    def get(self):
        """Request and return the state of the GPIO pin."""
        self.state = self.client.get('/status/gpio/%s' % self.name)
        return self.state

    def set(self, state):
        """Set the state of the GPIO pin."""
        self.state = state
        self.client.put('/control/gpio', {self.name: self.state})

    def toggle(self):
        """Toggle the state of the GPIO pin."""
        self.set(self.LOW if self.state else self.HIGH)
        return self.state


def run():
    """Application entry point."""
    client = CSClient()
    led = GPIO(client, "LED_USB1_G")

    while True:
        time.sleep(.5)
        led.toggle()


if __name__ == '__main__':
    run()
