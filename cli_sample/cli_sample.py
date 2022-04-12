# cli - execute CLI command and return output

from csclient import EventingCSClient


def cli(username, password, cmd):
    """
    :param username: string
        username for SSH login
    :param password: string
        user password for SSH login
    :param cmd: string
        CLI command to execute
        Example: "sms 2081234567 'hello world' int1"
        Example: "arpdump"
    :return: string
        Text output returned from CLI command
    """
    import cppxssh

    ssh_tunnel = cppxssh.cppxssh()
    ssh_tunnel.login("localhost", username, password, auto_prompt_reset=False)
    ssh_tunnel.PROMPT = "\[[0-9A-Za-z_]+@.+\]\$ "
    ssh_tunnel.sendline(cmd)
    ssh_tunnel.prompt()
    output = ssh_tunnel.before.decode()
    del ssh_tunnel
    try:
        # try to remove the command echo
        return output.split(cmd + "\r\n")[1]
    except IndexError:
        # for some reason we failed to remove so return original
        return output


cp = EventingCSClient("cli_sample")
cp.log("Starting...")
cp.log("Output:\n" + cli("admin", "11", "arpdump"))
