# Ericsson Router SDK Application
"""Corrections-provider plugins for rtk_provisioner.

Each provider knows how to register this router with one RTK corrections
service and hand back the NTRIP credentials the router needs. The generic
core in rtk_provisioner.py owns everything on the router side (GPS, the
config/system/rtk writes, the supervisor loop); a provider owns only the
account-side work for its service.

Adding a provider is three steps:
  1. Write a module here with a Provider subclass (see base.py and
     pointone.py).
  2. Give it a DETECT_FIELD so the core can recognise it from appdata.
  3. Append the class to PROVIDERS below.

Detection is by appdata field: the first provider whose DETECT_FIELD is
present in config/system/sdk/appdata wins. Point One is recognised by
'p1_token'. Keep DETECT_FIELD values distinct across providers so one set of
appdata selects exactly one provider.
"""

from .base import NtripResult, Provider, ProviderError
from .pointone import PointOneProvider

# Registration order is detection priority. The first provider whose
# DETECT_FIELD appears in appdata is selected.
PROVIDERS = [
    PointOneProvider,
]


def detect_provider(snapshot):
    """Return a provider instance for the appdata snapshot, or None.

    Args:
        snapshot: {name.lower(): value} appdata map from the core.

    Returns:
        Provider: An instance of the first matching provider, or None if no
            provider's DETECT_FIELD is present.
    """
    for provider_cls in PROVIDERS:
        field = provider_cls.DETECT_FIELD.lower()
        value = snapshot.get(field)
        if value is not None and str(value).strip():
            return provider_cls()
    return None


def provider_names():
    """Return the display names of every registered provider."""
    return [p.NAME for p in PROVIDERS]


def detect_fields():
    """Return the detection appdata field of every registered provider."""
    return [p.DETECT_FIELD for p in PROVIDERS]


__all__ = [
    'NtripResult',
    'Provider',
    'ProviderError',
    'PointOneProvider',
    'PROVIDERS',
    'detect_provider',
    'provider_names',
    'detect_fields',
]
