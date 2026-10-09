# Ericsson Router SDK Application
"""pointonenav - Configure NCOS RTK/NTRIP for the Point One Navigation service.

Configuration is a reloadable state, not a startup gate: a supervisor loop
re-reads appdata every CONFIG_POLL_INTERVAL seconds, so a token that is added,
edited or cleared while the app is running is picked up and re-applied without
restarting the app or rebooting the router.

Flow (re-run whenever the configuration changes):
  1. Read the Point One personal access token from SDK appdata field 'p1_token'.
  2. Resolve this router's P1 device. The device label is the router hostname;
     hardware identity is the router MAC, held in a 'router_mac' tag:
       - a device tagged with this MAC is ours -> reuse it, create nothing
       - otherwise, a device this app created that is labelled with this
         hostname is older hardware for the same slot -> unlicense it, delete
         it, and create the replacement
       - otherwise -> first run on this router, create the device
  3. License the device unless it already carries one. An unassigned license
     from account inventory is reused before a new one is created.
  4. Read the NTRIP credentials back, enable GPS if it is off, write
     config/system/rtk/ntrip, then set config/system/rtk/enabled = true.

Because identity is a tag rather than the label, renaming the router updates
the P1 label in place instead of orphaning the device and its license.

The Point One GraphQL API returns casterUrl / mountPoint as null today, so the
caster host, port and mountpoint fall back to the documented True RTK values
and can be overridden through appdata.
"""

import json
import time
import urllib.error
import urllib.request

import cp

GRAPHQL_URL = 'https://graphql.pointonenav.com/graphql'
HTTP_TIMEOUT = 30

# Point One True RTK caster defaults. The API does not return these.
DEFAULT_CASTER_HOST = 'truertk.pointonenav.com'
DEFAULT_CASTER_PORT = 2101
DEFAULT_MOUNTPOINT = 'AUTO'

# Preferred license type, matched against LicenseType.description.
DEFAULT_LICENSE_MATCH = 'True RTK'

NTRIP_CONFIG_PATH = 'config/system/rtk/ntrip'
RTK_ENABLED_PATH = 'config/system/rtk/enabled'

# The NTRIP client reports its position upstream to the caster as GGA
# sentences (see the gga_rate setting), so GPS has to be on for corrections
# to work.
GPS_ENABLED_PATH = 'config/system/gps/enabled'

# The device label is the router hostname. Hardware identity lives in a tag,
# so renaming the router never loses track of the device.
TAG_APP = 'sdk_app'          # scopes lookups to devices this app created
TAG_MAC = 'router_mac'       # true hardware identity (full MAC, no colons)
APP_TAG_VALUE = 'pointonenav'

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
STATE_WAITING = 'waiting'      # a required setting is missing
STATE_RETRYING = 'retrying'    # config is present, provisioning failed
STATE_READY = 'ready'          # config applied to the router

# Page size for paginated list queries.
PAGE_SIZE = 100
MAX_PAGES = 50

# NCOS caps these config fields (see: inspect config/system/rtk/ntrip).
MAX_MOUNTPOINT_LEN = 64
MAX_CREDENTIAL_LEN = 32


class P1Error(Exception):
    """A Point One API call failed."""


# ---------------------------------------------------------------------------
# GraphQL transport
# ---------------------------------------------------------------------------

def graphql(token, query, variables=None, description=''):
    """POST a GraphQL document and return the 'data' object.

    Args:
        token: Point One personal access token.
        query: GraphQL query or mutation document.
        variables: Optional dict of GraphQL variables.
        description: Short label used in error messages and logs.

    Returns:
        dict: The 'data' object from the response.

    Raises:
        P1Error: On transport failure or any GraphQL 'errors' entry.
    """
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(token),
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode('utf-8')
    except urllib.error.HTTPError as err:
        detail = ''
        try:
            detail = err.read().decode('utf-8')[:300]
        except Exception:
            pass
        if err.code == 401:
            raise P1Error('{}: 401 unauthorized - check the p1_token appdata '
                          'value (expired or wrong token)'.format(description))
        raise P1Error('{}: HTTP {} {}'.format(description, err.code, detail))
    except urllib.error.URLError as err:
        raise P1Error('{}: could not reach {} ({})'.format(
            description, GRAPHQL_URL, err.reason))
    except Exception as err:
        raise P1Error('{}: {}'.format(description, err))

    try:
        parsed = json.loads(body)
    except ValueError as err:
        raise P1Error('{}: invalid JSON response ({})'.format(description, err))

    if parsed.get('errors'):
        messages = []
        for entry in parsed['errors']:
            if isinstance(entry, dict):
                messages.append(str(entry.get('message') or entry))
            else:
                messages.append(str(entry))
        raise P1Error('{}: {}'.format(description, '; '.join(messages)))

    data = parsed.get('data')
    if data is None:
        raise P1Error('{}: response contained no data'.format(description))
    return data


