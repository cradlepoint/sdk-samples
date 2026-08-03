#!/usr/bin/env python3
"""Set up the NCOS SDK development environment.

Does everything needed to go from a fresh clone to building and deploying
apps with Kiro:

  1. Checks the Python version
  2. Creates the .venv virtual environment
  3. Installs dependencies from requirements.txt
  4. Creates sdk_settings.ini from sdk_settings.ini.example if it is missing
     (the real file is git-ignored because it holds credentials)
  5. Prompts for your dev-mode router IP / username / password and writes
     them to sdk_settings.ini (easy to skip)
  6. Tests the router connection and confirms Developer Mode
  7. Points the IDE's Python interpreter at .venv

Works on Windows, macOS, and Linux. Uses only the standard library, so it
can run with the system Python before the venv exists.

Usage:
    python setup_env.py                 # Windows
    python3 setup_env.py                # macOS / Linux

    python3 setup_env.py --configure    # only edit router settings
    python3 setup_env.py --skip-router  # only build the venv
    python3 setup_env.py -y             # never prompt (CI / hooks)
    python3 setup_env.py --quiet        # only report problems / changes
    python3 setup_env.py --router-ip 192.168.0.1 --router-username admin \
        --router-password secret
"""

import sys

# Fail clearly if launched with Python 2 or a very old Python 3. Keep this
# block free of modern syntax so it can actually run on those versions.
if sys.version_info < (3, 7):
    sys.stderr.write('This script needs Python 3.9 or newer '
                     '(you ran {}).\n'.format(sys.version.split()[0]))
    sys.stderr.write('Download it from https://www.python.org/downloads/\n')
    sys.exit(1)

import argparse
import configparser
import json
import os
import shutil
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(REPO_ROOT, '.venv')
REQUIREMENTS_FILE = os.path.join(REPO_ROOT, 'requirements.txt')
SETTINGS_FILE = os.path.join(REPO_ROOT, 'sdk_settings.ini')
EXAMPLE_SETTINGS_FILE = SETTINGS_FILE + '.example'
VSCODE_SETTINGS = os.path.join(REPO_ROOT, '.vscode', 'settings.json')

MIN_PYTHON = (3, 9)
HARD_MIN_PYTHON = (3, 7)

# Import name for packages whose module name differs from the pip name.
IMPORT_NAMES = {
    'pyserial': 'serial',
}

# Passwords that mean "not configured yet" (see .kiro/steering/workflow.md).
PLACEHOLDER_PASSWORDS = ('', 'mypassword', 'your_password', 'password', 'changeme')

DEFAULT_SETTINGS = {
    'app_name': 'app_template',
    'dev_client_ip': '192.168.0.1',
    'dev_client_username': 'admin',
    'dev_client_password': 'mypassword',
}

# Runs inside the venv (it needs `requests`). Credentials come from the
# environment so they never appear in a command line or process list.
ROUTER_CHECK = r'''
import json, os, sys
try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    print('RESULT ' + json.dumps({'error': 'requests-missing'}))
    sys.exit(0)

ip = os.environ['CP_IP']
user = os.environ['CP_USER']
password = os.environ['CP_PASS']
result = {}

for scheme in ('https', 'http'):
    url = '{}://{}/api/status/system/sdk/mode'.format(scheme, ip)
    try:
        resp = requests.get(url, auth=(user, password), verify=False, timeout=8)
    except Exception as err:
        result['error'] = type(err).__name__
        continue
    result.pop('error', None)
    result['scheme'] = scheme
    result['status_code'] = resp.status_code
    if resp.status_code == 200:
        try:
            result['mode'] = resp.json().get('data')
        except Exception:
            result['mode'] = None
        try:
            info = requests.get('{}://{}/api/status/product_info'.format(scheme, ip),
                                auth=(user, password), verify=False, timeout=8)
            if info.status_code == 200:
                result['product'] = (info.json().get('data') or {}).get('product_name')
        except Exception:
            pass
        try:
            fw = requests.get('{}://{}/api/status/fw_info'.format(scheme, ip),
                              auth=(user, password), verify=False, timeout=8)
            if fw.status_code == 200:
                data = fw.json().get('data') or {}
                result['firmware'] = '{}.{}.{}'.format(data.get('major_version', '?'),
                                                       data.get('minor_version', '?'),
                                                       data.get('patch_version', '?'))
        except Exception:
            pass
    break

print('RESULT ' + json.dumps(result))
'''


