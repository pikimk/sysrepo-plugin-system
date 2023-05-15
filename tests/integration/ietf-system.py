#
# telekom / sysrepo-plugin-system
#
# This program is made available under the terms of the
# BSD 3-Clause license which is available at
# https://opensource.org/licenses/BSD-3-Clause
#
# SPDX-FileCopyrightText: 2021 Deutsche Telekom AG
# SPDX-FileContributor: Sartura Ltd.
#
# SPDX-License-Identifier: BSD-3-Clause
#
#!/usr/bin/python3

import unittest
import sysrepo
import os
import subprocess
import pwd
import signal
import time
import json
import platform
import datetime
import pwd
import spwd
import socket
import tzlocal

from pydbus import SystemBus

IETF_SYSTEM = "/ietf-system"

class SystemTestCase(unittest.TestCase):
    def setUp(self):
        plugin_path = os.environ.get("SYSREPO_GENERAL_PLUGIN_PATH")
        if plugin_path is None:
            self.fail(
                "SYSREPO_GENRAL_PLUGIN_PATH has to point to general plugin executable")
        self.data_dir = os.environ.get('GEN_PLUGIN_DATA_DIR')
        if self.data_dir is None:
            self.fail(
                "GEN_PLUGIN_DATA_DIR has to point to general plugin executable")
        self.plugin = subprocess.Popen(
            [plugin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    
    def tearDown(self):
        self.session.switch_datastore("running")
        #if self.session.get_data("/ietf-system:*") == None:
        self.session.replace_config(self.initial_ietf_data, "ietf-system")
        self.session.stop()
        self.conn.disconnect()
        self.plugin.send_signal(signal.SIGINT)
        self.plugin.wait()

    def startSession(self, datastore):
        self.conn = sysrepo.SysrepoConnection()
        self.session = self.conn.start_session(datastore)
        time.sleep(1)
        self.initial_ietf_data = self.session.get_data(IETF_SYSTEM + ":*")
    
    def datastore_content_is_valid(
        self, expected_xml, expected_data_filepath, data_xpath
    ):
        """
        Check if the datastore content for the given xpath
        is the same as the data from the file (expected_data_filepath).
        """
        with self.session.get_data_ly(data_xpath) as ds_data:
            ds_data_xml = ds_data.print_mem("xml")
            if expected_data_filepath:
                with open(expected_data_filepath, "r") as f:
                    expected_xml = f.read()
                if expected_xml == ds_data_xml:
                    return True
                else:
                    print("Expected data:")
                    print(expected_xml)
                    print("In datastore:")
                    print(ds_data_xml)
                    return False

    def edit_config(self, data, path=None, operation="merge"):
        with self.session.get_ly_ctx() as ctx:
            if path:
                with open(path, "r") as f:
                    data = f.read()
            ly_data = ctx.parse_data_mem(data, "xml", strict=True, no_state=True)
            self.session.edit_batch_ly(ly_data, default_operation=operation)
            ly_data.free()
            self.session.apply_changes()
    


class HostnameTestCase(SystemTestCase):
    def test_hostname(self):
        self.startSession("running")
        hostnames = [
            "testhost",
            "testing.local",
            "another.test.com",
            "example.host.test",
        ]

        for h in hostnames:
            data = f'<system xmlns="urn:ietf:params:xml:ns:yang:ietf-system">\n  <hostname>{h}</hostname>\n</system>\n'
            xml_data = open("data/system_hostname.xml", "w")
            xml_data.write(data)
            xml_data.close()

            self.edit_config(data)

            assert (
                self.datastore_content_is_valid(
                    xml_data.name, xml_data.name, "/ietf-system:system/hostname"
                )
                == True
            )
            assert h == socket.gethostname()


class TimezoneTestCase(SystemTestCase):
    def test_timezone(self):
        self.startSession("running")
        # use only non-symlink values in /usr/share/zoneinfo/ !
        self.session.set_item(
            IETF_SYSTEM + ":system/clock/timezone-name", "Europe/Berlin"
        )
        self.session.apply_changes()

        with self.session.get_data_ly(
            IETF_SYSTEM + ":system/clock/timezone-name"
        ) as ietf:
            self.clock_data = ietf.print_mem("xml")

        print(tzlocal.get_localzone_name())
        print(os.path.realpath("/etc/localtime"))
        assert (
            os.path.realpath("/etc/localtime").find(tzlocal.get_localzone_name()) > -1
        )
        assert self.clock_data.find(tzlocal.get_localzone_name()) > -1

        # should not set since this timezone does not exist
        try:
            self.session.set_item(
                IETF_SYSTEM + ":system/clock/timezone-name", "Europe/Silverstone"
            )
            self.session.apply_changes()
        except:
            assert os.path.realpath("/etc/localtime").find("Europe/Silverstone") == -1

class DnsSearchServerTestCase(SystemTestCase):
    def test_dns_search_server(self):
        self.startSession("running")
        servers = [
            "testsrv",
             "examplesrv",
             "testexamplesrv",
             "testserver",
        ]

        for s in servers:

            data = f'<system xmlns="urn:ietf:params:xml:ns:yang:ietf-system">\n  <dns-resolver>\n    <search>{s}</search>\n  </dns-resolver>\n</system>\n'
            xml_data = open("data/system_dns_search.xml", "w")
            xml_data.write(data)    
            xml_data.close()

            self.edit_config(data)

        dns_data = self.session.get_data(IETF_SYSTEM + ":system/dns-resolver")
        dns_data_servers = dns_data.get("system").get("dns-resolver").get("search")

        dns_search_all = []
        dns_initial_servers = None

        # if there is current search servers in the list
        try:
            dns_initial_servers = self.initial_ietf_data.get("system").get("dns-resolver").get("search")
        except:
            dns_initial_servers = []

        for search_server in dns_initial_servers:
            dns_search_all.append(search_server)

        for search_server in servers:
            dns_search_all.append(search_server)

        #check datastore
        self.assertEqual(dns_search_all, dns_data_servers, "Datastore doesn't match with test case!")
        
        #apply the changes
        self.session.apply_changes()

        #get all from system bus
        bus = SystemBus()
        dns_search_bus = bus.get("org.freedesktop.resolve1").Domains

        #assert the system bus with datastore
        bus_servers = []
        for server in dns_search_bus:
            bus_servers.append(server[1])
        
        self.assertEqual(bus_servers,dns_search_all, "Servers do not match!")






# class SystemTestCase(unittest.TestCase):
#     def setUp(self):
#         plugin_path = os.environ.get('SYSREPO_GENERAL_PLUGIN_PATH')
#         if plugin_path is None:
#             self.fail(
#                 "SYSREPO_GENRAL_PLUGIN_PATH has to point to general plugin executable")

#         self.data_dir = os.environ.get('GEN_PLUGIN_DATA_DIR')
#         if self.data_dir is None:
#             self.fail(
#                 "GEN_PLUGIN_DATA_DIR has to point to general plugin executable")
#         self.plugin = subprocess.Popen(
#             [plugin_path],
#             env={
#                 "GEN_PLUGIN_DATA_DIR": self.data_dir},
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL)

#         self.conn = sysrepo.SysrepoConnection()
#         self.session = self.conn.start_session("running")

#         # self.initial_data = self.session.get_data("/ietf-system:system")
        
#         time.sleep(2)

#     def tearDown(self):
#         self.session.stop()
#         self.conn.disconnect()
#         self.plugin.send_signal(signal.SIGINT)
#         self.plugin.wait()

#     def load_initial_data(self, path):
#         ctx = self.conn.get_ly_ctx()

#         self.session.replace_config_ly(None, "ietf-system")
#         with open(path, "r") as f:
#             data = f.read()
#             data = ctx.parse_data_mem(data, "xml", config=True, strict=True)
#             self.session.replace_config_ly(data, "ietf-system")
#             data.free()

#     def edit_config(self, path):
#          with self.session.get_ly_ctx() as ctx:
#             if path:
#                 with open(path, "r") as f:
#                     data = f.read()
#             ly_data = ctx.parse_data_mem(data, "xml", strict=True, no_state=True)
#             self.session.edit_batch_ly(ly_data, default_operation="merge")
#             ly_data.free()
#             self.session.apply_changes()
            


# class HostnameTestCase(SystemTestCase):
#     def test_hostname(self):
#         initial_data = self.session.get_data('/ietf-system:system').get("system")
#         expected_hostname = "example.host.test"

#         #self.edit_config("data/system_hostname.xml")
#         self.session.replace_config({"system":{"hostname":"example.host.test"}}, "ietf-system")

#         with self.session.get_data_ly('/ietf-system:system/hostname') as data:
#             hostname = data.print_dict()
#             hostname_str = str(hostname.get('system').get('hostname'))

#         # hostname_str = self.session.get_data("/ietf-system:system/hostname").get("system").get("hostname")

#         self.assertEqual(hostname_str, expected_hostname, "hostname data is wrong ")

#         real_hostname = os.uname()[1]
#         self.assertEqual(
#             real_hostname,
#             "example.host.test",
#             "hostname on system doesn't match set hostname")

#         self.session.replace_config(initial_data, "ietf-system")

  
# class TimezoneTestCase(SystemTestCase):
#     def test_timezone(self):
#         tzdata = '/etc/localtime'
#         store_timezone = os.readlink(tzdata)
#         expected_timezone_name = 'Europe/Stockholm'
#         init_data = self.session.get_data("/ietf-system:*")

#         self.session.replace_config({"system":{"clock": {"timezone-name":"Europe/Stockholm"}}}, 'ietf-system')

#         with self.session.get_data_ly('/ietf-system:system/clock/timezone-name') as data:
#             timezone_name = data.print_dict()
#             timezone_name_str = str(timezone_name.get('system').get('clock').get('timezone-name'))
        
#         self.assertEqual(timezone_name_str, expected_timezone_name, "timezone_name data is wrong")
#         real_timezone = os.readlink('/etc/localtime')
#         self.assertEqual(
#             real_timezone,
#             '/usr/share/zoneinfo/Europe/Stockholm', 
#             "timezone on system doesn't match set timezone")

#         self.session.replace_config(self.initial_data, 'ietf-system')


# # class DnsSearchTestCase(SystemTestCase):
# #     def test_dns_search_server(self):
# #         bus = SystemBus()
# #         dev = bus.get("org.freedesktop.hostname1")
# #         self.assertEqual(1, 2, "Params not equal" + dev.Hostname)


# # class DummyTest(SystemTestCase):
# #     def test_dummy(self):
# #         self.assertEqual(1, 1, "Params not equal")


if __name__ == '__main__':
    unittest.main()
