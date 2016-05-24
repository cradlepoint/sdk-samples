"""
handle NMEA sentences
"""
import time
import calendar


class NmeaStatus(object):
    """
    Hold the state of a connected NMEA device.

    We assume the sentences come in a cluster, and some of the sentences
    contain duplicate values.

    So the paradigm is:
    1) call NmeaStatus.start() to prep the new data
    2) call NmeaStatus.parse_sentence() repeatedly
    3) call NmeaStatus.publish() to 'end' the parsing of data

    """
    TIMESTAMP = 'time'
    UTC_TIME = 'gps_utc'
    VALID = 'valid'
    LATITUDE = 'lat'
    LONGITUDE = 'long'
    LAT_DDMM = 'lat_ddmm'
    LONG_DDMM = 'long_ddmm'
    ALTITUDE = 'alt'
    SPEED_KNOTS = 'knots'
    SPEED_KMH = 'kmh'
    COURSE_TRUE = 'course'
    SATELLITES = 'num_sat'
    RAW_DATE = 'raw_date'
    RAW_TIME = 'raw_time'

    DEF_DATE_TIME = False
    DEF_SPEED = True
    DEF_ALTITUDE = False
    DEF_COOR_DDMM = False
    DEF_COOR_DEC = True

    def __init__(self):

        # if True, calc time.time() like value from GSP, else omit
        self.date_time = self.DEF_DATE_TIME

        # if True, calc speed over ground, else omit
        self.speed = self.DEF_SPEED

        # if True, calc altitude, else omit
        self.altitude = self.DEF_ALTITUDE

        # decide which of the coordinates to use
        # coor_ddmm is the string "DDMM.M"
        self.coor_ddmm = self.DEF_COOR_DDMM
        # coor_dec is float in degrees
        self.coor_dec = self.DEF_COOR_DEC

        self._last_valid = None
        self._attrib = dict()
        self.__hold = None

        return

    def __getitem__(self, key):
        return self._attrib[key]

    def __setitem__(self, key, value):
        self._attrib[key] = value

    def start(self, now=None):
        """
        Start parsing a new cluster of sentences

        :param float now: force in a time-stamp, mainly for testing
        :return:
        """
        assert self.__hold is None

        self.__hold = dict()

        if now is None:
            now = time.time()
        self.__hold[self.TIMESTAMP] = now
        return

    def publish(self):
        """
        End parsing a cluster of sentences - discard the older data and
        shift the new data into its place

        :return:
        """
        if self._attrib.get(self.VALID, False):
            # then current readings are valid, so SAVE
            self._last_valid = self._attrib
        # else, do not 'lose' the last valid or None

        self._attrib = self.__hold
        self.__hold = None
        return

    def get_attributes(self):
        return self._attrib

    def parse_sentence(self, sentence):
        """

        :param str sentence:
        :return:
        """
        if self.__hold is None:
            raise ValueError("NMEA object not properly started!")

        sentence, seen_csum = strip_sentence(sentence)

        # confirm is already a valid-looking sentence
        if seen_csum is None:
            raise ValueError("Invalid NMEA sentence - lacks checksum")

        if seen_csum != calc_checksum(sentence):
            raise ValueError("Invalid NMEA checksum")

        tokens = sentence.split(',')
        if len(tokens) <= 1:
            raise ValueError("Bad NMEA format")

        result = False
        if tokens[0] == "GPRMC":
            # recommended minimum standard
            result = self.parse_rmc(tokens)

        elif tokens[0] == "GPVTG":
            # recommended minimum standard
            result = self.parse_vtg(tokens)

        elif tokens[0] == "GPGGA":
            # Global Positioning System Fixed Data
            result = self.parse_gga(tokens)

        return result

    def parse_rmc(self, tokens):
        """
        Recommended minimum standard

        GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2,
            020516,0.0,E,A

        :param list tokens:
        :return:
        """
        if len(tokens) < 9:
            raise ValueError("NMEA RMC is too short.")
        assert tokens[0] == "GPRMC"

        if tokens[2] == 'A':
            # then is valid
            self.__hold[self.VALID] = True
        else:
            self.__hold[self.VALID] = False
            return False

        # always do the lat/long
        if self.LATITUDE not in self.__hold:
            self._parse_latitude(tokens[3], tokens[4])
        if self.LONGITUDE not in self.__hold:
            self._parse_longitude(tokens[5], tokens[6])

        if self.date_time:
            # then parse in the date/time
            # tokens[1] = HHMMSS.ss, like '222227.0' - we'll discard the msec
            # tokens[9] = DDMMYY, like '020516'
            # so make like "020516T22227.0"

            value = tokens[9] + tokens[1][:6]
            value = time.strptime(value, "%d%m%y%H%M%S")
            """ :type value: time.struct_time """
            self.__hold[self.UTC_TIME] = calendar.timegm(value)

        if self.speed:
            # SPEED_KNOTS = 'knots', SPEED_KMH = 'kmh'
            self.__hold[self.SPEED_KNOTS] = float(tokens[7])
            if len(tokens[8]):
                self.__hold[self.COURSE_TRUE] = float(tokens[8])
            else:
                self.__hold[self.COURSE_TRUE] = 0.0

        return True

    def parse_vtg(self, tokens):
        """
        GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A

        :param list tokens:
        :return:
        """
        if not self.speed:
            # ignore this data
            return True

        if len(tokens) < 8:
            raise ValueError("NMEA VTG is too short.")

        assert tokens[0] == "GPVTG"

        if self.COURSE_TRUE not in self.__hold:
            self.__hold[self.COURSE_TRUE] = float(tokens[1])

        if self.SPEED_KNOTS not in self.__hold:
            self.__hold[self.SPEED_KNOTS] = float(tokens[5])

        if self.SPEED_KMH not in self.__hold:
            self.__hold[self.SPEED_KMH] = float(tokens[7])

        return True

    def parse_gga(self, tokens):
        """
        Global Positioning System Fixed Data

        GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A

        :param list tokens:
        :return:
        """
        if len(tokens) < 8:
            raise ValueError("NMEA VTG is too short.")

        assert tokens[0] == "GPGGA"

        # only do the lat/long is missing
        if self.LATITUDE not in self.__hold:
            self._parse_latitude(tokens[2], tokens[3])
        if self.LONGITUDE not in self.__hold:
            self._parse_longitude(tokens[4], tokens[5])

        # always do the number of satellites
        self.__hold[self.SATELLITES] = int(tokens[7])

        if self.altitude:
            self.__hold[self.ALTITUDE] = float(tokens[9])

        return True

    def _parse_latitude(self, latitude, north):
        """
        Parse the 2 fields: latitude and N/S indicator

        GPS returns as ddmm.mmm, or 'degree & decimal minutes'

        :param str latitude:
        :param str north:
        :return:
        """

        # LATITUDE = 'lat_dec'
        # LONGITUDE = 'long_dec'
        #  = 'lat_ddmm'
        # LONG_DDMM = 'long_ddmm'

        if self.coor_ddmm:
            # then leave as DDMM.MMMMMM string
            if north == 'S':
                # 'N' is +, 'S' is negative
                self.__hold[self.LAT_DDMM] = '-' + latitude
            else:
                self.__hold[self.LAT_DDMM] = latitude

        if self.coor_dec:
            # do the conversion
            assert latitude[4] == '.'
            value = float(latitude[:2]) + float(latitude[2:]) / 60.0
            if north == 'S':
                # 'N' is +, 'S' is negative
                value = -value
            self.__hold[self.LATITUDE] = value

        return

    def _parse_longitude(self, longitude, west):
        """
        Parse the 2 fields: longitude and W/E indicator

        GPS returns as dddmm.mmm, or 'degree & decimal minutes'

        :param str longitude:
        :param str west:
        :return:
        """

        if self.coor_ddmm:
            # then leave as DDDMM.MMMMMM string
            if west == 'W':
                # 'E' is +, 'W' is negative
                self.__hold[self.LONG_DDMM] = '-' + longitude
            else:
                self.__hold[self.LONG_DDMM] = longitude

        # LATITUDE = 'lat_dec'
        # LONGITUDE = 'long_dec'
        # LAT_DDMM = 'lat_ddmm'
        #  = 'long_ddmm'

        if self.coor_dec:
            # do the conversion
            assert longitude[5] == '.'
            value = float(longitude[:3]) + float(longitude[3:]) / 60.0
            if west == 'W':
                # 'E' is +, 'W' is negative
                value = -value
            self.__hold[self.LONGITUDE] = value
        return


