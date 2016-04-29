# Test the TARGET tool

import unittest
import logging
# noinspection PyUnresolvedReferences
import shutil


class TestTarget(unittest.TestCase):

    def test_load_ini(self):
        from tools.target import TheTarget

        print("")

        data = [
            "; think of these as 'flavors' to apply to the settings.ini", "",
            "[AER3100]", "; user_name=admin", "interface=ENet USB-1", "local_ip=192.168.30.1", "password=lin805",
            "", "[AER2100]", "local_ip=192.168.21.1", "password=4416ec79",
            "", "[AER1600]", "local_ip=192.168.16.1", "password=441ec8f9", ""
        ]

        expect = {
            "AER3100": {"interface": "ENet USB-1", "local_ip": "192.168.30.1", "password": "lin805"},
            "AER2100": {"local_ip": "192.168.21.1", "password": "4416ec79"},
            "AER1600": {"local_ip": "192.168.16.1", "password": "441ec8f9"},
        }

        file_name = "test/tmp_target.ini"

        # write the TARGET.INI to load
        _han = open(file_name, 'w')
        for line in data:
            _han.write(line + "\n")
        _han.close()

        target = TheTarget()
        result = target.load_target_ini(file_name)

        logging.debug("result:{}".format(result))
        self.assertEqual(expect, result)

        return

    def test_find_interface_ip(self):
        import ipaddress
        from tools.target import TheTarget

        print("")

        report = [
            "",
            "Configuration for interface \"ENet MB\"",
            "    IP Address:                           192.168.0.10",
            "    Subnet Prefix:                        192.168.0.0/24 (mask 255.255.255.0)",
            "    Default Gateway:                      192.168.0.1",
            "",
            "Configuration for interface \"ENet USB-1\"",
            "    IP Address:                           192.168.30.6",
            "    Subnet Prefix:                        192.168.30.0/24 (mask 255.255.255.0)",
            ""
            "Configuration for interface \"ENet Virtual\"",
            "    Subnet Prefix:                        192.168.30.0/24 (mask 255.255.255.0)",
            ""
        ]

        target = TheTarget()

        interface = "ENet MB"
        expect = ipaddress.IPv4Address("192.168.0.10")
        result, network = target.get_interface_ip_info(interface, report)
        self.assertEqual(expect, result)

        interface = "ENet USB-1"
        expect = ipaddress.IPv4Address("192.168.30.6")
        result, network = target.get_interface_ip_info(interface, report)
        self.assertEqual(expect, result)

        interface = "Other Port"
        expect = None
        result, network = target.get_interface_ip_info(interface, report)
        self.assertEqual(expect, result)

        interface = "ENet Virtual"
        expect = None
        result, network = target.get_interface_ip_info(interface, report)
        self.assertEqual(expect, result)

        return

    def test_ip_hacking(self):
        from tools.target import TheTarget

        print("")

        tests = [
            {"src": "192.168.30.6", "exp": "192.168.30.6"},
            {"src": "192.168.30.0/24", "exp": "192.168.30.0"},
            {"src": "192.168.30.6:8080", "exp": "192.168.30.6"},
        ]

        target = TheTarget()

        for test in tests:
            logging.debug("Test:{}".format(test))
            result = target.trim_ip_to_4(test["src"])
            self.assertEqual(test["exp"], result)

        return

    def test_whoami(self):
        from tools.target import TheTarget

        print("")

        result = TheTarget.get_whoami()
        logging.debug("WhoAmI:[{}]".format(result))

        return


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
