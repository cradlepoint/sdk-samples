# Ericsson Router SDK Application
"""rtk_provisioner - Configure NCOS RTK/NTRIP for a corrections service.

A generic RTK/NTRIP provisioner. The corrections provider is detected from
SDK appdata: whichever provider's detection field is present selects it. Today
'p1_token' selects Point One Navigation; other providers can be added under
providers/ without touching this core.

Configuration is a reloadable state, not a startup gate: a supervisor loop
re-reads appdata every CONFIG_POLL_INTERVAL seconds, so settings added, edited
or cleared while the app is running are picked up and re-applied without
restarting the app or rebooting the router.

Flow (re-run whenever the configuration changes):
  1. Read SDK appdata and detect the provider from its fields.
  2. Ask the provider to register this router and return NTRIP credentials.
     The device label is the router hostname; hardware identity is the router
     MAC, so a rename is tracked in place rather than orphaning the device.
  3. Enable GPS if it is off, write config/system/rtk/ntrip, then set
     config/system/rtk/enabled = true.

This core never touches a provider's account; a provider never touches router
config. GPS is required because the NTRIP client reports its position to the
caster as GGA sentences, so corrections cannot flow without it.
"""

import json
import time

import cp

import providers
from providers import ProviderError

NTRIP_CONFIG_PATH = 'config/system/rtk/ntrip'
RTK_ENABLED_PATH = 'config/system/rtk/enabled'

# The NTRIP client reports its position upstream to the caster as GGA
# sentences, so GPS has to be on for corrections to work.
GPS_ENABLED_PATH = 'config/system/gps/enabled'

# How often log_rtk_status() reports the RTK/NTRIP state once the router has
# been provisioned. This is a logging cadence only - the supervisor loop runs
# on CONFIG_POLL_INTERVAL.
STATUS_INTERVAL = 300

# Supervisor loop timings. Configuration is re-read every pass, so a change
# to appdata takes effect without restarting the app.
CONFIG_POLL_INTERVAL = 15    # seconds between appdata polls
WAIT_LOG_INTERVAL = 300      # re-log "waiting for config" at most this often
PROVISION_BACKOFF_START = 60   # first retry delay after a failed attempt
PROVISION_BACKOFF_MAX = 900    # retry delay ceiling
WAN_WAIT_TIMEOUT = 300       # one-shot WAN wait at startup only

# Supervisor states.
STATE_WAITING = 'waiting'      # no provider detected, or a field is missing
STATE_RETRYING = 'retrying'    # config is present, provisioning failed
STATE_READY = 'ready'          # config applied to the router

# NCOS caps these config fields (see: inspect config/system/rtk/ntrip).
MAX_MOUNTPOINT_LEN = 64
MAX_CREDENTIAL_LEN = 32


# ---------------------------------------------------------------------------
# Appdata snapshot and helpers
# ---------------------------------------------------------------------------

def read_appdata_snapshot():
    """Read all appdata once and return {lowercased name: value}.

    Change detection is polling, not cp.register(): appdata entries are
    addressed by an '_id_' UUID that changes whenever a field is deleted and
    recreated, so there is no stable per-field path to register on, and
    cp.register() is a no-op off-router. One read of this single small path
    per poll is cheap, so polling is the only code path.

    Returns:
        dict: {name.lower(): value}, or None if the read failed. None means
            "unknown", not "empty" - the caller must not read a failed poll
            as cleared configuration.
    """
    try:
        entries = cp.get('config/system/sdk/appdata')
    except Exception as err:
        cp.log('Could not read config/system/sdk/appdata: {}'.format(err))
        return None
    if entries is None:
        cp.log('config/system/sdk/appdata read returned nothing')
        return None
    if not isinstance(entries, list):
        cp.log('config/system/sdk/appdata is {!r}, expected a list'.format(
            type(entries).__name__))
        return None

    snapshot = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        if not name:
            continue
        snapshot[str(name).lower()] = entry.get('value')
    return snapshot