def strip_sentence(sentence):
    """
    Given an NMEA sentence, which may (or may not) have a checksum attached,
    strip down to raw sentence and optional checksum (None if none attached)

    We assume the 'sentence' might be like this:
    "$GPRMC,222247.0,A,4500.8,N,09320.0,W,0.0,353.2,020516,0.0,E,A*1F\r\n"

    Or it might merely be:
    "GPRMC,222247.0,A,4500.8,N,09320.0,W,0.0,353.2,020516,0.0,E,A"

    :param str sentence:
    :return:
    """
    if isinstance(sentence, bytes):
        # convert bytes to str
        source = sentence.decode()

    if not isinstance(sentence, str):
        raise TypeError("NMEA sentence must be type(string)")

    # chop off any white-space, such as trailing \r\n
    sentence = sentence.strip()
    seen_csum = None

    if sentence[0] == '$':
        # then assume is a fully formed NMEA sentence
        offset = sentence.find('*')
        if offset >= 0:
            seen_csum = int(sentence[offset+1:], 16)
            sentence = sentence[1:offset]
        else:
            sentence = sentence[1:]

    return sentence, seen_csum


def calc_checksum(sentence):
    """
    Given an NMEA sentence, which may (or may not) have a checksum attached,
    calculate what the checksum SHOULD be.

    We assume the 'sentence' might be like this:
    "$GPRMC,222247.0,A,4500.8,N,09320.0,W,0.0,353.2,020516,0.0,E,A*1F\r\n"

    Or it might merely be:
    "GPRMC,222247.0,A,4500.8,N,09320.0,W,0.0,353.2,020516,0.0,E,A"

    :param sentence:
    :return:
    """
    if not isinstance(sentence, str):
        raise TypeError("NMEA sentence must be type(string)")

    if sentence[0] == '$':
        # chop off any formatting, as we want the raw sentence only!
        sentence, seen_csum = strip_sentence(sentence)

    csum = 0
    for c in sentence:
        # XOR each new char one by one
        csum ^= ord(c)

    return csum