# ---------------------------------------------------------------------------
# Point One operations
# ---------------------------------------------------------------------------

# Shared selection set for every device query and mutation below.
#
# 'tags { key value }' MUST stay in this fragment. find_devices_by_tag() and
# resolve_device() re-check tags locally on the devices these queries return,
# and a GraphQL field that is not in the selection set comes back absent, not
# empty. Drop it and every device reads tags == None, so each local re-check
# matches nothing: the "find my existing device" lookup always misses and the
# app creates (and licenses) a duplicate of a device that already exists.
DEVICE_FIELDS = """
  id
  label
  createdAt
  tags { key value }
  services {
    rtk {
      enabled
      connectionStatus
      polarisKey
      ntrip { login password casterUrl mountPoint }
    }
  }
"""

FIND_DEVICES_QUERY = """
query FindDevices($filter: DeviceFilter, $offset: Int, $limit: Int) {
  myDevices(offset: $offset, limit: $limit, filter: $filter) {
    totalElements
    content { %s }
  }
}
""" % DEVICE_FIELDS

SET_TAG_MUTATION = """
mutation SetTag($input: TagInput!) {
  setDeviceTag(input: $input) { key value }
}
"""

UPDATE_DEVICE_MUTATION = """
mutation UpdateDevice($device: DeviceInput!) {
  updateDevice(device: $device) { id label updatedAt }
}
"""

GET_DEVICE_QUERY = """
query GetDevice($id: ID!) {
  device(id: $id) { %s }
}
""" % DEVICE_FIELDS

CREATE_DEVICE_MUTATION = """
mutation CreateDevice($device: DeviceInput!) {
  createDevice(device: $device) { %s }
}
""" % DEVICE_FIELDS

DELETE_DEVICES_MUTATION = """
mutation DeleteDevices($ids: [ID!]!) {
  deleteDevices(ids: $ids) { deletedCount success }
}
"""

LICENSES_QUERY = """
query Licenses($devices: [String!], $offset: Int, $limit: Int) {
  licenses(devices: $devices, offset: $offset, limit: $limit) {
    totalElements
    content {
      id
      number
      startDate
      endDate
      autoRenewal
      device { id label }
      currentLicenseType { id description termLength termPeriod }
    }
  }
}
"""

LICENSE_TYPES_QUERY = """
query LicenseTypes {
  licenseTypes { id name description termLength termPeriod
                 entitlements { id name } }
}
"""

APPLY_LICENSE_MUTATION = """
mutation ApplyLicense($licenseId: ID!, $deviceId: ID!) {
  applyLicenseToDevice(licenseId: $licenseId, deviceId: $deviceId) {
    id number startDate endDate device { id label }
    currentLicenseType { id description }
  }
}
"""

REMOVE_LICENSE_MUTATION = """
mutation RemoveLicense($licenseId: ID!, $deviceId: ID!) {
  removeLicenseFromDevice(licenseId: $licenseId, deviceId: $deviceId) {
    id number device { id label }
  }
}
"""

CREATE_LICENSES_FOR_DEVICES_MUTATION = """
mutation CreateLicenses($licenseType: ID!, $deviceIDs: [ID!]!,
                        $autoRenewal: Boolean) {
  createLicensesForDevices(licenseType: $licenseType, deviceIDs: $deviceIDs,
                           autoRenewal: $autoRenewal) {
    id number startDate endDate autoRenewal device { id label }
    currentLicenseType { id description }
  }
}
"""