class AppdataHelpers(object):
    """String/int/bool resolvers passed to a provider's read_config().

    Defaults live in code and are never written back to appdata - that would
    override group configs pushed from NetCloud Manager.
    """

    def string(self, snapshot, name, default=None):
        """Resolve one appdata field as a string."""
        value = snapshot.get(name.lower())
        if value is None:
            return default
        value = str(value).strip()
        if not value:
            return default
        return value

    def boolean(self, snapshot, name, default):
        """Resolve a boolean appdata field."""
        value = self.string(snapshot, name)
        if value is None:
            return default
        return value.lower() in ('1', 'true', 'yes', 'on', 'enabled')

    def integer(self, snapshot, name, default):
        """Resolve an integer appdata field."""
        value = self.string(snapshot, name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            cp.log('WARNING: appdata "{}" is not an integer ("{}"), using {}'
                   .format(name, value, default))
            return default


HELPERS = AppdataHelpers()


def read_config():
    """Detect the provider and read the full configuration.

    Returns:
        dict: {
            'provider': Provider instance (or None if none detected),
            'settings': provider settings dict (or None),
            'hostname': router hostname,
        }
        or None if appdata could not be read (the caller skips the pass
        rather than treating the unknown state as cleared configuration).
    """
    snapshot = read_appdata_snapshot()
    if snapshot is None:
        return None

    provider = providers.detect_provider(snapshot)
    settings = None
    if provider is not None:
        settings = provider.read_config(snapshot, HELPERS)

    return {
        'provider': provider,
        'settings': settings,
        # The device label follows the router hostname, so a live rename has
        # to re-provision too.
        'hostname': cp.get_name(),
    }


def config_identity(config):
    """A comparable snapshot of config, for change detection.

    Returns a tuple of (provider name, sorted settings items, hostname) that
    changes whenever anything the provisioner consumes changes. The provider
    *instance* itself is not comparable across polls, so its name stands in.
    """
    if config is None:
        return None
    provider = config.get('provider')
    name = provider.NAME if provider is not None else None
    settings = config.get('settings') or {}
    try:
        items = tuple(sorted(settings.items()))
    except TypeError:
        items = tuple(sorted((k, str(v)) for k, v in settings.items()))
    return (name, items, config.get('hostname'))


def changed_fields(old_settings, new_settings):
    """Return the sorted names of settings whose values differ.

    Names only, never values: a setting can hold a secret.
    """
    old_settings = old_settings or {}
    new_settings = new_settings or {}
    names = set(old_settings.keys()) | set(new_settings.keys())
    return sorted(n for n in names if old_settings.get(n) != new_settings.get(n))


def missing_required(config):
    """Return human-readable names of what is needed but not present.

    Covers both "no provider detected" and "provider detected but a required
    field is empty".
    """
    missing = []
    if not config.get('hostname'):
        missing.append('config/system/system_id (router hostname)')

    provider = config.get('provider')
    if provider is None:
        fields = providers.detect_fields()
        missing.append('a provider detection field (one of: {})'.format(
            ', '.join('"{}"'.format(f) for f in fields)))
        return missing

    settings = config.get('settings') or {}
    for field in provider.required_fields():
        # read_config stores detection/required fields under their own short
        # keys; fall back to presence by the appdata name when not mapped.
        if not _required_present(settings, field):
            missing.append('appdata "{}"'.format(field))
    return missing


def _required_present(settings, appdata_field):
    """Best-effort check that a provider's required field has a value.

    Providers map appdata into short keys of their own choosing, so this
    checks the common cases: a key equal to the appdata field, and the
    'token' convention used by the Point One provider.
    """
    candidates = [appdata_field, appdata_field.lower()]
    if appdata_field.endswith('_token'):
        candidates.append('token')
    for key in candidates:
        if settings.get(key):
            return True
    return False


# ---------------------------------------------------------------------------
# Router configuration
# ---------------------------------------------------------------------------

def rtk_supported():
    """Check whether this router model has the RTK config tree.

    Models without RTK support have no 'rtk' key under config/system at all,
    and config/system/rtk reads back as None.

    Returns:
        bool: True if config/system/rtk exists.
    """
    try:
        return cp.get('config/system/rtk') is not None
    except Exception as err:
        cp.log('Could not read config/system/rtk: {}'.format(err))
        return False


def ensure_gps_enabled():
    """Turn GPS on if it is not already on.

    The NTRIP client sends its position to the caster as GGA sentences, so
    without GPS the service cannot deliver corrections. Already-enabled GPS
    is left untouched rather than rewritten.

    Returns:
        bool: True if GPS is enabled (or was already).
    """
    try:
        enabled = cp.get(GPS_ENABLED_PATH)
    except Exception as err:
        cp.log('ERROR: could not read {}: {}'.format(GPS_ENABLED_PATH, err))
        return False

    if enabled is True:
        cp.log('GPS is already enabled')
        return True

    if enabled is None:
        cp.log('ERROR: {} does not exist on this router, so GPS cannot be '
               'enabled. NTRIP needs GPS to report position to the caster.'
               .format(GPS_ENABLED_PATH))
        return False

    cp.log('GPS is disabled - enabling it')
    result = cp.put(GPS_ENABLED_PATH, True)
    if not _put_succeeded(result):
        cp.log('ERROR: could not set {} -> {}'.format(
            GPS_ENABLED_PATH, json.dumps(result)))
        return False

    try:
        enabled = cp.get(GPS_ENABLED_PATH)
    except Exception as err:
        cp.log('ERROR: could not read back {}: {}'.format(
            GPS_ENABLED_PATH, err))
        return False
    if enabled is not True:
        cp.log('ERROR: {} reads back as {} after the write, expected True'
               .format(GPS_ENABLED_PATH, enabled))
        return False
    cp.log('GPS enabled and verified')
    return True


def build_ntrip_config(result):
    """Turn a provider NtripResult into the config/system/rtk/ntrip struct.

    Args:
        result: NtripResult from a provider.

    Returns:
        dict: Values for config/system/rtk/ntrip.

    Raises:
        ProviderError: If a value exceeds an NCOS length limit or a required
            field is empty.
    """
    login = result.username
    password = result.password
    if not login or not password:
        raise ProviderError('provider returned no NTRIP credentials '
                            '(login/password empty)')

    host = result.host
    port = result.port
    mount = result.mountpoint
    if not host or not port or not mount:
        raise ProviderError('provider returned an incomplete caster: '
                            'host={!r} port={!r} mountpoint={!r}'.format(
                                host, port, mount))

    if len(str(login)) > MAX_CREDENTIAL_LEN:
        raise ProviderError('NTRIP username is {} chars, NCOS allows {}'.format(
            len(str(login)), MAX_CREDENTIAL_LEN))
    if len(str(password)) > MAX_CREDENTIAL_LEN:
        raise ProviderError('NTRIP password is {} chars, NCOS allows {}'.format(
            len(str(password)), MAX_CREDENTIAL_LEN))
    if len(str(mount)) > MAX_MOUNTPOINT_LEN:
        raise ProviderError('NTRIP mountpoint is {} chars, NCOS allows {}'
                            .format(len(str(mount)), MAX_MOUNTPOINT_LEN))

    return {
        'host': str(host),
        'port': int(port),
        'mountpoint': str(mount),
        'username': str(login),
        'password': str(password),
    }


def apply_router_config(ntrip_config):
    """Enable GPS, write the NTRIP settings, and enable RTK.

    The whole NTRIP struct goes in a single PUT: NCOS validates a config
    struct as a unit, so a leaf-by-leaf write can be rejected partway
    through and leave the config half-applied.

    Every write is verified by reading the value back. The PUT response alone
    is not trusted: an unsupported path can return an 'ok' envelope while the
    router logs an unhandled error and applies nothing.

    Returns:
        bool: True if GPS, the NTRIP write, and the RTK enable were verified.
    """
    # GPS first: it is a prerequisite for the NTRIP client, so there is no
    # point enabling RTK without it.
    if not ensure_gps_enabled():
        return False

    safe = dict(ntrip_config)
    safe['password'] = '***'
    cp.log('Writing {} -> {}'.format(NTRIP_CONFIG_PATH, json.dumps(safe)))

    result = cp.put(NTRIP_CONFIG_PATH, ntrip_config)
    if not _put_succeeded(result):
        cp.log('ERROR: could not write {} -> {}'.format(
            NTRIP_CONFIG_PATH, json.dumps(result)))
        return False

    if not _verify_ntrip_config(ntrip_config):
        return False
    cp.log('NTRIP settings applied and verified')

    result = cp.put(RTK_ENABLED_PATH, True)
    if not _put_succeeded(result):
        cp.log('ERROR: could not set {} -> {}'.format(
            RTK_ENABLED_PATH, json.dumps(result)))
        return False

    try:
        enabled = cp.get(RTK_ENABLED_PATH)
    except Exception as err:
        cp.log('ERROR: could not read back {}: {}'.format(
            RTK_ENABLED_PATH, err))
        return False
    if enabled is not True:
        cp.log('ERROR: {} reads back as {} after the write, expected True'
               .format(RTK_ENABLED_PATH, enabled))
        return False
    cp.log('RTK enabled and verified')
    return True


def _verify_ntrip_config(expected):
    """Read config/system/rtk/ntrip back and compare it to what we wrote.

    The password is skipped: NCOS stores it encrypted and never returns the
    plaintext.

    Returns:
        bool: True if every comparable field matches.
    """
    try:
        current = cp.get(NTRIP_CONFIG_PATH)
    except Exception as err:
        cp.log('ERROR: could not read back {}: {}'.format(
            NTRIP_CONFIG_PATH, err))
        return False

    if not isinstance(current, dict):
        cp.log('ERROR: {} reads back as {} after the write - nothing was '
               'applied'.format(NTRIP_CONFIG_PATH, current))
        return False

    for field in ('host', 'port', 'mountpoint', 'username'):
        if current.get(field) != expected[field]:
            cp.log('ERROR: {}/{} reads back as {!r}, expected {!r}'.format(
                NTRIP_CONFIG_PATH, field, current.get(field),
                expected[field]))
            return False

    if not current.get('password'):
        cp.log('ERROR: {}/password is empty after the write'.format(
            NTRIP_CONFIG_PATH))
        return False
    return True


def _put_succeeded(result):
    """Interpret a cp.put() result.

    cp.put returns the raw transport envelope, which differs by environment:
      - on-router socket: {'status': 'ok'|'error'|'timeout', 'data': ...}
      - local REST:       {'success': True|False, 'data': ...}
    """
    if result is None:
        return False
    if not isinstance(result, dict):
        return True

    if result.get('success') is False:
        return False
    if str(result.get('status', 'ok')).lower() in ('error', 'timeout'):
        return False
    if 'exception' in result or 'reason' in result:
        return False

    data = result.get('data')
    if isinstance(data, dict) and ('exception' in data or 'reason' in data):
        return False
    return True


def log_rtk_status():
    """Log the router's RTK/NTRIP status, if the model reports it."""
    try:
        status = cp.get('status/rtk')
        if not status:
            cp.log('status/rtk is empty - this model does not report RTK status')
            return

        source = status.get('correction_source') or {}
        corrections = status.get('corrections') or {}
        # Current firmware reports correction_source / corrections. Older
        # builds reported an ntrip struct and rtcm_total instead, so fall
        # back to those keys when they are the ones present.
        ntrip_status = status.get('ntrip') or {}
        if source or corrections:
            cp.log('RTK status: enabled={} source={} state={} frames_total={} '
                   'dropped={} queued={}'.format(
                       status.get('enabled'), source.get('type'),
                       source.get('state'), corrections.get('frames_total'),
                       corrections.get('frames_dropped'),
                       corrections.get('frames_queued')))
            if source.get('error'):
                cp.log('RTK correction source error: {}'.format(
                    source.get('error')))
        else:
            cp.log('RTK status: enabled={} connected={} quality={} '
                   'rtcm_total={}'.format(
                       status.get('enabled'), ntrip_status.get('connected'),
                       ntrip_status.get('rtk_quality'),
                       status.get('rtcm_total')))
        error_detail = ntrip_status.get('error_detail')
        if error_detail:
            cp.log('RTK NTRIP error detail: {}'.format(error_detail))
    except Exception as err:
        cp.log('Could not read status/rtk: {}'.format(err))


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------

def provision(config):
    """Run the full provisioning flow once against the given configuration.

    Args:
        config: The dict from read_config(). A provider is present and its
            required fields are known to be set - the supervisor checks that.

    Returns:
        True if the router was configured and RTK enabled, the string
        'unsupported' if this router model has no RTK support (retrying
        sooner will not help), or False on any other failure.
    """
    provider = config['provider']
    settings = config['settings']
    hostname = config['hostname']
    cp.log('Provider: {}'.format(provider.NAME))
    cp.log('Router hostname: {}'.format(hostname))

    # Gate before touching the provider account: creating resources for a
    # router that cannot use them would leave stray billable resources behind.
    if not rtk_supported():
        cp.log('ERROR: this router model has no config/system/rtk key, so it '
               'does not support RTK/NTRIP. RTK requires a product with RTK '
               'support (for example an R2400). No provider resources were '
               'created.')
        return 'unsupported'

    mac = cp.get_mac()
    if not mac:
        cp.log('ERROR: could not read the router MAC address '
               '(status/product_info/mac0)')
        return False
    mac = mac.replace(':', '').lower()
    cp.log('Router MAC: {}'.format(mac))

    # The provider registers the router and hands back NTRIP credentials.
    result = provider.provision(settings, hostname, mac)

    ntrip_config = build_ntrip_config(result)
    cp.log('NTRIP config resolved: host={} port={} mountpoint={} username={}'
           .format(ntrip_config['host'], ntrip_config['port'],
                   ntrip_config['mountpoint'], ntrip_config['username']))

    if not apply_router_config(ntrip_config):
        return False

    cp.log('RTK/NTRIP provisioning complete via {}'.format(provider.NAME))
    time.sleep(5)
    log_rtk_status()
    return True


def wan_connected():
    """Cheap non-blocking WAN readiness check.

    cp.wait_for_wan_connection() blocks in its own poll loop, which would
    stall the config poll, so the supervisor reads the single state value
    instead.
    """
    try:
        return cp.get('status/wan/connection_state') == 'connected'
    except Exception as err:
        cp.log('Could not read status/wan/connection_state: {}'.format(err))
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Supervise configuration and keep the router provisioned.

    Configuration is a reloadable state, not a startup gate: every pass
    re-reads appdata, re-detects the provider, compares against what was last
    applied, and re-provisions when it differs. Missing configuration parks
    the app in this same loop, so a token added at runtime is picked up within
    CONFIG_POLL_INTERVAL with no app restart and no reboot.

    This function never returns. package.ini sets restart = true, so a
    process that exits is relaunched immediately - every error path stays
    inside the loop.
    """
    cp.log('Starting rtk_provisioner...')
    cp.log('Known providers: {}'.format(', '.join(providers.provider_names())))

    # One blocking wait at startup so a cold boot provisions as soon as the
    # WAN comes up. A timeout is not fatal: the loop re-checks connectivity
    # on every pass.
    if not cp.wait_for_wan_connection(timeout=WAN_WAIT_TIMEOUT):
        cp.log('No WAN connection after {}s; continuing to poll for '
               'connectivity and configuration'.format(WAN_WAIT_TIMEOUT))

    state = None          # STATE_*, None until the first pass decides
    last_identity = None  # comparable identity of the last config read
    last_settings = None  # last settings dict, for change-field naming
    applied = None        # identity last provisioned successfully
    last_wait_log = 0.0
    last_wan_log = 0.0
    last_status_log = 0.0
    next_attempt = 0.0
    backoff = PROVISION_BACKOFF_START

    while True:
        try:
            now = time.monotonic()
            config = read_config()
            missing = missing_required(config) if config is not None else None
            identity = config_identity(config)
            settings = config.get('settings') if config is not None else None

            if config is None:
                # Unknown, not empty. A failed read must never be mistaken
                # for cleared configuration, so applied state is left alone.
                cp.log('Skipping this pass - configuration could not be read')

            elif missing:
                if applied is not None:
                    cp.log('Required configuration was cleared. The router '
                           'keeps its current RTK/NTRIP config; it is left '
                           'alone rather than torn down as a side effect of '
                           'an appdata edit.')
                    applied = None
                if state != STATE_WAITING or \
                        now - last_wait_log >= WAIT_LOG_INTERVAL:
                    cp.log('Waiting for configuration: {} not set. Add it '
                           'under config/system/sdk/appdata - this app picks '
                           'it up within {}s, no restart needed.'.format(
                               ' and '.join(missing), CONFIG_POLL_INTERVAL))
                    last_wait_log = now
                state = STATE_WAITING
                last_identity = identity
                last_settings = settings
                backoff = PROVISION_BACKOFF_START
                next_attempt = 0.0

            else:
                if last_identity is None or identity != last_identity:
                    if last_identity is None:
                        cp.log('Configuration read: provider {}'.format(
                            config['provider'].NAME))
                    else:
                        # Field names only - a value may be a secret.
                        names = changed_fields(last_settings, settings)
                        cp.log('Configuration changed: {} - re-applying'
                               .format(', '.join(names) or 'provider'))
                    last_identity = identity
                    last_settings = settings
                    applied = None
                    backoff = PROVISION_BACKOFF_START
                    next_attempt = 0.0

                if applied is None and now >= next_attempt:
                    if not wan_connected():
                        if now - last_wan_log >= WAIT_LOG_INTERVAL:
                            cp.log('No WAN connection - cannot reach the '
                                   'provider API; still polling')
                            last_wan_log = now
                    else:
                        detail = ''
                        try:
                            result = provision(config)
                        except ProviderError as err:
                            detail = str(err)
                            cp.log('ERROR: {}'.format(detail))
                            result = False
                        except Exception as err:
                            detail = 'unexpected failure: {}'.format(err)
                            cp.log('ERROR: {}'.format(detail))
                            result = False

                        if result is True:
                            applied = identity
                            last_status_log = now
                            backoff = PROVISION_BACKOFF_START
                            if state != STATE_READY:
                                cp.log('RTK/NTRIP corrections configured '
                                       'and enabled')
                            state = STATE_READY
                        elif result == 'unsupported':
                            if state != STATE_RETRYING:
                                cp.log('RTK is unsupported on this model - '
                                       're-checking every {}s in case the '
                                       'config changes'.format(
                                           PROVISION_BACKOFF_MAX))
                            state = STATE_RETRYING
                            next_attempt = now + PROVISION_BACKOFF_MAX
                        else:
                            if state != STATE_RETRYING and detail:
                                cp.log('RTK/NTRIP provisioning failed: {}'
                                       .format(detail))
                            cp.log('Provisioning did not complete - retrying '
                                   'in {}s'.format(backoff))
                            state = STATE_RETRYING
                            next_attempt = now + backoff
                            backoff = min(backoff * 2, PROVISION_BACKOFF_MAX)

                elif applied is not None and \
                        now - last_status_log >= STATUS_INTERVAL:
                    log_rtk_status()
                    last_status_log = now

        except Exception as err:
            cp.log('ERROR: supervisor loop pass failed: {}'.format(err))

        # Exactly one sleep per pass, on every path: no branch can spin and
        # none can double-sleep.
        time.sleep(CONFIG_POLL_INTERVAL)


if __name__ == '__main__':
    main()