# ---------------------------------------------------------------- output


class Out(object):
    """Console output that can be muted for hook/quiet runs."""

    def __init__(self, quiet):
        self.quiet = quiet

    def step(self, message):
        if not self.quiet:
            print('\n== {} =='.format(message))

    def say(self, message=''):
        if not self.quiet:
            print(message)

    def ok(self, message):
        self.say('   [ok] {}'.format(message))

    def change(self, message):
        # Something was actually modified — always worth reporting.
        print('   [ok] {}'.format(message))

    def warn(self, message):
        # Warnings are always shown, even in quiet mode.
        print('   [!] {}'.format(message))

    def fail(self, message):
        print('   [X] {}'.format(message))


def run(cmd, out, capture=False, env=None):
    """Run a command. Returns (returncode, output)."""
    merged_env = None
    if env:
        merged_env = os.environ.copy()
        merged_env.update(env)
    if capture:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              env=merged_env)
        text = (proc.stdout or b'').decode('utf-8', 'replace')
        return proc.returncode, text
    stdout = subprocess.DEVNULL if out.quiet else None
    proc = subprocess.run(cmd, stdout=stdout, stderr=subprocess.STDOUT, env=merged_env)
    return proc.returncode, ''


# ---------------------------------------------------------------- python


def check_python(out):
    version = sys.version_info
    label = '{}.{}.{}'.format(version[0], version[1], version[2])
    if version < HARD_MIN_PYTHON:
        out.fail('Python {} is too old. Install Python {}.{} or newer.'.format(
            label, MIN_PYTHON[0], MIN_PYTHON[1]))
        out.say('       https://www.python.org/downloads/')
        return False
    if version < MIN_PYTHON:
        out.warn('Python {} detected. {}.{}+ is recommended.'.format(
            label, MIN_PYTHON[0], MIN_PYTHON[1]))
        return True
    out.ok('Python {} ({})'.format(label, sys.executable))
    return True


# ------------------------------------------------------------------ venv


def venv_python():
    """Path to the venv interpreter, or None if the venv is not usable."""
    if os.name == 'nt':
        candidates = [os.path.join(VENV_DIR, 'Scripts', 'python.exe'),
                      os.path.join(VENV_DIR, 'Scripts', 'python')]
    else:
        candidates = [os.path.join(VENV_DIR, 'bin', 'python3'),
                      os.path.join(VENV_DIR, 'bin', 'python')]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def ensure_venv(out):
    """Create (or repair) .venv. Returns the venv interpreter path or None."""
    out.step('Virtual environment')
    existing = venv_python()

    if existing:
        code, _ = run([existing, '-c', 'import sys'], out, capture=True)
        if code == 0:
            code, text = run([existing, '-c',
                              'import sys; print("%d.%d.%d" % sys.version_info[:3])'],
                             out, capture=True)
            out.ok('.venv ready (Python {})'.format(text.strip() or 'unknown'))
            return existing
        out.warn('.venv is broken — rebuilding it')
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    out.say('   Creating .venv ...')
    code, text = run([sys.executable, '-m', 'venv', VENV_DIR], out, capture=True)
    if code != 0:
        out.fail('Could not create the virtual environment.')
        out.say(text.strip())
        if 'ensurepip' in text or 'python3-venv' in text:
            out.say('       On Debian/Ubuntu: sudo apt install python3-venv')
        return None

    created = venv_python()
    if not created:
        out.fail('Virtual environment created but no interpreter was found in .venv.')
        return None
    out.change('.venv created')
    return created


