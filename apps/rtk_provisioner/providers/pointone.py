# Ericsson Router SDK Application
"""Point One Navigation ("P1") corrections provider.

Registers this router as a licensed Point One device through the P1 GraphQL
API and returns its NTRIP credentials. Selected when appdata contains
'p1_token'.

Device identity (unchanged from the original pointonenav app):
  - the device label is the router hostname
  - hardware identity is the router MAC, held in a 'router_mac' tag, so a
    rename updates the label in place instead of orphaning the device
  - a device this app created that still carries this hostname but a
    different MAC is older hardware for the same slot and is replaced

The P1 GraphQL API returns casterUrl / mountPoint as null today, so the
caster host, port and mountpoint fall back to the documented True RTK values
and can be overridden through appdata.
"""

import json
import urllib.error
import urllib.request

import cp

from .base import NtripResult, Provider, ProviderError

GRAPHQL_URL = 'https://graphql.pointonenav.com/graphql'
HTTP_TIMEOUT = 30

# Point One True RTK caster defaults. The API does not return these.
DEFAULT_CASTER_HOST = 'truertk.pointonenav.com'
DEFAULT_CASTER_PORT = 2101
DEFAULT_MOUNTPOINT = 'AUTO'

# Preferred license type, matched against LicenseType.description.
DEFAULT_LICENSE_MATCH = 'True RTK'

# The device label is the router hostname. Hardware identity lives in a tag,
# so renaming the router never loses track of the device.
TAG_APP = 'sdk_app'          # scopes lookups to devices this app created
TAG_MAC = 'router_mac'       # true hardware identity (full MAC, no colons)
APP_TAG_VALUE = 'rtk_provisioner'

# Page size for paginated list queries.
PAGE_SIZE = 100
MAX_PAGES = 50


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
        ProviderError: On transport failure or any GraphQL 'errors' entry.
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
            raise ProviderError('{}: 401 unauthorized - check the p1_token '
                                'appdata value (expired or wrong token)'
                                .format(description))
        raise ProviderError('{}: HTTP {} {}'.format(description, err.code,
                                                    detail))
    except urllib.error.URLError as err:
        raise ProviderError('{}: could not reach {} ({})'.format(
            description, GRAPHQL_URL, err.reason))
    except Exception as err:
        raise ProviderError('{}: {}'.format(description, err))

    try:
        parsed = json.loads(body)
    except ValueError as err:
        raise ProviderError('{}: invalid JSON response ({})'.format(
            description, err))

    if parsed.get('errors'):
        messages = []
        for entry in parsed['errors']:
            if isinstance(entry, dict):
                messages.append(str(entry.get('message') or entry))
            else:
                messages.append(str(entry))
        raise ProviderError('{}: {}'.format(description, '; '.join(messages)))

    data = parsed.get('data')
    if data is None:
        raise ProviderError('{}: response contained no data'.format(
            description))
    return data


# ---------------------------------------------------------------------------
# GraphQL documents
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


# ---------------------------------------------------------------------------
# Point One operations
# ---------------------------------------------------------------------------

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
        except ProviderError as err:
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
        raise ProviderError('create device: response had no device ID')
    cp.log('Created P1 device "{}" id {}'.format(label, device['id']))
    return device


def _term_days(license_type):
    """Approximate a license type's term length in days, for sorting."""
    periods = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
    length = license_type.get('termLength') or 0
    period = (license_type.get('termPeriod') or '').strip().lower().rstrip('s')
    try:
        return int(length) * periods.get(period, 0)
    except (TypeError, ValueError):
        return 0


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


def find_unassigned_license(licenses, license_type_id):
    """Find an existing license of the given type not attached to a device."""
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


def resolve_device(token, hostname, mac, replace_stale):
    """Find this router's P1 device, or create it, replacing stale hardware.

    The device label is the router hostname. Identity is the router MAC,
    carried in the TAG_MAC tag, so a rename never loses the device. Three
    cases:

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


# ---------------------------------------------------------------------------
# NTRIP derivation
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


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class PointOneProvider(Provider):
    """Point One Navigation corrections provider."""

    NAME = 'Point One Navigation'
    DETECT_FIELD = 'p1_token'

    def required_fields(self):
        return ['p1_token']

    def read_config(self, snapshot, helpers):
        return {
            'provider': self.NAME,
            'token': helpers.string(snapshot, 'p1_token'),
            'caster_host': helpers.string(snapshot, 'p1_caster_host',
                                          DEFAULT_CASTER_HOST),
            'caster_port': helpers.integer(snapshot, 'p1_caster_port',
                                           DEFAULT_CASTER_PORT),
            'mountpoint': helpers.string(snapshot, 'p1_mountpoint',
                                         DEFAULT_MOUNTPOINT),
            'license_type': helpers.string(snapshot, 'p1_license_type',
                                           DEFAULT_LICENSE_MATCH),
            'create_license': helpers.boolean(snapshot, 'p1_create_license',
                                              True),
            'license_auto_renewal': helpers.boolean(
                snapshot, 'p1_license_auto_renewal', False),
            'replace_stale': helpers.boolean(snapshot, 'p1_replace_stale',
                                             True),
        }

    def provision(self, config, hostname, mac):
        token = config['token']

        # 1. Find our device by MAC, or create it - replacing different
        #    hardware that holds this hostname.
        device, _freed = resolve_device(token, hostname, mac,
                                        config['replace_stale'])
        device_id = device['id']

        # 2. License it (a no-op when it already carries a license).
        ensure_license(token, device_id, config['license_type'],
                       config['create_license'],
                       config['license_auto_renewal'])

        # 3. Read the device back so the NTRIP values reflect the license.
        refreshed = get_device(token, device_id)
        if refreshed:
            device = refreshed
        rtk = ((device.get('services') or {}).get('rtk')) or {}
        ntrip = rtk.get('ntrip') or {}
        cp.log('P1 RTK service: enabled={} connectionStatus={}'.format(
            rtk.get('enabled'), rtk.get('connectionStatus')))

        login = ntrip.get('login')
        password = ntrip.get('password')
        if not login or not password:
            raise ProviderError('device has no NTRIP credentials '
                                '(login/password empty)')

        # A non-null casterUrl / mountPoint from the API wins over defaults.
        api_host, api_port = parse_caster_url(ntrip.get('casterUrl'))
        host = api_host or config['caster_host']
        port = api_port or config['caster_port']
        mount = ntrip.get('mountPoint') or config['mountpoint']

        cp.log('Point One provisioning complete for device {}'.format(
            device_id))
        return NtripResult(host=host, port=port, mountpoint=mount,
                           username=login, password=password)
