"""
Helper function to parse a time durations; use '3 hr' or '15 min' instead
of mind-bending settings such as 10800 and 900 seconds
"""

from parse_data import parse_float, parse_integer

__version__ = "1.0.0"

# History:
#
# 1.0.0: 2015-Apr Lynn
#        * initial rewrite
#


class TimeDuration(object):
    """
    Helper class to process user settings such as "3 hr" or "5 min", rather
    than demanding a setting like 900 sec

    It handles basically 2 classes of data:
    1) lone token must be a numeric in seconds, so 5 or " 5" means 5 seconds.
    2) time tag in the set ('sec', 'ms', 'min', 'hr', 'day', 'mon', 'yr')
       decorates so "5 min" becomes 900 sec

    In addition, one can add a + or -, so "-5 min" means -900 seconds. This
    can be used to trigger an even before the hour, such once an hour plus
    "-5 min" means at minute = 55 of the hour.

    One can also decorate with UTC, Z, or GM. This rarely affects the seconds,
    but can be used by callers to as example trigger something every 12 hours
    based on UTC (or local).

    """

    DURATION_SECOND = 0
    DURATION_MSEC = 1
    DURATION_MINUTE = 2
    DURATION_HOUR = 3
    DURATION_DAY = 4
    DURATION_MONTH = 5
    DURATION_YEAR = 6
    DURATION_NAME_LIST = ('sec', 'ms', 'min', 'hr', 'day', 'mon', 'yr')
    DURATION_FROM_SECS = (1.0, 1000.0, 1/60.0, 1/3600.0, 1/86400.0, None, None)
    DURATION_TO_SECS = (1.0, 0.001, 60.0, 3600.0, 86400.0, None, None)

    DURATION_TAG_TO_MSEC = {
        DURATION_MSEC: 1,
        DURATION_SECOND: 1000,
        DURATION_MINUTE: 60000,
        DURATION_HOUR: 3600000,
        DURATION_DAY: 86400000,
        # no Month or Year due to variable days-per-month and leap-years
        # DURATION_MONTH: 0,
        # DURATION_YEAR: 0
    }

    FORMAT_FLOAT = "%0.2f %s"
    FORMAT_INT = "%d %s"

    def __init__(self, source=None):
        self.period_code = self.DURATION_SECOND
        self.period_value = 0
        self.seconds = None
        self.utc = None
        self.format = self.FORMAT_INT

        if source is not None:
            self.parse_time_duration_to_seconds(source)
        return

    def reset(self):
        self.period_code = self.DURATION_SECOND
        self.period_value = 0
        self.seconds = None
        self.utc = None
        self.format = self.FORMAT_INT
        return

    def get_period_as_string(self):
        """
        :return: return the formatted STRING of the period, such as "5 min"
        :rtype: str
        """
        # TODO - add the UTC support, and what about sign?
        # print "period_value:%s type=%s" % (self.period_value,
        #                                    type(self.period_value))
        # print " period_code:%s type=%s" % (self.period_code,
        #                                    type(self.period_code))
        return self.format % (self.period_value,
                              self.DURATION_NAME_LIST[self.period_code])

    def get_tag_as_string(self, tag=None):
        """
        :return: return the simple STRING tag of the period, so
                 if DURATION_MINUTE, return "min"
        :rtype: str
        """
        if tag is None:
            tag = self.period_code

        elif not isinstance(tag, int):
            raise TypeError("Duration enum must be between 0 and 6")

        elif not (self.DURATION_SECOND <= tag <= self.DURATION_YEAR):
            raise ValueError("Duration enum must be between 0 and 6")

        return self.DURATION_NAME_LIST[tag]

    def get_seconds(self):
        """
        :return: return the seconds in thi period, or ValueError if no
                 seconds (such as for month or year)
        :rtype: int or float
        """
        if self.seconds is None:
            raise ValueError("get_seconds() impossible for period:%s" %
                             self.get_tag_as_string())
        return self.seconds

    def parse_time_duration_to_seconds(self, source, delimiter=None):
        """
        Parse a given time duration into a specified unit of measure.

        Supports integer, float, and string input. String input will be split
        into a list and parsed if necessary.

        The in/out type must be in ['ms', 'sec', 'min', 'hr', 'day']
        'mon' and 'year' NOT supported

        :param source: the source duration to be parsed, which might be 10,
                       or '10 min' or '10 min utc'
        :type source: int, str, bytes
        :param delimiter: allows using ',' or other tag delimiter. If None,
                          use space (' ')
        :type delimiter: str or None
        :return: seconds as float
        :rtype: float
        """

        if isinstance(source, int) or isinstance(source, float):
            # _tracer.info('is number, so just return SAME type')
            self.period_code = self.DURATION_SECOND
            self.period_value = source
            self.seconds = source
            return self.seconds

        if isinstance(source, bytes):
            # make bytes into string
            source = source.decode()

        # get rid of any leading/trailing spaces
        source = source.strip().lower()

        # this should be one of three forms
        # 1) "60" which is already seconds
        # 2) "60 min", which is a number plus the time tag
        # 3) "60 min utz", which adds a time-zone tag
        if delimiter is None:
            delimiter = ' '
        elements = source.split(delimiter)

        # see if LAST token is UTC decoration - this examines the LAST
        # space-delimited token
        self.utc = self._decode_utc_element(elements[-1])
        if self.utc:
            # if True, pop off the last item in elements
            elements.pop()

        self._decode_a_pair(elements)

        return self.seconds

    def _decode_a_pair(self, pair):
        """
        Given a two-element list such as ['5', 'sec'] or (10, 'min'), with
        the second element in the set:
            ['ms', 'sec', 'min', 'hr', 'day', 'mon', 'yr'].

        :param pair: two-element list such as ['5', 'sec'] or (10, 'min')
        :type pair: list
        :return: adjusts 'self' if okay, else throws exception
        :rtype: None
        """
        if len(pair) < 1:
            raise ValueError(
                "_decode_a_pair() requires at least 1 element in list")

        if pair[0].find('.') >= 0:
            # then is a float
            self.period_value = parse_float(pair[0])
            self.format = self.FORMAT_FLOAT
        else:
            self.period_value = parse_integer(pair[0])
            self.format = self.FORMAT_INT

        if len(pair) > 1:
            # obtain period code, like DURATION_SECOND or DURATION_HOUR
            self.period_code = self.decode_time_tag(pair[1])
        else:
            self.period_code = self.DURATION_SECOND

        # obtain the number, convert to seconds
        if self.DURATION_TO_SECS[self.period_code] is None:
            # for Month/Year, there are no 'seconds'
            self.seconds = None
        else:
            # else calc seconds from 2 'period values' (10 minutes = 600 sec)
            self.seconds = self.period_value * \
                           self.DURATION_TO_SECS[self.period_code]

        # print "period_code:%s type=%s" % (self.period_code,
        #                                   type(self.period_code))
        return True

    @staticmethod
    def _decode_utc_element(utc):
        """
        Given a source string, such as '5 day' (etc), check for a
        UTC/Z/Zulu/uct/gm tag (not case sensitive).
        We assume the tag is the LAST space-delimited token in the string

        So these strings all return True:
        * 'utc', 'min zulu', '2 hr utc', 'silly funny 5 crap utc'

        So these strings all return False:
        * '', 'min', '2 hr', 'silly funny 5 crap'

        :param utc: string like "hour" or "utc"
        :type utc: str
        :return: True if UTC was indicated, else is False
        :rtype: bool
        """
        if isinstance(utc, str):
            utc = utc.lower()
            if utc.endswith('z'):
                return True
            if utc.endswith('utc'):
                return True
            if utc.endswith('gm'):
                return True
            if utc.endswith('uct'):
                return True
            if utc.endswith('zulu'):
                return True
        return False

    def decode_time_tag(self, source):
        """
        :param source: source string
        :type source: str
        :return: int code for the period
        :rtype: int
        """
        if not isinstance(source, str):
            raise TypeError("decode_time_tag(%s) requires STRING, not %s" %
                            (str(source), type(source)))

        # only check if we seem to have something
        source = source.lower() + '   '
        source = source[:3]  # first 3 char only

        if source == 'sec':  # then sec, secs, second, seconds
            return self.DURATION_SECOND

        elif source == 'min':  # then min, mins, minute, minutes
            return self.DURATION_MINUTE

        elif source in ('hr ', 'hrs', 'hou'):  # then hr, hrs, hour, hours
            return self.DURATION_HOUR

        elif source in ('dy ', 'dys', 'day'):  # then d, dy, dys, day, days
            return self.DURATION_DAY

        elif source in ('mse', 'ms ', 'mil'):  # then ms, msec, millis...
            return self.DURATION_MSEC

        elif source in ('mn ', 'mon'):  # then special for Month
            return self.DURATION_MONTH

        elif source in ('yr ', 'yea'):  # then special for YEAR
            return self.DURATION_YEAR

        raise ValueError('decode_time_tag(%s) unknown string source' % source)