# ---------------------------------------------------------- dependencies


def required_imports():
    """Import names for everything in requirements.txt."""
    names = []
    if not os.path.isfile(REQUIREMENTS_FILE):
        return names
    with open(REQUIREMENTS_FILE, 'r') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            for separator in ('==', '>=', '<=', '~=', '>', '<', '[', ';'):
                line = line.split(separator)[0]
            package = line.strip()
            if package:
                names.append(IMPORT_NAMES.get(package.lower(), package.replace('-', '_')))
    return names


def ensure_dependencies(python_exe, out, force=False):
    """Install requirements.txt into the venv if anything is missing."""
    out.step('Dependencies')
    if not os.path.isfile(REQUIREMENTS_FILE):
        out.warn('No requirements.txt found — skipping dependency install.')
        return True

    imports = required_imports()
    check = 'import ' + ', '.join(imports) if imports else 'pass'

    if not force and imports:
        code, _ = run([python_exe, '-c', check], out, capture=True)
        if code == 0:
            out.ok('All dependencies present ({})'.format(', '.join(imports)))
            return True

    out.say('   Installing from requirements.txt ...')
    run([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip',
         '--disable-pip-version-check', '-q'], out, capture=out.quiet)
    code, text = run([python_exe, '-m', 'pip', 'install', '-r', REQUIREMENTS_FILE,
                      '--disable-pip-version-check'], out, capture=out.quiet)
    if code != 0:
        out.fail('pip install failed.')
        if text:
            out.say(text.strip()[-2000:])
        out.say('       Check your internet connection or proxy settings and re-run.')
        return False

    if imports:
        code, text = run([python_exe, '-c', check], out, capture=True)
        if code != 0:
            out.fail('Dependencies installed but not importable:')
            out.say(text.strip())
            return False
    out.change('Dependencies installed')
    return True


# -------------------------------------------------------------- settings


def ensure_settings_file(out):
    """Create sdk_settings.ini from the example if it does not exist.

    The file is git-ignored because it holds router credentials, so a fresh
    clone will not have one.
    """
    if os.path.isfile(SETTINGS_FILE):
        return True

    contents = ('[sdk]\n'
                'app_name={app_name}\n'
                'dev_client_ip={dev_client_ip}\n'
                'dev_client_username={dev_client_username}\n'
                'dev_client_password={dev_client_password}\n').format(**DEFAULT_SETTINGS)
    source = 'built-in defaults'
    if os.path.isfile(EXAMPLE_SETTINGS_FILE):
        try:
            with open(EXAMPLE_SETTINGS_FILE, 'r') as handle:
                contents = handle.read()
            source = 'sdk_settings.ini.example'
        except OSError:
            pass

    try:
        with open(SETTINGS_FILE, 'w') as handle:
            handle.write(contents)
    except OSError as err:
        out.fail('Could not create sdk_settings.ini: {}'.format(err))
        return False
    out.change('Created sdk_settings.ini from {} (git-ignored)'.format(source))
    return True


def read_settings():
    """Current sdk_settings.ini values merged over the defaults."""
    values = dict(DEFAULT_SETTINGS)
    parser = configparser.ConfigParser()
    try:
        parser.read(SETTINGS_FILE)
    except configparser.Error:
        return values
    for section in parser.sections():
        if section.lower() == 'sdk':
            for key in DEFAULT_SETTINGS:
                if key in parser[section]:
                    values[key] = parser[section][key]
    return values


def write_settings(values, out):
    """Write values into the [sdk] section, preserving any extra keys."""
    parser = configparser.ConfigParser()
    parser.read(SETTINGS_FILE)
    if not parser.has_section('sdk'):
        parser.add_section('sdk')
    for key, value in values.items():
        parser.set('sdk', key, value)
    try:
        import io
        buffer = io.StringIO()
        parser.write(buffer, space_around_delimiters=False)
        text = buffer.getvalue().rstrip('\n') + '\n'
        with open(SETTINGS_FILE, 'w') as handle:
            handle.write(text)
    except OSError as err:
        out.fail('Could not write sdk_settings.ini: {}'.format(err))
        return
    out.change('Saved to sdk_settings.ini')


