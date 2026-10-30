import random
import time
import re
import sys


class Terminal:
    def inkey(self, timeout=0):
        i = b''
        c, *_ = select.select([sys.stdin],[],[],timeout)
        if c:
            i = os.read(self.fd, 4)
            if len(i) > 1:
                while True:
                    c, *_ = select.select( [sys.stdin], [], [], timeout )
                    if not c:
                        break
                    i += os.read(self.fd, 1024)
        return i.decode()

    def cbreak(self):
        return self

    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        if exc_type is not None:
            raise


try:
    from blessed import Terminal
except ImportError:
    # NOTE: blessed not installed, using fallback terminal (pip3 install blessed)
    import select
    import tty, termios
    import os


class CSTerm:
    INTERVAL = 0.3 # how often to poll for output, faster can sometimes miss output

    def __init__(self, csclient, timeout=10, soft_timeout=5, user=None):
        """
        :param csclient: csclient.EventingCSClient
            csclient object to use for communication
        :param timeout: int
            absolute maximum number of seconds to wait for output (default 10)
        :param soft_timeout: int
            number of seconds to wait for output before sending interrupt (default 5)
        """
        self.c = csclient
        self.timeout = timeout
        self.soft_timeout = soft_timeout
        self.s_id = "term-%s" % random.randint(100000000, 999999999)
        self.user = user
    
    def exec(self, cmds, clean=True):
        """
        :param cmds: list or string
            list of commands to execute or single command to execute
        :param clean: bool
            if True, remove terminal escape sequences from output
        :return: string
            Text output returned from CLI command
        """
        cmds = cmds if isinstance(cmds, list) else [cmds]
        cmds = [c + '\n' for c in cmds]
        timeout = self.timeout
        soft_timeout = self.soft_timeout

        k = iter(cmds)
        kp = next(k)
        r = ''
        start = time.time()
        while True:
            self.c.put("/control/csterm/%s" % self.s_id, self._k(kp))
            rp = self.c.get("/control/csterm/%s" % self.s_id)

            r += rp['k']
            # the output generally will end with a prompt and no newline, so we can check for that
            # after we've sent all our commands
            if kp == "" and not r.endswith('\n'):
                break

            kp = next(k, None) or ""

            time.sleep(self.INTERVAL)
            elapsed = time.time() - start
            if elapsed > timeout:
                break
            if elapsed > soft_timeout:
                self.c.put("/control/csterm/%s" % self.s_id, self._k('\x03'))
                rp = self.c.get("/control/csterm/%s" % self.s_id)
                r += rp['k']
                soft_timeout = sys.maxsize

        # remove the prompt and any terminal escape sequences
        if clean:
            r = re.sub(r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])','', r)
            r = r.split('\n')
            prompt = r[-1]
            r = [l for l in r if not l.startswith(prompt)]
            r = "\n".join(r)

        return r

    def interactive(self):
        initial = self._k("")
        print(f"Connecting (ctrl+d to quit)...")
        self.c.put("/control/csterm/%s" % self.s_id, initial)
        r = self.c.get("/control/csterm/%s" % self.s_id)

        term = Terminal()

        with term.cbreak():
            print(r['k'], end='', flush=True)
            interrupt = False
            while True:
                kill = False

                c = ""
                try:
                    while True:
                        if interrupt:
                            c = '\x03'
                            interrupt = False
                            break
                        i = term.inkey(timeout=0.01)
                        if '\x04' in i:
                            kill = True
                            break
                        if not i:
                            break
                        c += i
                    if kill:
                        break
                    self.c.put("/control/csterm/%s" % self.s_id, self._k(c))
                    r = self.c.get("/control/csterm/%s" % self.s_id)
                    if r['k']:
                        print(r['k'], end='', flush=True)
                except KeyboardInterrupt:
                    interrupt = True
        print("\nExiting...")

    def _k(self, v):
        r = {"k": v}
        if self.user:
            r["u"] = self.user
        return r


if __name__ == '__main__':
    from csclient import EventingCSClient

    c = EventingCSClient('cli_sample')
    ct = CSTerm(c, user="admin")

    if len(sys.argv) == 1:
       ct.interactive()
    else:
       print(ct.exec(" ".join(sys.argv[1:])))
