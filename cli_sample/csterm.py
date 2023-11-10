import random
import time
import re


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
        timeout = self.timeout * (1 / self.INTERVAL)
        soft_timeout = self.soft_timeout * (1 / self.INTERVAL)

        k = iter(cmds)
        kp = next(k)
        r = ''
        while timeout > 0:

            self.c.put("/control/csterm/%s" % self.s_id, self._k(kp))
            rp = self.c.get("/control/csterm/%s" % self.s_id)

            r += rp['k']
            # the output generally will end with a prompt and no newline, so we can check for that
            # after we've sent all our commands
            if kp == "" and not r.endswith('\n'):
                break

            kp = next(k, None) or ""
            timeout-=1
            time.sleep(self.INTERVAL)
            if timeout < soft_timeout:
                self.c.put("/control/csterm/%s" % self.s_id, self._k('\x03'))
                rp = self.c.get("/control/csterm/%s" % self.s_id)
                r += rp['k']
                soft_timeout = 0

        # remove the prompt and any terminal escape sequences
        if clean:
            r = re.sub(r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])','', r)
            r = r.split('\n')
            prompt = r[-1]
            r = [l for l in r if not l.startswith(prompt)]
            r = "\n".join(r)

        return r

    def _k(self, v):
        r = {"k": v}
        if self.user:
            r["u"] = self.user
        return r

if __name__ == '__main__':
    import sys
    from csclient import EventingCSClient

    c = EventingCSClient('cli_sample')
    ct = CSTerm(c, user="admin")
    print(ct.exec(sys.argv[1:]))