def is_configured(values):
    """True when the router settings look like real values, not the shipped ones."""
    return bool(values.get('dev_client_ip')
                and values.get('dev_client_username')
                and values.get('dev_client_password') not in PLACEHOLDER_PASSWORDS)


def ask(prompt, default=''):
    """Prompt with a default. Returns the default when the user hits Enter."""
    label = '   {} [{}]: '.format(prompt, default) if default else '   {}: '.format(prompt)
    try:
        answer = input(label).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if answer.lower() in ('skip', 'q', 'quit'):
        return None
    return answer or default


def ask_password(default_present):
    hint = 'press Enter to keep the current one' if default_present else 'required'
    label = '   Router password ({}): '.format(hint)
    try:
        import getpass
        return getpass.getpass(label)
    except (ImportError, EOFError, KeyboardInterrupt):
        print()
        return None
    except Exception:
        # Some terminals cannot hide input — fall back to a visible prompt.
        try:
            return input(label)
        except (EOFError, KeyboardInterrupt):
            print()
            return None


def yes_no(prompt, default=True):
    suffix = '[Y/n]' if default else '[y/N]'
    try:
        answer = input('   {} {}: '.format(prompt, suffix)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer.startswith('y')


def configure_router(args, out, interactive):
    """Collect router settings. Returns (values, changed)."""
    out.step('Dev-mode router connection')
    current = read_settings()

    # Flags win, and never prompt when they are used.
    from_flags = {}
    if args.router_ip:
        from_flags['dev_client_ip'] = args.router_ip
    if args.router_username:
        from_flags['dev_client_username'] = args.router_username
    if args.router_password:
        from_flags['dev_client_password'] = args.router_password
    if args.app_name:
        from_flags['app_name'] = args.app_name
    if from_flags:
        current.update(from_flags)
        write_settings(current, out)
        return current, True

    if not interactive:
        if is_configured(current):
            out.ok('Using existing settings ({}@{})'.format(
                current['dev_client_username'], current['dev_client_ip']))
        else:
            out.warn('sdk_settings.ini still has placeholder values. '
                     'Run "python setup_env.py --configure" to set them.')
        return current, False

    out.say('   Kiro deploys apps to a router that has Developer Mode enabled')
    out.say('   in NetCloud Manager (Tools > Developer Mode Devices).')
    out.say('   Current: ip={} user={} password={}'.format(
        current['dev_client_ip'], current['dev_client_username'],
        '<set>' if current['dev_client_password'] not in PLACEHOLDER_PASSWORDS else '<not set>'))
    out.say()
    out.say('   To skip: answer "n" below, or type "skip" at any prompt.')
    out.say('   You can always edit sdk_settings.ini later, or re-run:')
    out.say('     python setup_env.py --configure')
    out.say()

    if not yes_no('Enter router IP, username, and password now?', default=True):
        out.say('   Skipped. sdk_settings.ini left unchanged.')
        return current, False

    ip = ask('Router IP address', current['dev_client_ip'])
    if ip is None:
        out.say('   Skipped. sdk_settings.ini left unchanged.')
        return current, False

    username = ask('Router username', current['dev_client_username'] or 'admin')
    if username is None:
        out.say('   Skipped. sdk_settings.ini left unchanged.')
        return current, False

    has_password = current['dev_client_password'] not in PLACEHOLDER_PASSWORDS
    password = ask_password(has_password)
    if password is None:
        out.say('   Skipped. sdk_settings.ini left unchanged.')
        return current, False
    password = password.strip()
    if password.lower() in ('skip', 'q', 'quit'):
        out.say('   Skipped. sdk_settings.ini left unchanged.')
        return current, False
    if not password:
        if not has_password:
            out.warn('No password entered — deploys will fail until you set one.')
            password = current['dev_client_password']
        else:
            password = current['dev_client_password']

    values = dict(current)
    values['dev_client_ip'] = ip
    values['dev_client_username'] = username
    values['dev_client_password'] = password
    write_settings(values, out)
    return values, True


def test_router(python_exe, values, out):
    """Check the router is reachable, credentials work, and Dev Mode is on."""
    out.step('Router check')
    if not is_configured(values):
        out.say('   Skipped — router settings are not configured yet.')
        return

    ip = values['dev_client_ip']
    out.say('   Contacting {} ...'.format(ip))
    code, text = run([python_exe, '-c', ROUTER_CHECK], out, capture=True,
                     env={'CP_IP': ip,
                          'CP_USER': values['dev_client_username'],
                          'CP_PASS': values['dev_client_password']})
    result = {}
    for line in text.splitlines():
        if line.startswith('RESULT '):
            try:
                result = json.loads(line[len('RESULT '):])
            except ValueError:
                result = {}
    if code != 0 and not result:
        out.warn('Could not run the router check.')
        return

    if result.get('error') == 'requests-missing':
        out.warn('The "requests" package is missing from .venv — skipping check.')
        return
    if result.get('error') or not result.get('status_code'):
        out.warn('No response from {}. Check that you are on the same network '
                 'and the IP is correct.'.format(ip))
        out.say('       This does not block setup — fix it later and re-run.')
        return
    if result['status_code'] in (401, 403):
        out.warn('{} answered but rejected the credentials (HTTP {}).'.format(
            ip, result['status_code']))
        out.say('       Re-run: python setup_env.py --configure')
        return
    if result['status_code'] != 200:
        out.warn('{} returned HTTP {} for the SDK mode check.'.format(
            ip, result['status_code']))
        return

    product = result.get('product')
    if product:
        out.ok('Connected to {} (NCOS {})'.format(product, result.get('firmware', '?')))
    else:
        out.ok('Connected to {}'.format(ip))

    mode = result.get('mode')
    if mode == 'devmode':
        out.ok('Developer Mode is enabled — ready to deploy')
    elif mode == 'standard':
        out.warn('Developer Mode is NOT enabled on this router.')
        out.say('       Enable it in NetCloud Manager: Tools > Developer Mode Devices.')
        out.say('       It cannot be enabled from the router UI.')
    else:
        out.warn('Unexpected SDK mode: {}'.format(mode))


# -------------------------------------------------------------- IDE hook


def configure_ide(python_exe, out):
    """Point the IDE's Python interpreter at .venv without clobbering settings."""
    relative = os.path.relpath(python_exe, REPO_ROOT).replace(os.sep, '/')
    settings = {}
    if os.path.isfile(VSCODE_SETTINGS):
        try:
            with open(VSCODE_SETTINGS, 'r') as handle:
                settings = json.load(handle)
        except (ValueError, OSError):
            # Comments or unreadable file — leave it alone.
            return
    if settings.get('python.defaultInterpreterPath') == '${workspaceFolder}/' + relative:
        return
    settings['python.defaultInterpreterPath'] = '${workspaceFolder}/' + relative
    try:
        os.makedirs(os.path.dirname(VSCODE_SETTINGS), exist_ok=True)
        with open(VSCODE_SETTINGS, 'w') as handle:
            json.dump(settings, handle, indent=4)
            handle.write('\n')
    except OSError:
        return
    out.change('IDE Python interpreter set to .venv')


def check_git_tracking(out):
    """sdk_settings.ini should be untracked. Older clones still track it."""
    if not shutil.which('git'):
        return
    proc = subprocess.run(['git', 'ls-files', '-v', '--', 'sdk_settings.ini'],
                          cwd=REPO_ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
    listing = (proc.stdout or b'').decode('utf-8', 'replace').strip()
    if proc.returncode != 0 or not listing:
        return  # Not a git checkout, or already untracked. Nothing to do.

    steps = []
    if listing[0] == 'S' or listing[0].islower():
        # skip-worktree / assume-unchanged has to come off first.
        steps.append('git update-index --no-skip-worktree sdk_settings.ini')
    steps.append('git rm --cached sdk_settings.ini')

    if out.quiet:
        # Keep it to one actionable line for session-start hook runs.
        out.warn('sdk_settings.ini is still tracked by git (it holds credentials). '
                 'Untrack it: {}'.format(' && '.join(steps)))
        return

    out.say()
    out.warn('sdk_settings.ini is still tracked by git in this clone, so your '
             'credentials could be committed by mistake.')
    out.say('       It is git-ignored upstream now. To untrack your local copy:')
    for step in steps:
        out.say('         {}'.format(step))
    out.say('       Your file and its contents stay on disk.')


def print_next_steps(python_exe, values, out):
    relative = os.path.relpath(python_exe, REPO_ROOT).replace(os.sep, '/')
    activate = ('.venv\\Scripts\\activate' if os.name == 'nt'
                else 'source .venv/bin/activate')
    out.say()
    out.say('=' * 68)
    out.say('Setup complete.')
    out.say('=' * 68)
    out.say()
    out.say('You do not need to activate anything to chat with Kiro — just ask:')
    out.say()
    out.say('  "Build a web app that shows WAN status and signal for all modems"')
    out.say('  "Create an app that runs a speedtest every hour and logs to CSV"')
    out.say('  "Explain how #5GSpeed works"')
    out.say()
    if is_configured(values):
        out.say('Kiro creates the app, deploys it to {}, and checks the logs.'.format(
            values['dev_client_ip']))
    else:
        out.say('Kiro creates the app, deploys it to your router, and checks the logs.')
    out.say()
    out.say('To work in a terminal instead:')
    out.say('  {}'.format(activate))
    out.say('  {} make.py create my_app'.format(relative))
    out.say('  {} make.py deploy my_app'.format(relative))
    out.say()
    out.say('Full walkthrough: docs/SETUP.md')
    if not is_configured(values):
        out.say()
        out.say('Router not configured yet. When you are ready:')
        out.say('  python setup_env.py --configure')


# ------------------------------------------------------------------ main


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Set up the NCOS SDK development environment.')
    parser.add_argument('-y', '--non-interactive', action='store_true',
                        help='never prompt for input')
    parser.add_argument('--quiet', action='store_true',
                        help='only print problems and changes (implies -y)')
    parser.add_argument('--configure', action='store_true',
                        help='only configure the router settings')
    parser.add_argument('--skip-router', action='store_true',
                        help='do not touch router settings')
    parser.add_argument('--no-check', action='store_true',
                        help='skip the router connection test')
    parser.add_argument('--force-install', action='store_true',
                        help='reinstall requirements even if already present')
    parser.add_argument('--router-ip', help='dev-mode router IP address')
    parser.add_argument('--router-username', help='router username')
    parser.add_argument('--router-password', help='router password')
    parser.add_argument('--app-name', help='default app_name for make.py')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    out = Out(args.quiet)
    interactive = not (args.non_interactive or args.quiet)
    if interactive and not (sys.stdin and sys.stdin.isatty()):
        interactive = False

    if not args.quiet:
        print('=' * 68)
        print('Ericsson Cradlepoint NCOS SDK — environment setup')
        print('=' * 68)

    if not check_python(out):
        return 1

    python_exe = venv_python()
    if not args.configure:
        python_exe = ensure_venv(out)
        if not python_exe:
            return 1
        if not ensure_dependencies(python_exe, out, force=args.force_install):
            return 1
        configure_ide(python_exe, out)

    if not python_exe:
        out.fail('No .venv found. Run "python setup_env.py" first.')
        return 1

    if not ensure_settings_file(out):
        return 1

    values = read_settings()
    changed = False
    if not args.skip_router:
        values, changed = configure_router(args, out, interactive)

    # Skipped in quiet mode so the session-start hook stays fast.
    if not (args.skip_router or args.no_check or args.quiet):
        test_router(python_exe, values, out)

    check_git_tracking(out)

    print_next_steps(python_exe, values, out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
