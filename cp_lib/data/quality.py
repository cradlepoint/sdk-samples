# File: quality.py
# Desc: manage the quality bits, tags, and names

__version__ = "1.0.0"

# History:
#
# 1.0.0: 2015-Mar Lynn
#       * initial draft, new design
#
#

"""
The data samples:
"""

# lowest 8 bits define 'BadData' - generally hardware errors, disabled etc
# such data is probably meaningless; for example a '0' reading of a broken
# sensor doesn't mean it is zero (0) degrees outside
QUALITY_NO_SUPPORTED = 0x00000000   # no support, value is meaningless

QUAL_DISABLE = 0x00000001       # source is disabled
QUAL_FAULT = 0x00000002         # low-level HW fault; device specific
QUAL_OFFLINE = 0x00000004       # source is unavailable, offline, etc)
QUAL_NOT_INIT = 0x00000008      # the data has never been set
QUAL_OVER_RANGE = 0x00000010    # above permitted range-of-operation
QUAL_UNDER_RANGE = 0x00000020   # below permitted range-of-operation
QUAL_RES_BD = 0x00000040        # (reserved)
QUAL_VALID = 0x00000080         # status is valid if 1
QUAL_BAD_DATA = 0x0000007F      # these are internal data alarms

QUAL_QUAL_UNK = 0x00000100      # data is of unknown quality
QUAL_QUAL_LOW = 0x00000200      # data is of known low quality
QUAL_MANUAL = 0x00000400        # at least 1 input is in Manual mode
QUAL_CLAMP_HIGH = 0x00001000    # was forced high due to system fault
QUAL_CLAMP_LOW = 0x00002000     # was forced low due to system fault
QUAL_SOSO_DATA = 0x00003700     # internal process 'conditions'

QUAL_DIGITAL = 0x00010000  # digital NOT in desired state
QUAL_RES_AL = 0x00020000   # (reserved)
QUAL_LO = 0x00040000       # normal/expected low alarm (warning)
QUAL_LOLO = 0x00080000     # abnormal/unexpected too-low alarm (err)
QUAL_ROC_NOR = 0x00100000  # normal/expected rate-of-change alarm
QUAL_ROC_AB = 0x00200000   # abnormal/unexpected rate-of-change alarm
QUAL_HI = 0x00400000       # normal/expected high alarm (warning)
QUAL_HIHI = 0x00800000     # abnormal/unexpected too-high alarm (err)
QUAL_DEV_NOR = 0x01000000  # normal/expected deviation alarm (warning)
QUAL_DEV_AB = 0x02000000   # abnormal/unexpected deviation alarm (err)
QUAL_ALARMS = 0x0FFF0000   # These are External Process Alarms

QUAL_ABNORM = 0x10000000  # first sample after go to alarm
QUAL_RTNORM = 0x20000000  # first sample after a return to normal
QUAL_RES_EV = 0x40000000  # (reserved)

QUAL_ALL_BITS = 0x7FFFFFFF  # handle py 3.x when all int or long

QUALITY_GOOD = QUAL_VALID
QUALITY_BAD = QUAL_BAD_DATA

QUALITY_DEFAULT_ALARM_BITS = (QUAL_FAULT | QUAL_OFFLINE |
                              QUAL_OVER_RANGE |
                              QUAL_UNDER_RANGE | QUAL_ALARMS)

QUALITY_DEFAULT_EVENT_BITS = (QUAL_MANUAL | QUAL_RTNORM |
                              QUAL_ABNORM)

QUALITY_TAG_TO_BIT = {
    'dis': QUAL_DISABLE, 'flt': QUAL_FAULT,
    'ofl': QUAL_OFFLINE,
    'ovr': QUAL_OVER_RANGE, 'udr': QUAL_UNDER_RANGE,
    'N/A': QUAL_NOT_INIT, 'n/a': QUAL_NOT_INIT,
    'unq': QUAL_QUAL_UNK, 'loq': QUAL_QUAL_LOW,
    'man': QUAL_MANUAL, 'clh': QUAL_CLAMP_HIGH,
    'cll': QUAL_CLAMP_LOW, 'dig': QUAL_DIGITAL,
    'low': QUAL_LO, 'llo': QUAL_LOLO,
    'roc': QUAL_ROC_NOR, 'rab': QUAL_ROC_AB,
    'hig': QUAL_HI, 'hhi': QUAL_HIHI,
    'dev': QUAL_DEV_NOR, 'dab': QUAL_DEV_AB,
    'abn': QUAL_ABNORM, 'rtn': QUAL_RTNORM,
    'ok': QUAL_VALID
}

QUALITY_SHORT_NAME = {
    QUAL_DISABLE: 'dis', QUAL_FAULT: 'flt',
    QUAL_OFFLINE: 'ofl',
    QUAL_OVER_RANGE: 'ovr', QUAL_UNDER_RANGE: 'udr',
    QUAL_NOT_INIT: 'N/A',
    QUAL_QUAL_UNK: 'unq', QUAL_QUAL_LOW: 'loq',
    QUAL_MANUAL: 'man', QUAL_CLAMP_HIGH: 'clh',
    QUAL_CLAMP_LOW: 'cll', QUAL_DIGITAL: 'dig',
    QUAL_LO: 'low', QUAL_LOLO: 'llo',
    QUAL_ROC_NOR: 'roc', QUAL_ROC_AB: 'rab',
    QUAL_HI: 'hig', QUAL_HIHI: 'hhi',
    QUAL_DEV_NOR: 'dev', QUAL_DEV_AB: 'dab',
    QUAL_ABNORM: 'abn', QUAL_RTNORM: 'rtn',
    QUAL_VALID: 'ok',
}

