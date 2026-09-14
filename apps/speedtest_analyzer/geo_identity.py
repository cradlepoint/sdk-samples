"""Cell identity normalization for GeoView resolution (v1.1.3).

Turns a site-inventory serving-cell record (from
``cellular_analysis.build_site_cell_inventory``) into either a
``NormalizedIdentity`` eligible for provider geolocation, or an explicit
``Ineligible`` result. It NEVER guesses a location and NEVER substitutes PCI
for a Cell ID (LLD §6, HLD §9).

Rules:
    * LTE / 5G NSA  -> require a full ECI (a real Cell ID). PCI-only is
      INELIGIBLE. Semantics = ECI.
    * 5G SA         -> require a full NCI (a real NR Cell ID). PCI-only is
      INELIGIBLE. Semantics = NCI.
    * SCells are eligible only when a sufficiently unique supported identity
      exists; otherwise INELIGIBLE.
    * Incomplete identity -> explicit Ineligible(reason), never a guess.

The upstream ``build_site_cell_inventory`` already refuses to manufacture a
serving identity from PCI/TAC/band (``_canonical_cell_id`` returns '' unless a
real Cell ID/NCI is present), so this module's Cell-ID check composes with that
guarantee rather than duplicating modem-specific parsing.
"""


SEMANTICS_ECI = 'eci'
SEMANTICS_NCI = 'nci'

# Ineligibility reasons (explicit, surfaced to the UI; never a fake location).
REASON_NO_CELL_ID = 'no_cell_id'
REASON_PCI_ONLY = 'pci_only'
REASON_NO_PLMN = 'no_plmn'
REASON_SCELL_NOT_UNIQUE = 'scell_not_unique'
REASON_UNKNOWN_ACCESS = 'unknown_access'


class NormalizedIdentity(object):
    """An eligible, provider-ready normalized cell identity."""

    __slots__ = ('cell_key', 'semantics', 'value', 'cell_id', 'mcc', 'mnc',
                 'lac', 'radio')

    def __init__(self, cell_key, semantics, value, cell_id, mcc, mnc,
                 lac=None, radio=None):
        self.cell_key = cell_key
        self.semantics = semantics
        self.value = value
        self.cell_id = cell_id
        self.mcc = mcc
        self.mnc = mnc
        self.lac = lac
        self.radio = radio

    @property
    def eligible(self):
        return True

    def to_request(self):
        """Dict consumed by provider adapters (no display-only fields)."""
        return {
            'cell_key': self.cell_key,
            'semantics': self.semantics,
            'value': self.value,
            'cell_id': self.cell_id,
            'mcc': self.mcc,
            'mnc': self.mnc,
            'lac': self.lac,
            'radio': self.radio,
        }

    def to_metadata(self):
        """Metadata-only view for status responses."""
        return {
            'cell_key': self.cell_key,
            'eligible': True,
            'semantics': self.semantics,
        }


class Ineligible(object):
    """An explicit ineligible result. Carries a reason, never a location."""

    __slots__ = ('cell_key', 'reason')

    def __init__(self, cell_key, reason):
        self.cell_key = cell_key
        self.reason = reason

    @property
    def eligible(self):
        return False

    def to_metadata(self):
        return {
            'cell_key': self.cell_key,
            'eligible': False,
            'reason': self.reason,
        }


def _positive_int(value):
    """Return a positive int for a decimal/hex-ish string, else None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        try:
            number = int(text, 16)
        except (TypeError, ValueError):
            return None
    return number if number > 0 else None


def _split_plmn(plmn):
    """Split a PLMN string into (mcc, mnc) ints, or (None, None).

    MCC is the first 3 digits; MNC is the remaining 2-3 digits. Providers
    accept a 2- or 3-digit MNC, so the remainder is passed through as-is.
    """
    if plmn is None:
        return None, None
    digits = ''.join(ch for ch in str(plmn) if ch.isdigit())
    if len(digits) not in (5, 6):
        return None, None
    mcc = _positive_int(digits[:3])
    mnc = _positive_int(digits[3:])
    return mcc, mnc


def _access_semantics(cell):
    """Map a cell's service_mode / cell_id_source to (semantics, radio)."""
    source = str(cell.get('cell_id_source') or '').upper()
    service_mode = str(cell.get('service_mode') or '').upper()

    is_nr = (
        source in ('NR', 'NR_CELL_ID')
        or service_mode == '5G SA'
    )
    if is_nr:
        return SEMANTICS_NCI, 'nr'

    # LTE and 5G NSA both use the LTE anchor identity (ECI semantics).
    if source == 'LTE' or service_mode in ('LTE', '5G NSA'):
        return SEMANTICS_ECI, 'lte'

    # A present Cell ID with an unrecognized source still defaults to LTE/ECI
    # only when a source is derivable; otherwise treat as unknown access.
    if source:
        return SEMANTICS_ECI, 'lte'
    return None, None


def normalize_identity(cell):
    """Normalize one site-inventory cell into NormalizedIdentity | Ineligible.

    ``cell`` is a dict from ``build_site_cell_inventory`` (keys: ``key``,
    ``cell_id``, ``cell_id_source``, ``plmn``, ``pci``, ``band``, ...).
    """
    if not isinstance(cell, dict):
        return Ineligible('', REASON_NO_CELL_ID)

    cell_key = cell.get('key') or ''

    semantics, radio = _access_semantics(cell)
    if semantics is None:
        # No usable access class. If only a PCI exists, say so explicitly.
        if cell.get('pci') and not cell.get('cell_id'):
            return Ineligible(cell_key, REASON_PCI_ONLY)
        return Ineligible(cell_key, REASON_UNKNOWN_ACCESS)

    cell_id = _positive_int(cell.get('cell_id'))
    if cell_id is None:
        # PCI must never substitute for a Cell ID. Distinguish the PCI-only
        # case for a clearer explicit result.
        if cell.get('pci'):
            return Ineligible(cell_key, REASON_PCI_ONLY)
        return Ineligible(cell_key, REASON_NO_CELL_ID)

    mcc, mnc = _split_plmn(cell.get('plmn'))
    if mcc is None or mnc is None:
        return Ineligible(cell_key, REASON_NO_PLMN)

    # TAC (LTE) is not a LAC, but the Geolocation API accepts it as the area
    # code hint when present; pass it through when numeric.
    lac = _positive_int(cell.get('tac'))

    return NormalizedIdentity(
        cell_key=cell_key,
        semantics=semantics,
        value=cell_id,
        cell_id=cell_id,
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        radio=radio,
    )


def normalize_inventory(cells):
    """Normalize a list of inventory cells.

    Returns ``(eligible, ineligible)`` where ``eligible`` is a list of
    ``NormalizedIdentity`` and ``ineligible`` is a list of ``Ineligible``.
    SCell uniqueness: identities that collapse to the same (semantics, value,
    mcc, mnc) are de-duplicated so a non-uniquely-identifiable duplicate is not
    resolved twice; a first occurrence wins.
    """
    eligible = []
    ineligible = []
    seen = set()

    for cell in cells or []:
        result = normalize_identity(cell)
        if not result.eligible:
            ineligible.append(result)
            continue

        signature = (result.semantics, result.value, result.mcc, result.mnc)
        if signature in seen:
            # Not uniquely identifiable versus an already-eligible cell.
            ineligible.append(Ineligible(result.cell_key,
                                         REASON_SCELL_NOT_UNIQUE))
            continue

        seen.add(signature)
        eligible.append(result)

    return eligible, ineligible