def device_tag(device, key):
    """Read one tag value off a device, or None."""
    for tag in device.get('tags') or []:
        if tag.get('key') == key:
            return tag.get('value')
    return None


def _find_devices(token, device_filter, description):
    """Run a paginated myDevices query with the given filter."""
    found = []
    offset = 0
    for _ in range(MAX_PAGES):
        variables = {'filter': device_filter, 'offset': offset,
                     'limit': PAGE_SIZE}
        data = graphql(token, FIND_DEVICES_QUERY, variables, description)
        page = data.get('myDevices') or {}
        content = page.get('content') or []
        found.extend(content)
        total = page.get('totalElements') or 0
        offset += PAGE_SIZE
        if not content or len(found) >= total:
            break
    return found


def find_devices_by_tag(token, key, value):
    """Return every device carrying an exact key=value tag.

    Matches are re-checked locally, so a server-side filter change can never
    widen a match into deleting the wrong device. That local re-check only
    works while DEVICE_FIELDS requests 'tags { key value }' - see the comment
    there.
    """
    found = _find_devices(token, {'tag': {'key': key, 'value': {'eq': value}}},
                          'find devices by tag {}={}'.format(key, value))
    return [d for d in found if device_tag(d, key) == value]


def find_devices_by_label(token, label):
    """Return every device whose label exactly equals the given label."""
    found = _find_devices(token, {'label': {'eq': label}},
                          'find devices labelled {}'.format(label))
    return [d for d in found if d.get('label') == label]


def set_device_tags(token, device_id, tags):
    """Apply key=value tags to a device."""
    for key, value in tags:
        if value is None:
            continue
        graphql(token, SET_TAG_MUTATION,
                {'input': {'key': key, 'value': str(value),
                           'ids': [device_id]}},
                'set tag {}'.format(key))


def rename_device(token, device_id, label):
    """Change a device's label."""
    graphql(token, UPDATE_DEVICE_MUTATION,
            {'device': {'id': device_id, 'label': label}}, 'rename device')
    cp.log('Renamed P1 device {} to "{}"'.format(device_id, label))


def get_device(token, device_id):
    """Fetch a single P1 device by ID."""
    data = graphql(token, GET_DEVICE_QUERY, {'id': device_id}, 'get device')
    return data.get('device') or {}


def get_licenses(token, device_ids=None):
    """Return licenses in the account, optionally only for given devices.

    Args:
        token: P1 personal access token.
        device_ids: Optional list of device IDs to restrict the query to.

    Returns:
        list: License dicts.
    """
    collected = []
    offset = 0
    for _ in range(MAX_PAGES):
        variables = {'offset': offset, 'limit': PAGE_SIZE}
        if device_ids is not None:
            variables['devices'] = list(device_ids)
        data = graphql(token, LICENSES_QUERY, variables, 'list licenses')
        page = data.get('licenses') or {}
        content = page.get('content') or []
        collected.extend(content)
        total = page.get('totalElements') or 0
        offset += PAGE_SIZE
        if not content or len(collected) >= total:
            break
    return collected


def get_license_types(token):
    """Return all license types available to the account."""
    data = graphql(token, LICENSE_TYPES_QUERY, None, 'list license types')
    return data.get('licenseTypes') or []


def licenses_for_device(licenses, device_id):
    """Filter a license list down to those attached to a device ID."""
    matches = []
    for lic in licenses:
        device = lic.get('device') or {}
        if device.get('id') == device_id:
            matches.append(lic)
    return matches


def remove_device_licenses(token, device_id, licenses):
    """Detach every license currently attached to a device.

    Returns:
        list: IDs of licenses that were successfully detached.
    """
    detached = []
    for lic in licenses_for_device(licenses, device_id):
        license_id = lic.get('id')
        if not license_id:
            continue
        try:
            graphql(token, REMOVE_LICENSE_MUTATION,
                    {'licenseId': license_id, 'deviceId': device_id},
                    'remove license {}'.format(license_id))
            detached.append(license_id)
            cp.log('Removed license {} (number {}) from device {}'.format(
                license_id, lic.get('number'), device_id))
        except P1Error as err:
            # Keep going: the device delete is still worth attempting.
            cp.log('WARNING: could not remove license {}: {}'.format(
                license_id, err))
    return detached


