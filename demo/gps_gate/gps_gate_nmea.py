"""
handle NMEA sentences, in ways customized to Gpsgate expectations

This file is used by demo.gps_gate.gps_gate_protocol.py!
"""
import time

from cp_lib.parse_data import parse_float


class NmeaCollection(object):
    """
    Hold the state of a connected NMEA device.

    We assume the sentences come in a cluster, and some of the sentences
    contain duplicate values.

    So the paradigm is:
    1) call NmeaCollection.start() to prep the new data
    2) call NmeaCollection.parse_sentence() repeatedly
    3) call NmeaCollection.end() to 'end' the parsing of data & test filters
       if end() returns True, then there has been enough of a change to
       warrant uploading
    4) call NmeaCollection.publish() to formalize (confirm) we've uploaded

    """

    # if True, then just claim an out-of-range setting, don't ignore
    CLAMP_SETTINGS = True

    DISTANCE_FILTER_DEF = None
    # at some point, GPS is not accurate enough to be like 1 inch! And for
    # MAX, roughly 1/2 way around earth is probably silly
    DISTANCE_FILTER_LIMITS = (1.0, 6000000.0, "distance")

    TIME_FILTER_DEF = "1 min"
    # at most each 10 seconds (not too fast) and at least once a day
    TIME_FILTER_LIMITS = (10.0, 86400.0, "time")

    SPEED_FILTER_DEF = None
    # at most each 10 seconds (not too fast) and at least once a day
    SPEED_FILTER_LIMITS = (1.0, 500.0, "speed")

    DIRECTION_FILTER_DEF = None
    # direction/degrees limited to 0 to 360
    DIRECTION_FILTER_LIMITS = (1.0, 360.0, "direction")

    DIRECTION_THRESHOLD_DEF = None
    # like distance
    DIRECTION_THRESHOLD_LIMITS = (1.0, 6000000.0, "direction threshold")

    def __init__(self, _logger):

        # hold the last RMC data
        self.gprmc = dict()

        # hold the last VYG data
        self.gpvtg = dict()

        # hold the last GGA data
        self.gpgga = dict()

        self.publish_time = None

        self.new_data = dict()
        self.last_data = None
        self.publish_reason = None

        self.logger = _logger

        # Distance in meters before a new update should be sent to server.
        self.distance_filter = None
        self.set_distance_filter(self.DISTANCE_FILTER_DEF)

        # Interval in seconds before a new position should be sent to server
        self.time_filter = None
        self.set_time_filter(self.TIME_FILTER_DEF)

        # Change in speed in meters per second, before a new position update
        # should sent to server by client.
        self.speed_filter = None
        self.set_speed_filter(self.SPEED_FILTER_DEF)

        # Change of heading in degrees, before a new update should be sent.
        self.direction_filter = None
        self.set_direction_filter(self.DIRECTION_FILTER_DEF)

        # Distance in meters travelled before "DirectionFilter" is considered.
        self.direction_threshold = None
        self.set_direction_threshold(self.DIRECTION_THRESHOLD_DEF)

        return

    def set_distance_filter(self, value=None):
        """
        Distance in meters before a new update should be sent to server.

        Distance must be > 0.0, and although logically it should not be
        too large, I'm not sure what MAX would be.
        """
        # test None, make float, test Min/Max, clamp or throw ValueError
        value = self._test_value_limits(value, self.DISTANCE_FILTER_LIMITS)

        if value is None:
            # then disable the distance filter
            self.distance_filter = None
            self.logger.debug("Disable distance_filter")
        elif value != self.distance_filter:
                self.distance_filter = value
                self.logger.debug("Set distance_filter = {} m".format(value))
        return

    def set_time_filter(self, value):
        """
        Interval in seconds before a new position should be sent to server
        """
        from cp_lib.parse_duration import TimeDuration

        # handle the "null" or 0 times, as disable
        value = self._test_value_as_none(value)

        if value is None:
            # then disable the distance filter
            if self.time_filter is not None:
                self.logger.debug("Disable time_filter")
            self.time_filter = None
        else:
            try:
                duration = TimeDuration(value)
            except AttributeError:
                raise ValueError("Bad Time Filter Value:{}".format(value))

            value = duration.get_seconds()

            # test Min/Max, clamp or throw ValueError
            value = self._test_value_limits(value, self.TIME_FILTER_LIMITS)
            if value != self.time_filter:
                self.time_filter = value
                self.logger.debug("Set time_filter = {} sec".format(value))
        return

    def set_speed_filter(self, value):
        """
        Change in speed in meters per second, before a new position update
        should sent to server.
        """
        # test None, make float, test Min/Max, clamp or throw ValueError
        value = self._test_value_limits(value, self.SPEED_FILTER_LIMITS)

        if value is None:
            # then disable the distance filter
            if self.speed_filter is not None:
                self.logger.debug("Disable speed_filter")
            self.speed_filter = None
        elif value != self.speed_filter:
            self.speed_filter = value
            self.logger.debug("Set speed_filter = {} m/sec".format(value))
        return

    def set_direction_filter(self, value):
        """
        Change in direction in degrees, before a new position update
        should sent to server .
        """
        # test None, make float, test Min/Max, clamp or throw ValueError
        value = self._test_value_limits(value, self.DIRECTION_FILTER_LIMITS)

        if value is None:
            # then disable the distance filter
            if self.direction_filter is not None:
                self.logger.debug("Disable direction_filter")
            self.direction_filter = None
        elif value != self.direction_filter:
            self.direction_filter = value
            self.logger.debug("Set direction_filter = {} deg".format(value))
        return

    def set_direction_threshold(self, value):
        """
        Distance in meters travelled before "DirectionFilter" should be
        considered.
        """
        # test None, make float, test Min/Max, clamp or throw ValueError
        value = self._test_value_limits(value, self.DIRECTION_THRESHOLD_LIMITS)

        if value is None:
            # then disable the distance filter
            if self.direction_threshold is not None:
                self.logger.debug("Disable direction_threshold")
            self.direction_threshold = None
        else:
            if value != self.direction_threshold:
                self.direction_threshold = value
                self.logger.debug(
                    "NMEA.set_direction_threshold = {} m".format(value))
        return

    @staticmethod
    def _test_value_as_none(value):
        """
        give a value, which might be float or string (etc) but in our
        context of 'filters' we want to disable or set None
        :param value:
        :return:
        """
        if value in (None, 0, 0.0):
            # none of the filters are usable if '0'
            return None

        if isinstance(value, bytes):
            # make any string bytes
            value = value.decode()

        if isinstance(value, str):
            if value.lower() in ("", "0", "0.0", "none", "null"):
                # none of the filters are usable if '0'
                return None

        return value

    def _test_value_limits(self, value, limits):
        """
        We assume 'limits' is like (min, max, name), so confirm the value in
        within range. If CLAMP is true, we claim to MIN or MAX, else we
        throw ValueError

        :param value: the value to test - like float
        :param tuple limits:
        :return:
        """
        assert isinstance(limits, tuple)
        assert len(limits) >= 3

        value = self._test_value_as_none(value)
        if value is None:
            return None

        value = parse_float(value)

        if value < limits[0]:
            # value is too low
            if self.CLAMP_SETTINGS:
                return limits[0]
            else:
                raise ValueError(
                    "Set {} filter={} is below MIN={}".format(
                        limits[2], value, limits[0]))

        if value > limits[1]:
            # too high
            if self.CLAMP_SETTINGS:
                return limits[1]
            else:
                raise ValueError(
                    "Set {} filter={} is above MAX={}".format(
                        limits[2], value, limits[1]))

        # if still here, then is within range
        return value

    def start(self, now=None):
        """
        Start parsing a new cluster of sentences

        :param float now: force in a time-stamp, mainly for testing
        :return:
        """
        if now is None:
            now = time.time()

        self.new_data = dict()
        self.new_data['time'] = now
        return

    def end(self):
        """
        End parsing a cluster of sentences, so check out filters

        :return: (T/F, reason string)
        :rtype: bool, str
        """

        if not self.new_data.get('valid', False):
            # test if new_data is valid - for now never publish is RMC is bad
            # at some point likely need to publish as 'bad'
            return False, 'invalid'

        # we use self.filtered to RECORD if there are any filters, or not.
        filtered = False
        result = False
        reason = "error"

        if self.last_data is None or self.last_data == {}:
            # if no last data, a special case
            self.last_data = self.new_data
            return True, "first"

        # place the filter tests in roughly order of computational complexity

        if self.time_filter is not None:
            # Interval in seconds before a new data should be sent to server
            filtered = True
            if self._test_time_filter():
                result = True
                reason = "time"

        if not result and self.speed_filter is not None:
            # Change in speed in meters per second
            # we only test if result isn't True yet
            filtered = True
            if self._test_speed_filter():
                result = True
                reason = "speed"

        if not result and self.distance_filter is not None:
            # Distance in meters before a new update should be sent to server
            # we only test if result isn't True yet
            filtered = True
            if self._test_distance_filter():
                result = True
                reason = "distance"

        if not result and self.direction_filter is not None:
            # Change of heading in degrees, before new update sent.
            # we only test if result isn't True yet
            filtered = True
            if self._test_direction_filter():
                result = True
                reason = "direction"

        # self.direction_threshold is handled within _test_direction_filter()

        if not result:
            # if still here, one of two situations were true
            if filtered:
                # a) we have filter conditions, but NONE wanted to publish
                # result is already False
                reason = "filtered"
            else:
                # b) we have NO filter conditions, so always publish
                result = True
                reason = "always"
        # else result == True, so assume 'reason' is valid already

        return result, reason

    def publish(self, now=None):
        """
        End parsing a cluster of sentences - discard the older data and
        shift the new data into its place

        :param float now: force in a time-stamp, mainly for testing
        :return:
        """
        # else, do not 'lose' the last valid or None

        if now is None:
            now = time.time()

        if self.new_data.get("valid", False):
            # only save if last was valid!
            self.last_data = self.new_data

        self.publish_time = now
        return True

    def report_list(self):
        """
        return a list of 'details' for a report
        :return:
        """
        report = []
        if self.time_filter is not None:
            report.append("Time Filter = %0.2f sec" % float(self.time_filter))
        if self.speed_filter is not None:
            report.append(
                "Speed Filter = %0.2f m/sec" % float(self.speed_filter))
        if self.distance_filter is not None:
            report.append(
                "Distance Filter = %0.1f m" % float(self.distance_filter))
        if self.direction_filter is not None:
            report.append(
                "Direction Filter = %0.1f deg" % float(self.direction_filter))
            if self.direction_threshold is not None:
                report.append(
                    "Direction Threshold = %0.1f m" % float(
                        self.direction_threshold))

        if 'raw' in self.gprmc:
            report.append(self.gprmc['raw'])
        if 'raw' in self.gprmc:
            report.append(self.gpvtg['raw'])
        if 'raw' in self.gprmc:
            report.append(self.gpgga['raw'])

        if self.new_data.get('valid', False):
            report.append("Newest: Lat:%f Long:%f Alt:%0.1f m" %
                          (self.new_data['latitude'],
                           self.new_data['longitude'],
                           self.new_data['altitude']))
            report.append(
                "Newest: time:%s satellite_count:%d" %
                (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime(self.new_data['time'])),
                 self.new_data['satellites']))
        else:
            report.append("Newest Data is invalid!")

        if self.publish_time is None:
            report.append("Never Published")
        else:
            report.append(
                "Last Publish:%s (%d seconds ago)" %
                (time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime(self.publish_time)),
                 time.time() - self.publish_time))

        return report

    def parse_sentence(self, raw_sentence):
        """

        :param str raw_sentence:
        :return:
        """
        from cp_lib.gps_nmea import strip_sentence, calc_checksum

        sentence, seen_csum = strip_sentence(raw_sentence)

        if seen_csum is not None:
            if seen_csum != calc_checksum(sentence):
                raise ValueError("Invalid NMEA checksum")

        tokens = sentence.split(',')
        if len(tokens) <= 1:
            raise ValueError("Bad NMEA format")

        # index = 0
        # for x in tokens:
        #     print("[%02d]=%s" % (index, x))
        #     index += 1

        result = False
        if tokens[0] == "GPRMC":
            # recommended minimum standard
            result = self.parse_rmc(tokens, raw_sentence)

        elif tokens[0] == "GPVTG":
            # recommended minimum standard
            result = self.parse_vtg(tokens, raw_sentence)

        elif tokens[0] == "GPGGA":
            # Global Positioning System Fixed Data
            result = self.parse_gga(tokens, raw_sentence)

        return result

    def parse_rmc(self, tokens, raw_sentence):
        """
        Recommended minimum standard

        GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2,
            020516,0.0,E,A

        :param list tokens:
        :param str raw_sentence:
        :return:
        """
        if len(tokens) < 9:
            raise ValueError("NMEA RMC is too short.")
        assert tokens[0] == "GPRMC"

        self.gprmc = dict()
        self.gprmc['time'] = time.time()
        self.gprmc['raw'] = raw_sentence
        self.gprmc['tokens'] = tokens

        if tokens[2] == 'A':
            # then is valid
            self.new_data['valid'] = True
        else:
            self.new_data['valid'] = False
            return False

        # convert to full decimal
        if 'latitude' not in self.new_data:
            self.new_data['latitude'] = self._parse_latitude(
                tokens[3], tokens[4])

        if 'longitude' not in self.new_data:
            self.new_data['longitude'] = self._parse_longitude(
                tokens[5], tokens[6])

        if 'knots' not in self.new_data:
            # self.new_data['knots'] = float(tokens[7])
            # 0.514444444 × Vkn = Vm/sec
            self.new_data['mps'] = float(tokens[7]) * 0.514444444

        if 'course' not in self.new_data and len(tokens[8]):
            # if null, is unknown
            self.new_data['course'] = float(tokens[8])

        return True

    def parse_vtg(self, tokens, raw_sentence):
        """
        GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A

        :param list tokens:
        :param str raw_sentence:
        :return:
        """
        if len(tokens) < 8:
            raise ValueError("NMEA VTG is too short.")

        assert tokens[0] == "GPVTG"

        self.gpvtg = dict()
        self.gpvtg['time'] = time.time()
        self.gpvtg['raw'] = raw_sentence
        self.gpvtg['tokens'] = tokens

        if 'course' not in self.new_data and len(tokens[1]):
            # if null, is unknown
            self.new_data['course'] = float(tokens[1])

        if 'knots' not in self.new_data:
            self.new_data['knots'] = float(tokens[5])
            # 0.514444444 × Vkn = Vm/sec
            self.new_data['mps'] = self.new_data['knots'] * 0.514444444

        return True

    def parse_gga(self, tokens, raw_sentence):
        """
        Global Positioning System Fixed Data

        GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A

        :param list tokens:
        :param str raw_sentence:
        :return:
        """
        if len(tokens) < 8:
            raise ValueError("NMEA GGA is too short.")

        assert tokens[0] == "GPGGA"

        self.gpgga = dict()
        self.gpgga['time'] = time.time()
        self.gpgga['raw'] = raw_sentence
        self.gpgga['tokens'] = tokens

        # convert to full decimal
        if 'latitude' not in self.new_data:
            self.new_data['latitude'] = self._parse_latitude(
                tokens[2], tokens[3])

        if 'longitude' not in self.new_data:
            self.new_data['longitude'] = self._parse_longitude(
                tokens[4], tokens[5])

        # always do the number of satellites
        if 'satellites' not in self.new_data:
            self.new_data['satellites'] = int(tokens[7])

        if 'altitude' not in self.new_data:
            self.new_data['altitude'] = float(tokens[9])

        return True

    @staticmethod
    def _parse_latitude(latitude, north):
        """
        Parse the 2 fields: latitude and N/S indicator

        GPS returns as ddmm.mmm, or 'degree & decimal minutes'

        :param str latitude:
        :param str north:
        :rtype: float
        """
        assert latitude[4] == '.'
        value = float(latitude[:2]) + float(latitude[2:]) / 60.0
        if north == 'S':
            # 'N' is +, 'S' is negative
            value = -value

        return value

    @staticmethod
    def _parse_longitude(longitude, west):
        """
        Parse the 2 fields: longitude and W/E indicator

        GPS returns as dddmm.mmm, or 'degree & decimal minutes'

        :param str longitude:
        :param str west:
        :return:
        :rtype: float
        """
        assert longitude[5] == '.'
        value = float(longitude[:3]) + float(longitude[3:]) / 60.0
        if west == 'W':
            # 'E' is +, 'W' is negative
            value = -value
        return value

    @staticmethod
    def _distance_meters(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)

        :param float lon1: first longitude (as decimal degrees)
        :param float lat1: first latitude (as decimal degrees)
        :param float lon2: second longitude (as decimal degrees)
        :param float lat2: second latitude (as decimal degrees)
        :return float: distance in meters
        """
        from math import radians, cos, sin, sqrt, atan2

        # convert decimal degrees to radians, use haversine formula
        diff_lon = radians(lon2 - lon1)
        diff_lat = radians(lat2 - lat1)
        a = sin(diff_lat / 2) * sin(diff_lat / 2) + cos(radians(lat1)) \
            * cos(radians(lat2)) * sin(diff_lon / 2) * sin(diff_lon / 2)
        # c = 2 * asin(sqrt(a))
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        km = 6371 * c
        return km * 1000.0

    def _test_time_filter(self):
        """
        Interval in seconds before a new data should be sent to server

        :return:
        """
        if 'time' in self.new_data and 'time' in self.last_data:
            delta = self.new_data['time'] - self.last_data['time']
            # print("Time Filter={} sec; delta={}".format(self.time_filter,
            #                                             delta))
            if delta >= self.time_filter:
                return True

        # else if either value missing, skip!
        return False

    def _test_distance_filter(self):
        """
        Distance in meters before a new update should be sent to server

        :return:
        """
        delta = self.__get_raw_distance()
        print("Distance Filter={} meters; delta={}".format(
            self.distance_filter, delta))
        if delta is not None and delta >= self.distance_filter:
            return True

        # else if either value missing, skip!
        return False

    def __get_raw_distance(self):
        """
        Warp test, confirming all required data exists

        :return:
        """
        if 'longitude' in self.new_data and 'latitude' in self.new_data and \
                'longitude' in self.last_data and \
                'latitude' in self.last_data:
            return self._distance_meters(
                self.new_data['longitude'], self.new_data['latitude'],
                self.last_data['longitude'], self.last_data['latitude'])

        # else if either value missing, skip!
        return None

    def _test_speed_filter(self):
        """
        Change in speed in meters per second

        :return:
        """
        if 'mps' in self.new_data and 'mps' in self.last_data:
            delta = abs(self.new_data['mps'] - self.last_data['mps'])
            print("Speed Filter={} mps; delta={}".format(
                self.speed_filter, delta))
            if delta >= self.speed_filter:
                return True

        # else if either value missing, skip!
        return False

    def _test_direction_filter(self):
        """
        Change in speed in meters per second

        :return:
        """
        if 'course' in self.new_data and 'course' in self.last_data:
            # Change of heading in degrees, before new update sent.

            # handle left or right course change, for example turn 10 deg
            # one way can be seen as 350 degrees the other way!
            if self.new_data['course'] > self.last_data['course']:
                delta = self.new_data['course'] - self.last_data['course']
            else:
                delta = self.last_data['course'] - self.new_data['course']
            delta = min(delta, 360 - delta)
            print("Direction Filter={}; delta={}".format(
                self.direction_filter, delta))
            if delta < self.direction_filter:
                # then won't apply, not enough change
                return False

            # else MIGHT apply, check the threshold
            if self.direction_threshold is not None:
                # Distance in meters travelled before "DirectionFilter"
                # should be considered.
                delta = self.__get_raw_distance()
                print("Directional Distance Threshold={}; delta={}".format(
                    self.distance_filter, delta))
                if delta < self.direction_threshold:
                    # have not travelled far enough
                    return False

            # had enough change, and threshold is null or satisfied
            return True

        return False
