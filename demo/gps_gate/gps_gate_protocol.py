"""
Received GPS, assuming the router's GPS function sends new data (sentences)
to a localhost port
"""
import copy

import cp_lib.gps_nmea as gps_nmea
from demo.gps_gate.gps_gate_nmea import NmeaCollection
from cp_lib.parse_data import clean_string, parse_integer
from cp_lib.split_version import split_version_string


class GpsGate(object):

    DEF_CLIENT_USERNAME = None
    DEF_CLIENT_PASSWORD = None
    DEF_CLIENT_IMEI = None
    DEF_SERVER_MAJOR_VERSION = 1
    DEF_SERVER_MINOR_VERSION = 1

    # update these 2 as you desire
    # DEF_TRACKER_NAME = "Cradlepoint SDK"
    DEF_TRACKER_NAME = "GpsGate TrackerOne"
    DEF_CLIENT_NAME = "Cradlepoint"
    DEF_CLIENT_VERSION = "1.0"

    OPT_USE_ONLY_TCP = False

    DEF_GPS_GATE_URL = 'online.gpsgate.com'
    DEF_GPS_GATE_PORT = 30175
    DEF_GPS_GATE_TRANSPORT = 'tcp'

    # our small state-machine
    STATE_OFFLINE = 'offline'
    STATE_TRY_LOGIN = 'login'
    STATE_HAVE_SESSION = 'session'
    STATE_WAIT_SERVER_VERSION = 'wait_ver'
    STATE_HAVE_SERVER_VERSION = 'have_ver'
    STATE_ASK_UPDATE = 'update'
    STATE_FORWARD_READY = 'ready'
    STATE_FORWARDING = 'forwarding'

    def __init__(self, _logger):
        self.client_username = self.DEF_CLIENT_USERNAME
        self.client_password = self.DEF_CLIENT_PASSWORD
        self.client_imei = self.DEF_CLIENT_IMEI
        self.server_major_version = self.DEF_SERVER_MAJOR_VERSION
        self.server_minor_version = self.DEF_SERVER_MINOR_VERSION
        self.tracker_name = self.DEF_TRACKER_NAME
        self.client_name = self.DEF_CLIENT_NAME
        self.client_version = self.DEF_CLIENT_VERSION

        self.gps_gate_url = self.DEF_GPS_GATE_URL
        self.gps_gate_port = self.DEF_GPS_GATE_PORT
        self.gps_gate_transport = self.DEF_GPS_GATE_TRANSPORT

        self.state = self.STATE_OFFLINE
        self.session = None
        self.server_title = None
        self.return_as_bytes = True

        self.logger = _logger

        # hold the NMEA data and filter-states to drive uploading
        self.nmea = NmeaCollection(_logger)
        return

    def reset(self):
        """

        :return:
        """
        self.state = self.STATE_OFFLINE
        self.session = None
        return

    def get_next_client_2_server(self):
        """
        A simple state machine, as defined in GpsGateServerProtocol200.pdf
        on page 18 of 26

        :return:
        """
        self.logger.debug("get_next() entry state:{}".format(self.state))

        if self.state == self.STATE_OFFLINE:
            # then we're first starting
            message = self.form_frlin()
            self.state = self.STATE_TRY_LOGIN

        elif self.state == self.STATE_TRY_LOGIN:
            # hmm, we shouldn't still be here, but start again
            message = self.form_frlin()
            self.logger.warning("stuck in LOGIN state?")

        elif self.state == self.STATE_HAVE_SESSION:
            # we sent login; server replied with session
            # we should send our version expectations
            message = self.form_frver()
            self.state = self.STATE_WAIT_SERVER_VERSION

        elif self.state == self.STATE_WAIT_SERVER_VERSION:
            # hmm, we shouldn't still be here, but start again
            message = self.form_frver()
            self.logger.warning("stuck in WAIT SERVER VERSION state?")

        elif self.state == self.STATE_HAVE_SERVER_VERSION:
            # ask the server for update rules
            message = self.form_frcmd_update()
            self.state = self.STATE_ASK_UPDATE

        elif self.state == self.STATE_FORWARD_READY:
            # we sent our version, server replied its version
            message = self.form_frwdt()
            self.state = self.STATE_FORWARDING

        else:
            self.logger.error("unexpected state:{}".format(self.state))
            self.state = self.STATE_OFFLINE
            message = None

        self.logger.debug("get_next() exit state:{}".format(self.state))

        if self.return_as_bytes:
            message = message.encode()

        return message

    def parse_message(self, source):
        """
        Feed in RESPONSES from GpsGate

        :param source:
        :return:
        """
        if isinstance(source, bytes):
            source = source.decode()

        # source MIGHT be more than one messages!
        # source = '$FRVAL,TimeFilter,60.0*42\r\n$FRVAL,SpeedFilter,2.8*' +
        #          '0C\r\n$FRVAL,DirectionFilter,30.0*37\r\n$FRVAL,' +
        #          'DirectionThreshold,10.0*42\r\n'
        tokens = source.split('\n')

        result = True
        for one in tokens:
            if len(one) > 0:
                if not self._parse_one_message(one):
                    result = False

        return result

    def _parse_one_message(self, source):
        """

        :param source:
        :return:
        """
        # clean off the data
        sentence, seen_csum = gps_nmea.strip_sentence(source)

        if seen_csum is not None:
            # then we had one, check it
            calc_csum = gps_nmea.calc_checksum(sentence)
            if seen_csum != calc_csum:
                raise ValueError(
                    "Bad NMEA checksum, saw:%02X expect:%02X" %
                    (seen_csum, calc_csum))

        # self.logger.debug("checksum={}".format(seen_csum))

        # break up the sentence
        tokens = sentence.split(',')

        if tokens[0] == "FRVAL":
            # setting a name-space value
            result = self._parse_frval(tokens)

        elif tokens[0] == "FRRET":
            # we have a command response
            result = self._parse_frret(tokens)

        elif tokens[0] == "FRSES":
            # we have a session!
            result = self._parse_frses(tokens)

        elif tokens[0] == "FRVER":
            # we have the server version
            result = self._parse_frver(tokens)

        # elif tokens[0] == "FRERR":
        #     # we have a server error
        #     result = self._parse_frerr(tokens)
        #     # '$FRERR,AuthError,Wrong username or password*56\r\n'
        #
        else:
            raise ValueError("Unknown response:{}".format(source))

        return result

    def get_my_identifier(self):
        """

        :return:
        """
        if self.client_imei is not None:
            return self.client_imei
        return self.client_name

    def get_frcmd_id(self, value: str):
        """

        :return:
        """
        return "FRCMD," + self.get_my_identifier() + "," + value

    def get_frret_id(self, value: str):
        """

        :return:
        """
        return "FRRET," + self.get_my_identifier() + "," + value

    def set_username(self, value: str):
        """
        Set the user-name used with GpsGate Server. There don't seem to
        be any 'rules' about what makes a valid user-name.

        Insure is string, remove extra quotes, etc.
        """
        value = clean_string(value)
        if self.client_username != value:
            self.client_username = value
            self.logger.info("GpsGate: Setting user name:{}".format(value))

    def set_password(self, value):
        """make string, remove extra quotes, etc"""
        value = clean_string(value)
        if self.client_password != value:
            self.client_password = value
            self.logger.info("GpsGate: Setting new PASSWORD:****")

    def set_imei(self, value):
        """make string, remove extra quotes, etc"""
        value = clean_string(value)
        if self.client_imei != value:
            self.client_imei = value
            self.logger.info("GpsGate: Setting IMEI:{}".format(value))

    def set_client_name(self, name: str, version=None):
        """
        Set client name. if version is none, then we assume name is like
        "my tool 1.4" 7 try to parse off the ending float.

        TODO At the moment, this routine assumes version is like x.y, with y
        being only 1 digit. So 1.2 is okay, but 1.22 is not
        """
        change = False

        name = clean_string(name)
        if version is None:
            # assume version is on end of name!
            name = name.split(' ')
            if len(name) <= 1:
                # then is a single work/token - assume version 1.0
                version = 1.0
                name = name[0]
            else:
                if name[-1].find('.') >= 0:
                    version = name[-1]
                    name.pop(-1)
                else:
                    version = 1.0
                name = ' '.join(name)

        if isinstance(version, int):
            version = float(version)

        if isinstance(version, float):
            version = str(version)

        if self.client_name != name:
            self.client_name = name
            change = True

        if self.client_version != version:
            self.client_version = version
            change = True

        if change and self.logger is not None:
            self.logger.info(
                "GpsGate: Setting client name:{} version:{}".format(
                    self.client_name, self.client_version))

    def set_server_version(self, value):
        """
        make string, remove extra quotes, etc. We assume will be like '1.1'
        so we need to split into 2 ints for GpsGate protocol
        """
        major, minor = split_version_string(value)
        if major != self.server_major_version or \
                minor != self.server_minor_version:
            self.server_major_version = major
            self.server_minor_version = minor
            self.logger.info(
                "GpsGate: Setting server version:%d.%d" % (major, minor))

    def set_server_url(self, value):
        """save the GpsGate server URL"""
        value = clean_string(value)
        if self.gps_gate_url != value:
            self.gps_gate_url = value
            self.logger.info("GpsGate: Setting Server URL:{}".format(value))

    def set_server_port(self, value):
        """save the GpsGate server port"""
        value = parse_integer(value)
        if self.gps_gate_port != value:
            self.gps_gate_port = value
            self.logger.info("GpsGate: Setting Server port:{}".format(value))

    def set_server_transport(self, value):
        """save the GpsGate server transport - ('tcp' or 'xml')"""
        value = clean_string(value).lower()
        if self.gps_gate_transport != value:
            if value == 'xml':
                raise NotImplementedError("GpsGate XML transport - not yet")
            elif value != 'tcp':
                raise ValueError("GpsGate - only TCP transport supported")
            self.gps_gate_transport = value
            self.logger.info("GpsGate: Setting Transport:{}".format(value))

    def form_frcmd_reset(self):
        """
        $FRCMD,IMEI,_DeviceReset

        The return is wrapped with the NMEA checksum

        :return:
        :rtype: str
        """
        return gps_nmea.wrap_sentence(self.get_frcmd_id("_Device_Reset"))

    @staticmethod
    def form_frcmd_update():
        """
        Request server's update rules

        :return:
        :rtype: str
        """
        return copy.copy("$FRCMD,,_getupdaterules,Inline*1E")

    def form_frcmd_imei(self, gps: dict):
        """
        <-- TrackerOne to GpsGate Server GPRS or SMS
        $FRCMD,IMEI,_SendMessage,,latitude,hemi,longitude,hemi,alt,
        speed,heading,date,time,valid

        The return is wrapped with the NMEA checksum

        :return:
        :rtype: str
        """
        if not isinstance(gps, dict):
            raise TypeError("Invalid GPS INFO type")

        sentence = self.get_frcmd_id("_SendMessage")

        try:
            lat = float(gps[gps_nmea.NmeaStatus.LATITUDE])
            if lat < 0.0:
                lat_h = 'S'
            else:
                lat_h = 'N'

            long = float(gps[gps_nmea.NmeaStatus.LONGITUDE])
            if long < 0.0:
                long_h = 'W'
            else:
                long_h = 'E'

            sentence += "%f,%s,%f,%s," % (lat, lat_h, long, long_h)

        except KeyError:
            raise ValueError()

        # these are optional
        alt = gps.get(gps_nmea.NmeaStatus.ALTITUDE, 0.0)
        speed = gps.get(gps_nmea.NmeaStatus.SPEED_KNOTS, 0.0)
        heading = gps.get(gps_nmea.NmeaStatus.COURSE_TRUE, "")
        raw_date = gps.get(gps_nmea.NmeaStatus.RAW_DATE, "")
        raw_time = gps.get(gps_nmea.NmeaStatus.RAW_TIME, "")
        sentence += "%f,%f,%s,%s,%s" % (alt, speed, heading,
                                        raw_date, raw_time)

        sentence = gps_nmea.wrap_sentence(sentence)
        return sentence

    def form_frlin(self, force_imei=True):
        """
        Form the $FRLIN sentence, assuming the SELF values are valid:
        * self.server_major_version
        * self.server_minor_version
        * self.client_name_version

        The return is wrapped with the NMEA checksum

        :return:
        :rtype: str
        """

        if not force_imei and self.client_username is not None:
            # we prefer the username - when set!
            if not isinstance(self.client_username, str):
                raise ValueError("FRLIN Error: user name is not string")
            if not isinstance(self.client_password, str):
                raise ValueError("FRLIN Error: password is not string")
            sentence = "FRLIN,,{0},{1}".format(
                self.client_username,
                self._encrypt_password(self.client_password))
        else:
            if not isinstance(self.client_imei, str):
                raise ValueError("FRLIN Error: IMEI is not string")
            sentence = "FRLIN,IMEI,{0},".format(self.client_imei)
        sentence = gps_nmea.wrap_sentence(sentence)
        return sentence

    def form_frret_imei(self):
        """
        Form the $FRRET,IMEI response for server

        The return is wrapped with the NMEA checksum

        :return:
        :rtype: str
        """
        sentence = self.get_frret_id(
            "_GprsSettings") + ",,{0},{1},{2}".format(
            self.DEF_TRACKER_NAME, self.client_name, self.client_version)

        if self.OPT_USE_ONLY_TCP:
            sentence += ",tcp"
        sentence = gps_nmea.wrap_sentence(sentence)
        return sentence

    def form_frver(self):
        """
        Form the $FRVER sentence, assuming the SELF values are valid:
        * self.server_major_version
        * self.server_minor_version
        * self.client_name_version

        The return is wrapped with the NMEA checksum

        :return:
        :rtype: str
        """
        sentence = "FRVER,{0},{1},{2} {3}".format(
            self.server_major_version, self.server_minor_version,
            self.client_name, self.client_version)
        sentence = gps_nmea.wrap_sentence(sentence)
        return sentence

    @staticmethod
    def form_frwdt():
        """
        Start our NMEA forwarding - is fixed message. We return a COPY just
        to prevent someone doing something wonky to 'the original', like
        make lower case or affect NMEA wrapping

        :return:
        :rtype: str
        """
        return copy.copy('$FRWDT,NMEA*78')

    def _parse_frret(self, tokens):
        """
        Parse a server response cms

        :param list tokens:
        :return:
        """
        if len(tokens) < 4:
            raise ValueError("FRRET is too short.")

        assert tokens[0] == "FRRET"

        # we'll ignore the user name or context

        value = tokens[2].lower()

        if value == '_getupdaterules':
            # then this is server's response to our update query
            if self.state == self.STATE_ASK_UPDATE:
                # then expected
                self.state = self.STATE_FORWARD_READY

            else:  # then unexpected!
                self.logger.warning(
                    "Unexpected FRRET _getupdaterules response")

            # ignore - not sure the significance
            # value = tokens[3].lower()
            # if value != 'nmea':
            #     self.logger.warning(
            #         "FRRET: Unexpected server major number, saw:" +
            #         "{} expect:{}".format(value, self.server_major_version))

        else:
            self.logger.warning("FRRET: Unexpected cmd:{}".format(value))
            return False

        return True

    def _parse_frses(self, tokens):
        """
        Parse the SESSION response from server

        :param list tokens:
        :return:
        """
        if len(tokens) < 2:
            raise ValueError("FRSES is too short.")

        assert tokens[0] == "FRSES"

        if self.state == self.STATE_TRY_LOGIN:
            # then expected
            self.state = self.STATE_HAVE_SESSION

        else:  # then unexpected!
            if self.logger is not None:
                self.logger.warning("Unexpected FRSES response")

        self.session = tokens[1]
        if self.logger is not None:
            self.logger.debug(
                "Recording server SESSION:{}".format(self.session))
        return True

    def _parse_frval(self, tokens):
        """
        Parse a value in our name-space

        FRVAL,DistanceFilter,500.0

        :param list tokens:
        :return:
        """
        if len(tokens) < 3:
            raise ValueError("FRVAL is too short.")

        assert tokens[0] == "FRVAL"

        name = tokens[1].lower()

        if name == "distancefilter":
            self.nmea.set_distance_filter(tokens[2])

        elif name == "timefilter":
            self.nmea.set_time_filter(tokens[2])

        elif name == "speedfilter":
            self.nmea.set_speed_filter(tokens[2])

        elif name == "directionfilter":
            self.nmea.set_direction_filter(tokens[2])

        elif name == "directionthreshold":
            self.nmea.set_direction_threshold(tokens[2])

        return True

    def _parse_frver(self, tokens):
        """
        Parse the SESSION response from server

        :param list tokens:
        :return:
        """
        if len(tokens) < 4:
            raise ValueError("FRVER is too short.")

        assert tokens[0] == "FRVER"

        if self.state == self.STATE_WAIT_SERVER_VERSION:
            # then expected
            self.state = self.STATE_HAVE_SERVER_VERSION

        else:  # then unexpected!
            self.logger.warning("Unexpected FRVER response")

        value = parse_integer(tokens[1])
        if value != self.server_major_version:
            self.logger.warning(
                "FRVER: Unexpected server major number, saw:" +
                "{} expect:{}".format(value, self.server_major_version))
            self.server_major_version = value

        value = parse_integer(tokens[2])
        if value != self.server_minor_version:
            self.logger.warning(
                "FRVER: Unexpected server minor number, saw:" +
                "{} expect:{}".format(value, self.server_minor_version))
            self.server_minor_version = value

        self.server_title = tokens[3]
        self.logger.debug(
            "Recording server TITLE:{}".format(self.server_title))
        return True

    @staticmethod
    def _encrypt_password(value: str):
        """
        Do the simple adjustment per spec

        Encryption sample: "coolness" -> "HHVMOLLX"

        :param value:
        :return:
        """
        assert isinstance(value, str)
        result = ""

        for ch in value:
            i = ord(ch)
            if '0' <= ch <= '9':
                # result += (9 - (i - '0') + '0')
                result += chr(9 - (i - 48) + 48)

            elif 'a' <= ch <= 'z':
                # (char)(('z' - 'a') - (c - 'a') + 'A'))
                result += chr(25 - (i - 97) + 65)

            elif 'A' <= ch <= 'Z':
                # (char)(('Z' - 'A') - (c - 'A') + 'a'));
                result += chr(25 - (i - 65) + 97)

        # use extended slice to reverse string
        return result[::-1]