def delete_device(token, device_id):
    """Delete a P1 device by ID.

    Returns:
        bool: True if the API reported a successful deletion.
    """
    data = graphql(token, DELETE_DEVICES_MUTATION, {'ids': [device_id]},
                   'delete device {}'.format(device_id))
    result = data.get('deleteDevices') or {}
    success = bool(result.get('success')) and (result.get('deletedCount') or 0) > 0
    if success:
        cp.log('Deleted stale P1 device {}'.format(device_id))
    else:
        cp.log('WARNING: delete of device {} reported {}'.format(
            device_id, json.dumps(result)))
    return success


def create_device(token, label):
    """Create a new enabled P1 device with the given label."""
    variables = {'device': {'label': label, 'enabled': True}}
    data = graphql(token, CREATE_DEVICE_MUTATION, variables, 'create device')
    device = data.get('createDevice') or {}
    if not device.get('id'):
        raise P1Error('create device: response had no device ID')
    cp.log('Created P1 device "{}" id {}'.format(label, device['id']))
    return device


def select_license_type(license_types, preference):
    """Pick a license type.

    Args:
        license_types: List of LicenseType dicts from the API.
        preference: A license type ID, or a substring to match against the
            license type description (case-insensitive).

    Returns:
        dict: The chosen license type, or None if nothing matched.
    """
    if not license_types:
        return None

    # Exact ID match wins.
    for lt in license_types:
        if lt.get('id') == preference:
            return lt

    wanted = (preference or '').strip().lower()
    if wanted:
        matches = [lt for lt in license_types
                   if wanted in (lt.get('description') or '').lower()]
        if matches:
            # Longest term first so "1 Year" beats "1 Month".
            return sorted(matches, key=_term_days, reverse=True)[0]

    cp.log('WARNING: no license type matched "{}", falling back to the '
           'longest available term'.format(preference))
    return sorted(license_types, key=_term_days, reverse=True)[0]


def _term_days(license_type):
    """Approximate a license type's term length in days, for sorting."""
    periods = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
    length = license_type.get('termLength') or 0
    period = (license_type.get('termPeriod') or '').strip().lower().rstrip('s')
    try:
        return int(length) * periods.get(period, 0)
    except (TypeError, ValueError):
        return 0


def find_unassigned_license(licenses, license_type_id):
    """Find an existing license of the given type that is not attached to a device."""
    for lic in licenses:
        if (lic.get('device') or {}).get('id'):
            continue
        current = lic.get('currentLicenseType') or {}
        if current.get('id') == license_type_id:
            return lic
    return None


def ensure_license(token, device_id, license_preference, allow_create,
                   auto_renewal, licenses=None):
    """Make sure a device has a license attached.

    Does nothing if the device is already licensed. Otherwise reuses an
    unassigned license from account inventory when one exists, and only
    creates (bills) a new license as a last resort.

    Returns:
        dict: The license attached to the device, or None if licensing
            could not be completed.
    """
    existing = licenses_for_device(get_licenses(token, device_ids=[device_id]),
                                   device_id)
    if existing:
        current = existing[0]
        cp.log('Device {} is already licensed: {} (number {}, expires {})'
               .format(device_id, current.get('id'), current.get('number'),
                       current.get('endDate')))
        return current

    license_types = get_license_types(token)
    if not license_types:
        cp.log('WARNING: account has no license types available; skipping '
               'licensing')
        return None

    chosen = select_license_type(license_types, license_preference)
    if not chosen:
        cp.log('WARNING: could not choose a license type; skipping licensing')
        return None
    cp.log('Using license type "{}" ({} {}) id {}'.format(
        chosen.get('description'), chosen.get('termLength'),
        chosen.get('termPeriod'), chosen.get('id')))

    if licenses is None:
        licenses = get_licenses(token)

    spare = find_unassigned_license(licenses, chosen['id'])
    if spare:
        cp.log('Reusing unassigned license {} (number {})'.format(
            spare['id'], spare.get('number')))
        data = graphql(token, APPLY_LICENSE_MUTATION,
                       {'licenseId': spare['id'], 'deviceId': device_id},
                       'apply license')
        applied = data.get('applyLicenseToDevice') or {}
        cp.log('Applied license {} to device {}'.format(
            applied.get('id'), device_id))
        return applied

    if not allow_create:
        cp.log('WARNING: no unassigned license available and license creation '
               'is disabled (p1_create_license=false); device is unlicensed')
        return None

    variables = {
        'licenseType': chosen['id'],
        'deviceIDs': [device_id],
        'autoRenewal': auto_renewal,
    }
    data = graphql(token, CREATE_LICENSES_FOR_DEVICES_MUTATION, variables,
                   'create license')
    created = data.get('createLicensesForDevices') or []
    if not created:
        cp.log('WARNING: license creation returned no licenses')
        return None
    new_license = created[0]
    cp.log('Created license {} (number {}) valid {} -> {}'.format(
        new_license.get('id'), new_license.get('number'),
        new_license.get('startDate'), new_license.get('endDate')))
    return new_license


