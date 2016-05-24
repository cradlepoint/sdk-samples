# Test the CP_LIB gps NMEA parser
import sys
import time
import unittest

import cp_lib.gps_nmea as nmea


class TestGpsNmea(unittest.TestCase):

    def test_checksum(self):

        tests = [
            ("$GPGGA,222227.0,4500.819061,N,09320.092805,W,1,10,0.8,281." +
             "3,M,-33.0,M,,*6F\r\n",
             "GPGGA,222227.0,4500.819061,N,09320.092805,W,1,10,0.8,281." +
             "3,M,-33.0,M,,", 0x6F),
            ("$GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2," +
             "020516,0.0,E,A*1D\r\n",
             "GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2," +
             "020516,0.0,E,A", 0x1D),
            ("$GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A*23\r\n",
             "GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A",
             0x23),
            ("$PCPTI,IBR1100-702,222227,222227*33\r\n",
             "PCPTI,IBR1100-702,222227,222227",
             0x33),
            ("$GPGGA,222237.0,4500.819061,N,09320.092805,W,1,09,0.8,281.3" +
             ",M,-33.0,M,,*66\r\n",
             "GPGGA,222237.0,4500.819061,N,09320.092805,W,1,09,0.8,281.3" +
             ",M,-33.0,M,,", 0x66),
            ("$GPRMC,222237.0,A,4500.819061,N,09320.092805,W,0.0,353.2" +
             ",020516,0.0,E,A*1C\r\n",
             "GPRMC,222237.0,A,4500.819061,N,09320.092805,W,0.0,353.2" +
             ",020516,0.0,E,A", 0x1C),

            # some bad tests
            (None, TypeError, 0),
            ("", IndexError, 0),
        ]

        for test in tests:
            full = test[0]
            base = test[1]
            csum = test[2]

            if base == TypeError:
                with self.assertRaises(TypeError):
                    nmea.calc_checksum(full)

            elif base == IndexError:
                with self.assertRaises(IndexError):
                    nmea.calc_checksum(full)

            else:
                self.assertEqual(nmea.calc_checksum(full), csum)
                self.assertTrue(nmea.validate_checksum(full))
                self.assertEqual(nmea.calc_checksum(base), csum)
                self.assertEqual(nmea.wrap_sentence(base), full)

        return

    def test_rmc(self):

        tests = [
            ("$GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2," +
             "020516,0.0,E,A*1D\r\n",
             {'course': 353.2, 'long': -93.33488008333333, 'knots': 0.0,
              'lat': 45.013651016666664, 'valid': True,
              'gps_utc':  1462227747.0, 'time': 1462302255.968968}),
            ("$GPRMC,222237.0,A,4500.819061,N,09320.092805,W,0.0,353.2" +
             ",020516,0.0,E,A*1C\r\n",
             {'course': 353.2, 'long': -93.33488008333333, 'knots': 0.0,
              'lat': 45.013651016666664, 'valid': True,
              'gps_utc':  1462227757.0, 'time': 1462302255.968968}),
        ]

        obj = nmea.NmeaStatus()
        obj.date_time = True
        obj.speed = True
        obj.altitude = True
        obj.coor_ddmm = False
        obj.coor_dec = True

        for test in tests:
            sentence = test[0]
            expect = test[1]
            now = 1462302255.968968

            # print("source[%s]" % sentence)
            obj.start(now)
            result = obj.parse_sentence(sentence)
            self.assertTrue(result)
            obj.publish()

            result = obj.get_attributes()
            # print("RMC result:{}".format(result))
            # print("RMC expect:{}".format(expect))
            self.assertEqual(result, expect)

        return

    def test_vtg(self):

        tests = [
            ("$GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A*23\r\n",
             {'course': 353.2, 'kmh': 0.0, 'knots': 0.0,
              'time': 1462302255.968968}),
        ]

        obj = nmea.NmeaStatus()
        obj.date_time = True
        obj.speed = True
        obj.altitude = True
        obj.coor_ddmm = False
        obj.coor_dec = True

        for test in tests:
            sentence = test[0]
            expect = test[1]
            now = 1462302255.968968

            # print("inp [%s]" % sentence)
            obj.start(now)
            result = obj.parse_sentence(sentence)
            self.assertTrue(result)
            obj.publish()

            result = obj.get_attributes()
            # print("out[{}]".format(result))
            self.assertEqual(result, expect)

        return

    def test_gga(self):

        tests = [
            ("$GPGGA,222227.0,4500.819061,N,09320.092805,W,1,10,0.8,281." +
             "3,M,-33.0,M,,*6F\r\n",
             {'long': -93.33488008333333, 'lat': 45.013651016666664,
              'num_sat': 10, 'alt': 281.3, 'time': 1462302255.968968}),
            ("$GPGGA,222237.0,4500.819061,N,09320.092805,W,1,09,0.8,281.3" +
             ",M,-33.0,M,,*66\r\n",
             {'long': -93.33488008333333, 'lat': 45.013651016666664,
              'num_sat': 9, 'alt': 281.3, 'time': 1462302255.968968}),
        ]

        obj = nmea.NmeaStatus()
        obj.date_time = True
        obj.speed = True
        obj.altitude = True
        obj.coor_ddmm = False
        obj.coor_dec = True

        for test in tests:
            sentence = test[0]
            expect = test[1]
            now = 1462302255.968968

            # print("inp [%s]" % sentence)
            obj.start(now)
            result = obj.parse_sentence(sentence)
            self.assertTrue(result)
            obj.publish()

            result = obj.get_attributes()
            # print("out[{}]".format(result))
            self.assertEqual(result, expect)

        return

    def test_batch(self):

        obj = nmea.NmeaStatus()
        obj.date_time = True
        obj.speed = True
        obj.altitude = True
        obj.coor_ddmm = False
        obj.coor_dec = True

        now = 1462302255.968968

        # print("[%s]" % sentence)
        obj.start(now)

        sentence = "$GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0," + \
                   "353.2,020516,0.0,E,A*1D\r\n"
        result = obj.parse_sentence(sentence)
        self.assertTrue(result)

        sentence = "$GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A*23\r\n"
        result = obj.parse_sentence(sentence)
        self.assertTrue(result)

        sentence = "$GPGGA,222227.0,4500.819061,N,09320.092805,W,1,10,0.8" + \
                   ",281.3,M,-33.0,M,,*6F\r\n"
        result = obj.parse_sentence(sentence)
        self.assertTrue(result)

        obj.publish()
        expect = {'course': 353.2, 'long': -93.33488008333333, 'knots': 0.0,
                  'lat': 45.013651016666664, 'valid': True,
                  'gps_utc':  1462227747.0, 'num_sat': 10, 'alt': 281.3,
                  'kmh': 0.0, 'time': 1462302255.968968}

        result = obj.get_attributes()
        # print("out[{}]".format(result))
        self.assertEqual(result, expect)

        return

    def test_fix_time_sentence(self):
        tests = [
            ("$GPGGA,222227.0,4500.819061,N,09320.092805,W,1,10,0.8,281." +
             "3,M,-33.0,M,,*6F\r\n",
             "$GPGGA,171614.0,4500.819061,N,09320.092805,W,1,10,0.8,281." +
             "3,M,-33.0,M,,*6E\r\n"),
            ("$GPRMC,222227.0,A,4500.819061,N,09320.092805,W,0.0,353.2," +
             "020516,0.0,E,A*1D\r\n",
             "$GPRMC,171614.0,A,4500.819061,N,09320.092805,W,0.0,353.2," +
             "010516,0.0,E,A*1F\r\n"),
            ("$GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A*23\r\n",
             "$GPVTG,353.2,T,353.2,M,0.0,N,0.0,K,A*23\r\n"),
            ("$PCPTI,IBR1100-702,222227,222227*33\r\n",
             "$PCPTI,IBR1100-702,222227,222227*33\r\n"),

            # some bad tests
            (None, TypeError, 0),
            ("", IndexError, 0),
        ]

        use_time = time.strptime("2016-05-01 17:16:14", "%Y-%m-%d %H:%M:%S")

        for test in tests:
            source = test[0]
            expect = test[1]

            if expect == TypeError:
                with self.assertRaises(TypeError):
                    nmea.fix_time_sentence(source, use_time)

            elif expect == IndexError:
                with self.assertRaises(IndexError):
                    nmea.fix_time_sentence(source, use_time)

            else:
                result = nmea.fix_time_sentence(source, use_time)
                self.assertEqual(result, expect)

        return


if __name__ == '__main__':
    unittest.main()