QUALITY_FULL_NAME = {
    QUAL_DISABLE: 'disabled', QUAL_FAULT: 'fault',
    QUAL_OFFLINE: 'offline', QUAL_NOT_INIT: 'not-initialized',
    QUAL_OVER_RANGE: 'over-range',
    QUAL_UNDER_RANGE: 'under-range',
    QUAL_QUAL_UNK: 'unknown-quality',
    QUAL_QUAL_LOW: 'low-quality',
    QUAL_MANUAL: 'manual', QUAL_CLAMP_HIGH: 'clamp-high',
    QUAL_CLAMP_LOW: 'clamp-low', QUAL_DIGITAL: 'digital',
    QUAL_LO: 'low', QUAL_LOLO: 'low-low',
    QUAL_ROC_NOR: 'rate-of-change',
    QUAL_ROC_AB: 'rate-of-change-abnorm',
    QUAL_HI: 'high', QUAL_HIHI: 'high-high',
    QUAL_DEV_NOR: 'deviation',
    QUAL_DEV_AB: 'deviation-abnormal',
    QUAL_ABNORM: 'go-abnormal',
    QUAL_RTNORM: 'return-to-normal',
    QUAL_VALID: 'status-valid',
}


def one_bit_to_tag(bit: int):
    """Given a single bit-mask, return the tag/mnemonic"""
    if bit in QUALITY_SHORT_NAME:
        return QUALITY_SHORT_NAME[bit]
    raise ValueError("one_bit_to_tag({0}) - bit matches no tag".format(bit))


def one_bit_to_name(bit: int):
    """Given a single bit-mask, return the long name"""
    if bit in QUALITY_FULL_NAME:
        return QUALITY_FULL_NAME[bit]
    raise ValueError("one_bit_to_name({0}) - bit matches no tag".format(bit))


def all_bits_to_tag(bits: int, long_name=False):
    """Cycle through all bits, returning a tag/mnemonic string"""

    if not (bits & QUAL_VALID):
        raise ValueError("all_bits_to_tag(0x%X) - lacks VALID bit tag" % bits)

    if bits == QUAL_VALID:
        if long_name:
            return "status-valid"
        else:
            return "ok"

    # else at least one bit is true, so continue
    tag_string = ''
    n = 1
    first = True
    while n & QUAL_ALL_BITS:
        if (bits & n) and (n != QUAL_VALID):
            # then this bit is true, so add the tag
            # but skip adding 'ok' tag!
            if long_name:
                tag = one_bit_to_name(n)
            else:
                tag = one_bit_to_tag(n)
            if tag is not None:
                if first:
                    first = False
                    tag_string = tag
                else:
                    tag_string += ',' + tag
        # cycle through all the bits.
        #   On 32-bit, will go zero after 0x80000000, so while cond not true
        #   On 64-bit/py 3.x, will go to 0x100000000, so while cond not true
        n <<= 1
    return tag_string


def clr_quality_tags(quality: int, tag):
    """
    Use the 3-ch tags to clear some bits

    :param int quality: the bits to mask in
    :param tag: the short or tag name
    :type tag: str, tuple, or list
    :rtype: int
    """
    if not isinstance(quality, int):
        raise TypeError("clr_quality_tags() quality must be int type")

    quality |= QUAL_VALID

    if isinstance(tag, str):
        # if a string was passed in, clear this one bit
        quality &= ~tag_to_one_bit(tag)

    else:
        try:
            # if a list was passed in, we cycle through the list clearing
            # each tag one by one
            for one_tag in tag:
                quality = clr_quality_tags(quality, one_tag)

        except:  # any other situation is an error
            raise TypeError("clr_quality_tags({0}) - invalid tags".format(tag))

    return quality


def set_quality_tags(quality, tag):
    """
    Use the 3-ch tags to set some bits

    :param int quality: the bits to mask in
    :param tag: the short or tag name
    :type tag: str, tuple, or list
    :rtype: int
    """
    if not isinstance(quality, int):
        raise TypeError("set_quality_tags() quality must be int type")

    quality |= QUAL_VALID

    if isinstance(tag, str):
        # if a string was passed in, clear this one bit
        quality |= tag_to_one_bit(tag)

    else:
        try:
            # if a list was passed in, we cycle through the list setting
            # each tag one by one
            for one_tag in tag:
                quality = set_quality_tags(quality, one_tag)

        except:  # any other situation is an error
            raise TypeError("set_quality_tags({0}) - invalid tags".format(tag))

    return quality


def tag_to_one_bit(tag):
    """
    Given string short (or tag) name, return alarm mask
    :param str tag: the short or tag name
    :rtype: int
    """
    if isinstance(tag, str):
        tag = tag.lower()
        if tag in QUALITY_TAG_TO_BIT:
            return QUALITY_TAG_TO_BIT[tag]

    raise ValueError("tag_to_one_bit({0}) - tag not valid".format(tag))