# ---------------------------------------------------------------------------
# Config value derivation
# ---------------------------------------------------------------------------

def parse_caster_url(caster_url):
    """Split a caster URL or host[:port] string into (host, port).

    Returns:
        tuple: (host or None, port or None)
    """
    if not caster_url:
        return None, None

    value = str(caster_url).strip()
    for scheme in ('ntrip://', 'https://', 'http://'):
        if value.lower().startswith(scheme):
            value = value[len(scheme):]
            break
    value = value.split('/')[0]

    host = value
    port = None
    if ':' in value:
        host, _, port_text = value.rpartition(':')
        try:
            port = int(port_text)
        except ValueError:
            host = value
            port = None
    return (host or None), port


def build_ntrip_config(ntrip, caster_host, caster_port, mountpoint):
    """Assemble the config/system/rtk/ntrip struct.

    Args:
        ntrip: The NTRIP object from the P1 API.
        caster_host: Configured caster host override/default.
        caster_port: Configured caster port override/default.
        mountpoint: Configured mountpoint override/default.

    Returns:
        dict: Values for config/system/rtk/ntrip.

    Raises:
        P1Error: If the API did not supply NTRIP credentials.
    """
    login = (ntrip or {}).get('login')
    password = (ntrip or {}).get('password')
    if not login or not password:
        raise P1Error('device has no NTRIP credentials (login/password empty)')

    # A non-null casterUrl / mountPoint from the API wins over our defaults.
    api_host, api_port = parse_caster_url((ntrip or {}).get('casterUrl'))
    host = api_host or caster_host
    port = api_port or caster_port
    mount = (ntrip or {}).get('mountPoint') or mountpoint

    if len(str(login)) > MAX_CREDENTIAL_LEN:
        raise P1Error('NTRIP username is {} chars, NCOS allows {}'.format(
            len(str(login)), MAX_CREDENTIAL_LEN))
    if len(str(password)) > MAX_CREDENTIAL_LEN:
        raise P1Error('NTRIP password is {} chars, NCOS allows {}'.format(
            len(str(password)), MAX_CREDENTIAL_LEN))
    if len(str(mount)) > MAX_MOUNTPOINT_LEN:
        raise P1Error('NTRIP mountpoint is {} chars, NCOS allows {}'.format(
            len(str(mount)), MAX_MOUNTPOINT_LEN))

    return {
        'host': str(host),
        'port': int(port),
        'mountpoint': str(mount),
        'username': str(login),
        'password': str(password),
    }


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
        cp.log('Could not read {}: {}'.format('config/system/rtk', err))
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

    applied = _verify_ntrip_config(ntrip_config)
    if not applied:
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
# Appdata settings
# ---------------------------------------------------------------------------