def validate_checksum(sentence):
    """
    Given an NMEA sentence, which we assume is already valid form,
    confirm the as-seen checksum is valid
    "$GPRMC,222247.0,A,4500.8,N,09320.0,W,0.0,353.2,020516,0.0,E,A*1F\r\n"

    :param sentence:
    :return:
    """
    # chop off any white-space, such as trailing \r\n
    sentence, seen_csum = strip_sentence(sentence)

    # confirm is already a valid-looking sentence
    if seen_csum is None:
        raise ValueError("Invalid NMEA sentence - lacks checksum")

    calc_csum = calc_checksum(sentence)
    return bool(seen_csum == calc_csum)


def wrap_sentence(sentence):
    """
    Given a raw NMEA sentence, add the CRC and delimiters

    If sentence starts with '$', then assume is already okay

    :param str sentence:
    :return:
    """
    if not isinstance(sentence, str):
        raise TypeError("NMEA sentence must be type(string)")

    if sentence[0] == '$':
        return sentence

    csum = calc_checksum(sentence)

    sentence = '$' + sentence + '*' + "%02X" % csum + '\r\n'
    return sentence


def fix_time_sentence(sentence, new_time=None):
    """
    Given an NMEA sentence, if the TYPE is known and it contains UTC TIME or
    DATE, we wish to swap out the values in the sentence and calc new checksum

    At present we only handle:
    - GPGGA, token[1]=UTC Time, there is no Date
    - GPRMC, token[1]=UTC Time, token[9]=Date

    UTC time is form HHMMSS.SSS in 24-hour format
    Date is form DDMMYY

    :param str sentence:
    :param float new_time: new UTC time to use; if None, use now (time.time())
    :return:
    """

    def _form_date_time(now):
        """take a time.time() and return the new strings"""
        if now is None:
            now = time.time()

        if not isinstance(now, time.struct_time):
            now = time.gmtime(now)

        # as HHMMSS.SS, but chop msec off since our msec are not likely valid
        _time = time.strftime("%H%M%S.0", now)

        # as DDMMYY
        _date = time.strftime("%d%m%y", now)

        return _date, _time

    final_form = bool(sentence[0] == "$")

    if final_form:
        # chop off any white-space, such as trailing \r\n
        work, seen_csum = strip_sentence(sentence)

    else:
        work = sentence

    if work.startswith("GPGGA"):
        tokens = work.split(',')

        # change UTC time in tokens[1]
        utc_date, utc_time = _form_date_time(new_time)
        # print("GGA: time, old:{} new{}".format(tokens[1], utc_time))
        tokens[1] = utc_time

        work = ','.join(tokens)
        sentence = None

    elif work.startswith("GPRMC"):
        tokens = work.split(',')

        # change UTC time in tokens[1]
        utc_date, utc_time = _form_date_time(new_time)
        # print("RMC: time, old:{} new{}".format(tokens[1], utc_time))
        tokens[1] = utc_time

        # change Date in tokens[9]
        # print("RMC: date, old:{} new{}".format(tokens[9], utc_date))
        tokens[9] = utc_date

        work = ','.join(tokens)
        sentence = None

    else:
        print("unknown:{}".format(work))

    if sentence is None:
        # then we may need to recreate, as we changed
        if final_form:
            # then add the format again
            sentence = wrap_sentence(work)
        else:
            # leave unwrapped
            sentence = work

    return sentence

