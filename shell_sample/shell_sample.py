# shell_sample - execute linux shell_sample command and return output

from csclient import EventingCSClient


def shell(cmd):
    """
    executes a linux shell command and returns the output
    :param cmd: string
        command to be executed. e.g. "ls -al"
    :return: string
        output of shell command
    """
    from subprocess import Popen, PIPE
    output = ''
    cmd = cmd.split(' ')
    tail = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    for line in iter(tail.stdout.readline, ''):
        if tail.returncode:
            break
        if line:
            output += line
    return output


cp = EventingCSClient('shell_sample')
cp.log('Starting...')
cp.log('Output:\n' + shell('ls -al'))
