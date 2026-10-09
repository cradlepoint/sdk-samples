# Ericsson Router SDK Application
"""Base classes shared by every corrections provider.

A provider owns the account-side work for one RTK corrections service:
register this router, make sure it is licensed/entitled, and return the NTRIP
credentials the router needs. The generic core applies those credentials to
config/system/rtk - a provider never touches router config itself.
"""


class ProviderError(Exception):
    """A corrections provider could not complete provisioning.

    The supervisor loop treats this as a retryable failure: it logs the
    message, backs off, and tries again. Raise it (rather than returning a
    half-built result) whenever an account-side step fails.
    """


class NtripResult(object):
    """The NTRIP connection details a provider hands back to the core.

    Attributes:
        host: NTRIP caster hostname.
        port: NTRIP caster port.
        mountpoint: NTRIP mountpoint.
        username: NTRIP login.
        password: NTRIP password.

    All five are required. The core validates NCOS length limits before it
    writes config/system/rtk/ntrip, so a provider does not need to.
    """

    def __init__(self, host, port, mountpoint, username, password):
        self.host = host
        self.port = port
        self.mountpoint = mountpoint
        self.username = username
        self.password = password


class Provider(object):
    """Base class for a corrections provider.

    Subclasses set NAME and DETECT_FIELD and implement required_fields(),
    read_config() and provision(). The core calls them in that order.
    """

    # Human-readable provider name, used in logs and as the sdk_app tag value
    # a provider sets on resources it owns.
    NAME = 'provider'

    # The appdata field whose presence selects this provider. Must be unique
    # across providers so one set of appdata selects exactly one provider.
    DETECT_FIELD = ''

    def required_fields(self):
        """Return the appdata field names this provider needs to run.

        The core reports the human-readable names of any that are missing and
        parks in its waiting state until they are set, without calling
        provision(). DETECT_FIELD is usually the only required field.

        Returns:
            list[str]: Required appdata field names.
        """
        return [self.DETECT_FIELD]

    def read_config(self, snapshot, helpers):
        """Pull this provider's settings out of the appdata snapshot.

        Args:
            snapshot: {name.lower(): value} appdata map.
            helpers: An AppdataHelpers instance with str/int/bool resolvers so
                a provider does not re-implement defaulting. Defaults live in
                code and are never written back to appdata.

        Returns:
            dict: Provider settings. The core stores this opaquely, compares it
                across polls to detect changes, and passes it back to
                provision(). It must be comparable with != and contain no
                secrets the provider would not want logged by name only (the
                core logs changed field *names*, never values).
        """
        raise NotImplementedError

    def provision(self, config, hostname, mac):
        """Register the router with the service and return NTRIP credentials.

        Called only when every required field is present and the router model
        supports RTK. Must be idempotent: the app re-runs this whenever
        configuration changes and on every restart, so a second run against an
        already-registered router must not create duplicate account resources.

        Args:
            config: The dict returned by read_config().
            hostname: Router hostname (config/system/system_id), the natural
                device label.
            mac: Router MAC, lowercased with no colons, the stable hardware
                identity.

        Returns:
            NtripResult: The caster and credential details to apply.

        Raises:
            ProviderError: On any account-side failure. The core retries.
        """
        raise NotImplementedError