def resolve_device(token, hostname, mac, replace_stale):
    """Find this router's P1 device, or create it, replacing stale hardware.

    The device label is simply the router hostname. Identity is the router
    MAC, carried in the '<TAG_MAC>' tag, so a rename never loses the device.
    Three cases:

    1. A device tagged with this MAC already exists -> it is ours. Reuse it
       as-is; no device is created and nothing is deleted. The label is
       refreshed if the router has been renamed.
    2. No MAC match, but a device created by this app carries this hostname
       as its label -> different hardware in the same deployment slot, i.e.
       this router is a replacement. The old device is unlicensed and
       deleted, then ours is created.
    3. Neither -> first run on this router. Create the device.

    Returns:
        tuple: (device dict, list of license IDs freed by a replacement)
    """
    mine = find_devices_by_tag(token, TAG_MAC, mac)
    if mine:
        # More than one would mean a previous partial run; keep the oldest.
        mine.sort(key=lambda d: d.get('createdAt') or '')
        device = mine[0]
        cp.log('Reusing existing P1 device {} ("{}") for MAC {}'.format(
            device.get('id'), device.get('label'), mac))

        for extra in mine[1:]:
            cp.log('WARNING: duplicate P1 device {} for MAC {} - removing'
                   .format(extra.get('id'), mac))
            release_and_delete(token, extra.get('id'))

        if device.get('label') != hostname:
            cp.log('Router was renamed: label "{}" -> "{}"'.format(
                device.get('label'), hostname))
            rename_device(token, device['id'], hostname)
            device['label'] = hostname
        if device_tag(device, TAG_APP) != APP_TAG_VALUE:
            set_device_tags(token, device['id'], [(TAG_APP, APP_TAG_VALUE)])
        return device, []

    # No device for this MAC. Anything holding our hostname as its label is
    # older hardware for the same slot.
    freed = []
    same_label = [d for d in find_devices_by_label(token, hostname)
                  if device_tag(d, TAG_MAC) != mac]

    # Only ever delete devices this app created. A device added by hand or by
    # other tooling that happens to share the hostname is left untouched.
    stale = [d for d in same_label if device_tag(d, TAG_APP) == APP_TAG_VALUE]
    for foreign in [d for d in same_label if d not in stale]:
        cp.log('WARNING: P1 device {} is labelled "{}" but was not created by '
               'this app (no {}={} tag) - leaving it alone'.format(
                   foreign.get('id'), hostname, TAG_APP, APP_TAG_VALUE))

    if stale:
        if not replace_stale:
            cp.log('WARNING: {} P1 device(s) labelled "{}" belong to different '
                   'hardware, but p1_replace_stale is false - leaving them '
                   'alone. This account may accumulate duplicates.'.format(
                       len(stale), hostname))
        else:
            cp.log('Hostname "{}" is registered to different hardware - this '
                   'router is a replacement'.format(hostname))
            for old in stale:
                cp.log('Replacing P1 device {} ("{}", MAC {}) with MAC {}'
                       .format(old.get('id'), old.get('label'),
                               device_tag(old, TAG_MAC), mac))
                freed.extend(release_and_delete(token, old.get('id')))
    elif not same_label:
        cp.log('No existing P1 device for MAC {} or label "{}" - first run '
               'on this router'.format(mac, hostname))

    device = create_device(token, hostname)
    set_device_tags(token, device['id'], [
        (TAG_APP, APP_TAG_VALUE),
        (TAG_MAC, mac),
    ])
    # createDevice's response predates the tags, so re-read to return a device
    # that actually carries them.
    refreshed = get_device(token, device['id'])
    return (refreshed or device), freed


def release_and_delete(token, device_id):
    """Detach a device's licenses and delete it.

    Returns:
        list: IDs of licenses freed, now reusable from account inventory.
    """
    if not device_id:
        return []
    device_licenses = get_licenses(token, device_ids=[device_id])
    freed = remove_device_licenses(token, device_id, device_licenses)
    delete_device(token, device_id)
    return freed


def mask_secret(value):
    """Describe a secret without disclosing it, for logs."""
    if not value:
        return '<unset>'
    text = str(value)
    return '{}... ({} chars)'.format(text[:4], len(text))


