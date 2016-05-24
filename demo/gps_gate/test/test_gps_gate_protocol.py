# Test the gps.gps_gate.gps_gate_protocol module

import unittest

import demo.gps_gate.gps_gate_protocol as protocol


class TestGpsGateProtocol(unittest.TestCase):

    def test_sets(self):
        global base_app

        print("")  # skip paste '.' on line

        base_app.logger.info("TEST set of client details")

        tests = [
            {'inp': '', 'out': ''},
            {'inp': 'User1', 'out': 'User1'},
            {'inp': '  User2 ', 'out': 'User2'},
            {'inp': '\"User3\"', 'out': 'User3'},
            {'inp': '\'User4\'', 'out': 'User4'},
            {'inp': b'', 'out': ''},
            {'inp': b'User1', 'out': 'User1'},
            {'inp': b'  User2 ', 'out': 'User2'},
            {'inp': b'\"User3\"', 'out': 'User3'},
            {'inp': b'\'User4\'', 'out': 'User4'},
            {'inp': None, 'out': TypeError},
            {'inp': 10, 'out': TypeError},
            {'inp': 100.998, 'out': TypeError},
        ]

        obj = protocol.GpsGate(base_app.logger)
        self.assertIsNone(obj.client_username)
        self.assertIsNone(obj.client_password)
        self.assertIsNone(obj.client_imei)

        for test in tests:

            if test['out'] == TypeError:
                with self.assertRaises(TypeError):
                    obj.set_username(test['inp'])
                with self.assertRaises(TypeError):
                    obj.set_password(test['inp'])
                with self.assertRaises(TypeError):
                    obj.set_imei(test['inp'])

            else:
                obj.set_username(test['inp'])
                self.assertEqual(obj.client_username, test['out'])
                obj.set_password(test['inp'])
                self.assertEqual(obj.client_password, test['out'])
                obj.set_imei(test['inp'])
                self.assertEqual(obj.client_imei, test['out'])

        base_app.logger.info("TEST set of client name")
        tests = [
            {'name_in': 'My Tools', 'ver_in': '9.3',
             'name_out': 'My Tools', 'ver_out': '9.3'},
            {'name_in': 'My Toes', 'ver_in': 7.8,
             'name_out': 'My Toes', 'ver_out': '7.8'},
            {'name_in': 'My Nose', 'ver_in': 14,
             'name_out': 'My Nose', 'ver_out': '14.0'},
            {'name_in': 'Boss', 'ver_in': 13.25,
             'name_out': 'Boss', 'ver_out': '13.25'},
            {'name_in': 'Tammy Gears 7.2', 'ver_in': None,
             'name_out': 'Tammy Gears', 'ver_out': '7.2'},
            {'name_in': 'Ziggy', 'ver_in': None,
             'name_out': 'Ziggy', 'ver_out': '1.0'},
            {'name_in': 'Tammy Gears 9 8.1', 'ver_in': None,
             'name_out': 'Tammy Gears 9', 'ver_out': '8.1'},
            {'name_in': 'Tammy Gears two 4.3', 'ver_in': None,
             'name_out': 'Tammy Gears two', 'ver_out': '4.3'},
            {'name_in': 'Tammy Gears two', 'ver_in': None,
             'name_out': 'Tammy Gears two', 'ver_out': '1.0'},
        ]

        # start with defaults
        self.assertEqual(obj.client_name, obj.DEF_CLIENT_NAME)
        self.assertEqual(obj.client_version, obj.DEF_CLIENT_VERSION)

        for test in tests:
            obj.set_client_name(test['name_in'], test['ver_in'])
            self.assertEqual(obj.client_name, test['name_out'])
            self.assertEqual(obj.client_version, test['ver_out'])

        base_app.logger.info("TEST set of server URL, Port, and Transport")
        tests = [
            {'in': 'gps.linse.org', 'out': 'gps.linse.org'},
            {'in': '\"web.linse.org\"', 'out': 'web.linse.org'},
        ]

        # start with defaults
        self.assertEqual(obj.gps_gate_url, obj.DEF_GPS_GATE_URL)

        for test in tests:
            obj.set_server_url(test['in'])
            self.assertEqual(obj.gps_gate_url, test['out'])

        tests = [
            {'in': '9999', 'out': 9999},
            {'in': 8824, 'out': 8824},
        ]

        # start with defaults
        self.assertEqual(obj.gps_gate_port, obj.DEF_GPS_GATE_PORT)

        for test in tests:
            obj.set_server_port(test['in'])
            self.assertEqual(obj.gps_gate_port, test['out'])

        tests = [
            {'in': 'tcp', 'out': 'tcp'},
            {'in': 'TCP', 'out': 'tcp'},
            {'in': 'Tcp', 'out': 'tcp'},
            {'in': 'silly', 'out': ValueError},
            {'in': 'xml', 'out': NotImplementedError},
        ]

        # start with defaults
        self.assertEqual(obj.gps_gate_transport, obj.DEF_GPS_GATE_TRANSPORT)

        for test in tests:
            if test['out'] == ValueError:
                with self.assertRaises(ValueError):
                    obj.set_server_transport(test['in'])
            elif test['out'] == NotImplementedError:
                with self.assertRaises(NotImplementedError):
                    obj.set_server_transport(test['in'])
            else:
                obj.set_server_transport(test['in'])
                self.assertEqual(obj.gps_gate_transport, test['out'])

        return

    def test_frlin(self):
        global base_app

        print("")  # skip paste '.' on line
        base_app.logger.info("TEST FRLIN")

        obj = protocol.GpsGate(base_app.logger)
        self.assertIsNone(obj.client_username)
        self.assertIsNone(obj.client_password)
        self.assertIsNone(obj.client_imei)

        # a simple encryption test using sample in the spec
        expect = "HHVMOLLX"
        result = obj._encrypt_password("coolness")
        self.assertEqual(result, expect)

        with self.assertRaises(ValueError):
            # since user name is None
            obj.form_frlin()

        obj.set_username("cradlepoint")
        with self.assertRaises(ValueError):
            # since password is None
            obj.form_frlin()

        obj.set_password("Billy6Boy")
        result = obj.form_frlin()
        expect = '$FRLIN,,cradlepoint,BLy3BOORy*2F\r\n'
        self.assertEqual(result, expect)

        with self.assertRaises(ValueError):
            # since imei is None
            obj.form_frlin(force_imei=True)

        obj.set_imei("353547060660845")
        result = obj.form_frlin()
        expect = '$FRLIN,,cradlepoint,BLy3BOORy*2F\r\n'
        self.assertEqual(result, expect)

        result = obj.form_frlin(force_imei=True)
        expect = '$FRLIN,IMEI,353547060660845,*47\r\n'
        self.assertEqual(result, expect)

        return

    def test_frret_imei(self):
        global base_app

        print("")  # skip paste '.' on line
        base_app.logger.info("TEST FRRET IMEI")

        obj = protocol.GpsGate(base_app.logger)
        self.assertEqual(obj.tracker_name, obj.DEF_TRACKER_NAME)
        self.assertEqual(obj.client_name, obj.DEF_CLIENT_NAME)
        self.assertEqual(obj.client_version, obj.DEF_CLIENT_VERSION)

        # a simple encryption test using sample in the spec
        expect = '$FRRET,Cradlepoint,_GprsSettings,,GpsGate TrackerOne,' +\
                 'Cradlepoint,1.0*7B\r\n'
        result = obj.form_frret_imei()
        self.assertEqual(result, expect)

        return

    def test_frver(self):
        global base_app

        print("")  # skip paste '.' on line
        base_app.logger.info("TEST FRVER")

        obj = protocol.GpsGate(base_app.logger)

        # a simple encryption test using sample in the spec
        expect = '$FRVER,1,1,Cradlepoint 1.0*27\r\n'
        result = obj.form_frver()
        self.assertEqual(result, expect)

        return

    def test_parse_frval(self):
        global base_app

        print("")  # skip paste '.' on line
        base_app.logger.info("TEST FRVAL")

        obj = protocol.GpsGate(base_app.logger)

        self.assertIsNone(obj.nmea.distance_filter)
        source = "$FRVAL,DistanceFilter,500.0*67"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.distance_filter, 500.0)

        source = "$FRVAL,DistanceFilter,200.0"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.distance_filter, 200.0)

        source = "FRVAL,DistanceFilter,100.0"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.distance_filter, 100.0)

        self.assertIsNone(obj.nmea.time_filter)
        source = "$FRVAL,TimeFilter,60.0*42"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.time_filter, 60.0)

        self.assertIsNone(obj.nmea.direction_filter)
        source = "$FRVAL,DirectionFilter,40.0*30"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.direction_filter, 40.0)

        self.assertIsNone(obj.nmea.direction_threshold)
        source = "$FRVAL,DirectionThreshold,10.0*42"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.direction_threshold, 10.0)

        self.assertIsNone(obj.nmea.speed_filter)
        source = "$FRVAL,SpeedFilter,25.0*31"
        obj.parse_message(source)
        self.assertEqual(obj.nmea.speed_filter, 25.0)

        return

    def test_state_machine(self):
        global base_app

        print("")  # skip paste '.' on line
        base_app.logger.info("TEST server state machine")

        obj = protocol.GpsGate(base_app.logger)
        obj.set_imei("353547060660845")

        self.assertEqual(obj.state, obj.STATE_OFFLINE)

        expect = "$FRLIN,IMEI,353547060660845,*47\r\n"
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_TRY_LOGIN)
        self.assertEqual(message, expect)

        # repeat, is okay but get warning
        expect = "$FRLIN,IMEI,353547060660845,*47\r\n"
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_TRY_LOGIN)
        self.assertEqual(message, expect)

        server_response = "$FRSES,1221640*4F"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_HAVE_SESSION)
        self.assertTrue(result)

        # repeat, is okay but get warning
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_HAVE_SESSION)
        self.assertTrue(result)

        expect = "$FRVER,1,1,Cradlepoint 1.0*27\r\n"
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_WAIT_SERVER_VERSION)
        self.assertEqual(message, expect)

        # repeat, is okay but get warning
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_WAIT_SERVER_VERSION)
        self.assertEqual(message, expect)

        server_response = "$FRVER,1,1,GpsGate Server 1.1.0.360*04"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_HAVE_SERVER_VERSION)
        self.assertTrue(result)

        # repeat, is okay but get warning
        server_response = "$FRVER,1,1,GpsGate Server 1.1.0.360*04"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_HAVE_SERVER_VERSION)
        self.assertTrue(result)

        obj.set_server_version("0.3")
        self.assertEqual(obj.server_major_version, 0)
        self.assertEqual(obj.server_minor_version, 3)

        server_response = "$FRVER,1,1,GpsGate Server 1.1.0.360*04"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_HAVE_SERVER_VERSION)
        self.assertTrue(result)

        expect = "$FRCMD,,_getupdaterules,Inline*1E"
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_ASK_UPDATE)
        self.assertEqual(message, expect)

        server_response = "$FRRET,User1,_getupdaterules,Nmea,2*07"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_FORWARD_READY)
        self.assertTrue(result)

        server_response = "$FRVAL,DistanceFilter,500.0*67"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_FORWARD_READY)
        self.assertTrue(result)

        server_response = "$FRVAL,TimeFilter,60.0*42"
        result = obj.parse_message(server_response)
        self.assertEqual(obj.state, obj.STATE_FORWARD_READY)
        self.assertTrue(result)

        expect = "$FRWDT,NMEA*78"
        message = obj.get_next_client_2_server()
        self.assertEqual(obj.state, obj.STATE_FORWARDING)
        self.assertEqual(message, expect)

        return


if __name__ == '__main__':
    from cp_lib.app_base import CradlepointAppBase

    base_app = CradlepointAppBase(call_router=False)
    unittest.main()