def read_appdata_snapshot():
    """Read all appdata once and return {lowercased name: value}.

    Change detection is polling, not cp.register(): appdata entries are
    addressed by an '_id_' UUID that changes whenever a field is deleted and
    recreated, so there is no stable per-field path to register on, and
    cp.register() is a no-op off-router (it only works over the NCOS socket),
    which would leave local runs with no change detection at all. One read of
    this single small path per poll is cheap, so polling is the only code
    path.

    cp.get_appdata(name) rescans the whole appdata list on every call, so the
    eight fields this app consumes are resolved from one snapshot instead of
    eight reads.

    Returns:
        dict: {name.lower(): value}, or None if the read failed. None means
            "unknown", not "empty" - the caller must not read a failed poll
            as a cleared token.
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


def setting_from(snapshot, name, default=None):
    """Resolve one appdata field from a snapshot, defaulting in code.

    Defaults are never written back to appdata - that would override group
    configs pushed from NetCloud Manager.
    """
    value = snapshot.get(name.lower())
    if value is None:
        return default
    value = str(value).strip()
    if not value:
        return default
    return value


def bool_setting_from(snapshot, name, default):
    """Resolve a boolean appdata field from a snapshot."""
    value = setting_from(snapshot, name)
    if value is None:
        return default
    return value.lower() in ('1', 'true', 'yes', 'on', 'enabled')


def int_setting_from(snapshot, name, default):
    """Resolve an integer appdata field from a snapshot."""
    value = setting_from(snapshot, name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        cp.log('WARNING: appdata "{}" is not an integer ("{}"), using {}'
               .format(name, value, default))
        return default


def read_config():
    """Read the current configuration: one appdata read plus the hostname.

    Returns:
        dict: Settings keyed by short name, or None if appdata could not be
            read (the caller should skip the pass rather than treat the
            unknown state as a cleared field).
    """
    snapshot = read_appdata_snapshot()
    if snapshot is None:
        return None

    return {
        'token': setting_from(snapshot, 'p1_token'),
        'caster_host': setting_from(snapshot, 'p1_caster_host',
                                    DEFAULT_CASTER_HOST),
        'caster_port': int_setting_from(snapshot, 'p1_caster_port',
                                        DEFAULT_CASTER_PORT),
        'mountpoint': setting_from(snapshot, 'p1_mountpoint',
                                   DEFAULT_MOUNTPOINT),
        'license_type': setting_from(snapshot, 'p1_license_type',
                                     DEFAULT_LICENSE_MATCH),
        'create_license': bool_setting_from(snapshot, 'p1_create_license',
                                            True),
        'license_auto_renewal': bool_setting_from(
            snapshot, 'p1_license_auto_renewal', False),
        'replace_stale': bool_setting_from(snapshot, 'p1_replace_stale', True),
        # Not appdata, but consumed the same way: the P1 device label follows
        # the router hostname, so a live rename has to re-provision too.
        'hostname': cp.get_name(),
    }


def changed_fields(old, new):
    """Return the sorted names of settings whose values differ.

    Names only, never values: a setting can hold a secret.
    """
    if old is None:
        return sorted(new.keys())
    names = set(old.keys()) | set(new.keys())
    return sorted(n for n in names if old.get(n) != new.get(n))


def missing_required(config):
    """Return the human-readable names of required settings that are empty."""
    missing = []
    if not config.get('token'):
        missing.append('appdata "p1_token"')
    if not config.get('hostname'):
        missing.append('config/system/system_id (router hostname)')
    return missing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def provision(config):
    """Run the full provisioning flow once against the given configuration.

    Args:
        config: Settings dict from read_config(). The required fields are
            already known to be present - the supervisor checks that.

    Returns:
        True if the router was configured and RTK enabled, the string
        'unsupported' if this router model has no RTK support (retrying
        sooner will not help), or False on any other failure.
    """
    token = config['token']
    hostname = config['hostname']
    cp.log('Router hostname: {}'.format(hostname))

    # Gate before touching the P1 account: creating a device and license on a
    # router that cannot use them would leave stray billable resources behind.
    if not rtk_supported():
        cp.log('ERROR: this router model has no config/system/rtk key, so it '
               'does not support RTK/NTRIP. RTK requires a product with RTK '
               'support (for example an R2400). No Point One device or '
               'license was created.')
        return 'unsupported'

    # Skip the whole flow when nothing has changed since the last run, so a
    # reboot or app restart does not delete and recreate the P1 device.
    mac = cp.get_mac()
    if not mac:
        cp.log('ERROR: could not read the router MAC address '
               '(status/product_info/mac0)')
        return False
    mac = mac.replace(':', '').lower()
    cp.log('Router MAC: {}'.format(mac))

    caster_host = config['caster_host']
    caster_port = config['caster_port']
    mountpoint = config['mountpoint']
    license_preference = config['license_type']
    allow_create_license = config['create_license']
    auto_renewal = config['license_auto_renewal']
    replace_stale = config['replace_stale']

    # 1. Find our device by MAC, or create it - replacing different hardware
    #    that holds this hostname.
    device, _freed = resolve_device(token, hostname, mac, replace_stale)
    device_id = device['id']

    # 2. License it (a no-op when it already carries a license).
    ensure_license(token, device_id, license_preference, allow_create_license,
                   auto_renewal)

    # 3. Read the device back so the NTRIP values reflect the license.
    refreshed = get_device(token, device_id)
    if refreshed:
        device = refreshed
    rtk = ((device.get('services') or {}).get('rtk')) or {}
    ntrip = rtk.get('ntrip') or {}
    cp.log('P1 RTK service: enabled={} connectionStatus={}'.format(
        rtk.get('enabled'), rtk.get('connectionStatus')))

    # 4. Derive and apply the router config.
    ntrip_config = build_ntrip_config(ntrip, caster_host, caster_port,
                                      mountpoint)
    cp.log('NTRIP config resolved: host={} port={} mountpoint={} username={}'
           .format(ntrip_config['host'], ntrip_config['port'],
                   ntrip_config['mountpoint'], ntrip_config['username']))

    if not apply_router_config(ntrip_config):
        return False

    cp.log('Point One NTRIP provisioning complete for device {}'.format(
        device_id))
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


def main():
    """Supervise configuration and keep the router provisioned.

    Configuration is a reloadable state, not a startup gate: every pass
    re-reads appdata, compares it against what was last applied, and
    re-provisions when it differs. Missing configuration parks the app in
    this same loop, so a token added at runtime is picked up within
    CONFIG_POLL_INTERVAL with no app restart and no reboot.

    This function never returns. package.ini sets restart = true, so a
    process that exits is relaunched immediately - every error path stays
    inside the loop.
    """
    cp.log('Starting pointonenav...')

    # One blocking wait at startup so a cold boot provisions as soon as the
    # WAN comes up. A timeout is not fatal: the loop re-checks connectivity
    # on every pass.
    if not cp.wait_for_wan_connection(timeout=WAN_WAIT_TIMEOUT):
        cp.log('No WAN connection after {}s; continuing to poll for '
               'connectivity and configuration'.format(WAN_WAIT_TIMEOUT))

    state = None          # STATE_*, None until the first pass decides
    last_seen = None      # last complete config read, for change detection
    applied = None        # config last provisioned successfully
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

            if config is None:
                # Unknown, not empty. A failed read must never be mistaken
                # for a cleared token, so applied state is left alone.
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
                last_seen = config
                backoff = PROVISION_BACKOFF_START
                next_attempt = 0.0

            else:
                if last_seen is None or config != last_seen:
                    names = changed_fields(last_seen, config)
                    if last_seen is None:
                        cp.log('Configuration read: p1_token {}'.format(
                            mask_secret(config['token'])))
                    else:
                        # Field names only - a value may be a secret.
                        cp.log('Configuration changed: {} - re-applying'
                               .format(', '.join(names)))
                        if 'token' in names:
                            cp.log('Point One token is now {} - '
                                   're-provisioning under it'.format(
                                       mask_secret(config['token'])))
                    last_seen = config
                    applied = None
                    backoff = PROVISION_BACKOFF_START
                    next_attempt = 0.0

                if applied is None and now >= next_attempt:
                    if not wan_connected():
                        if now - last_wan_log >= WAIT_LOG_INTERVAL:
                            cp.log('No WAN connection - cannot reach the '
                                   'Point One API; still polling')
                            last_wan_log = now
                    else:
                        detail = ''
                        try:
                            result = provision(config)
                        except P1Error as err:
                            detail = str(err)
                            cp.log('ERROR: {}'.format(detail))
                            result = False
                        except Exception as err:
                            detail = 'unexpected failure: {}'.format(err)
                            cp.log('ERROR: {}'.format(detail))
                            result = False

                        if result is True:
                            applied = config
                            last_status_log = now
                            backoff = PROVISION_BACKOFF_START
                            if state != STATE_READY:
                                cp.log('Point One NTRIP corrections '
                                         'configured and enabled')
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
                                cp.log('Point One NTRIP provisioning '
                                         'failed: {}'.format(detail))
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
