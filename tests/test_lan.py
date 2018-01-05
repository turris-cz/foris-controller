#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

import os
import pytest

from foris_controller.exceptions import UciRecordNotFound

from .fixtures import (
    backend, message_bus, only_backends, infrastructure, ubusd_test, lock_backend
)
from .test_uci import get_uci_module
from .utils import match_subdict


@pytest.fixture(scope="function")
def lan_uci_configs():
    try:
        os.mkdir("/etc/config/")
    except:
        pass

    wireless_config = """
config wifi-device 'radio0'
        option type 'mac80211'
        option channel '36'
        option country 'CZ'
        option hwmode '11a'
        option path 'soc/soc:pcie-controller/pci0000:00/0000:00:01.0/0000:01:00.0'
        option htmode 'VHT80'
        option disabled '1'

config wifi-iface
        option device 'radio0'
        option network 'lan'
        option mode 'ap'
        option ssid 'Turris'
        option encryption 'none'

config wifi-device 'radio1'
        option type 'mac80211'
        option channel '11'
        option country 'CZ'
        option hwmode '11g'
        option path 'soc/soc:pcie-controller/pci0000:00/0000:00:03.0/0000:03:00.0'
        option htmode 'HT20'
        option disabled '1'

config wifi-iface
        option device 'radio1'
        option network 'lan'
        option mode 'ap'
        option ssid 'Turris'
        option encryption 'none'
"""
    with open("/etc/config/wireless", "w") as f:
        f.write(wireless_config)
        f.flush()

    network_config="""
config interface 'loopback'
        option ifname 'lo'
        option proto 'static'
        option ipaddr '127.0.0.1'
        option netmask '255.0.0.0'

config globals 'globals'
        option ula_prefix 'fdb2:5f63:e0e5::/48'

config interface 'lan'
        option ifname 'eth0 eth2'
        option force_link '1'
        option type 'bridge'
        option proto 'static'
        option netmask '255.255.255.0'
        option ip6assign '60'
        option ipaddr '192.168.0.0'

config interface 'wan'
        option ifname 'eth1'
        option proto 'dhcp'
        option ipv6 '0'

config interface 'wan6'
        option ifname '@wan'
        option proto 'dhcpv6'

config switch
        option name 'switch0'
        option reset '1'
        option enable_vlan '1'

config switch_vlan
        option device 'switch0'
        option vlan '1'
        option ports '0 1 2 3 5'

config switch_vlan
        option device 'switch0'
        option vlan '2'
        option ports '4 6'
"""
    with open("/etc/config/network", "w") as f:
        f.write(network_config)
        f.flush()

    dhcp_config="""
config dnsmasq
        option domainneeded '1'
        option boguspriv '1'
        option filterwin2k '0'
        option localise_queries '1'
        option rebind_protection '1'
        option rebind_localhost '1'
        option domain 'lan'
        option expandhosts '1'
        option nonegcache '0'
        option authoritative '1'
        option readethers '1'
        option leasefile '/tmp/dhcp.leases'
        option resolvfile '/tmp/resolv.conf.auto'
        option localservice '1'
        option port '0'
        option local '/bankavvv.fff/'

config dhcp 'lan'
        option interface 'lan'
        option start '100'
        option leasetime '12h'
        option dhcpv6 'server'
        option ra 'server'
        option ignore '0'
        option limit '800'
        list dhcp_option '6,192.168.0.0'

config dhcp 'wan'
        option interface 'wan'
        option ignore '1'

config odhcpd 'odhcpd'
        option maindhcp '0'
        option leasefile '/tmp/hosts/odhcpd'
        option leasetrigger '/usr/sbin/odhcpd-update'
"""
    with open("/etc/config/dhcp", "w") as f:
        f.write(dhcp_config)
        f.flush()

    sqm_config="""
config queue 'eth1'
        option enabled '0'
        option interface 'eth1'
        option download '85000'
        option upload '10000'
        option qdisc 'fq_codel'
        option script 'simple.qos'
        option qdisc_advanced '0'
        option ingress_ecn 'ECN'
        option egress_ecn 'ECN'
        option qdisc_really_really_advanced '0'
        option itarget 'auto'
        option etarget 'auto'
        option linklayer 'none'
"""
    with open("/etc/config/sqm", "w") as f:
        f.write(sqm_config)
        f.flush()

    firewall_config = """
config defaults
        option syn_flood        1
        option input            ACCEPT
        option output           ACCEPT
        option forward          REJECT

config zone
        option name             lan
        list   network          'lan'
        option input            ACCEPT
        option output           ACCEPT
        option forward          ACCEPT

config zone
        option name             wan
        list   network          'wan'
        list   network          'wan6'
        option input            REJECT
        option output           ACCEPT
        option forward          REJECT
        option masq             1
        option mtu_fix          1

config forwarding
        option src              lan
        option dest             wan

config rule
        option name             Allow-DHCP-Renew
        option src              wan
        option proto            udp
        option dest_port        68
        option target           ACCEPT
        option family           ipv4

config rule
        option name             Allow-Ping
        option src              wan
        option proto            icmp
        option icmp_type        echo-request
        option family           ipv4
        option target           ACCEPT

config rule
        option name             Allow-IGMP
        option src              wan
        option proto            igmp
        option family           ipv4
        option target           ACCEPT

config rule
        option name             Allow-DHCPv6
        option src              wan
        option proto            udp
        option src_ip           fe80::/10
        option src_port         547
        option dest_ip          fe80::/10
        option dest_port        546
        option family           ipv6
        option target           ACCEPT

config rule
        option name             Allow-MLD
        option src              wan
        option proto            icmp
        option src_ip           fe80::/10
        list icmp_type          '130/0'
        list icmp_type          '131/0'
        list icmp_type          '132/0'
        list icmp_type          '143/0'
        option family           ipv6
        option target           ACCEPT

config rule
        option name             Allow-ICMPv6-Input
        option src              wan
        option proto    icmp
        list icmp_type          echo-request
        list icmp_type          echo-reply
        list icmp_type          destination-unreachable
        list icmp_type          packet-too-big
        list icmp_type          time-exceeded
        list icmp_type          bad-header
        list icmp_type          unknown-header-type
        list icmp_type          router-solicitation
        list icmp_type          neighbour-solicitation
        list icmp_type          router-advertisement
        list icmp_type          neighbour-advertisement
        option limit            1000/sec
        option family           ipv6
        option target           ACCEPT

config rule
        option name             Allow-ICMPv6-Forward
        option src              wan
        option dest             *
        option proto            icmp
        list icmp_type          echo-request
        list icmp_type          echo-reply
        list icmp_type          destination-unreachable
        list icmp_type          packet-too-big
        list icmp_type          time-exceeded
        list icmp_type          bad-header
        list icmp_type          unknown-header-type
        option limit            1000/sec
        option family           ipv6
        option target           ACCEPT

config include
        option path /etc/firewall.user

config include
        option path /usr/share/firewall/turris
        option reload 1

config include
        option path /etc/firewall.d/with_reload/firewall.include.sh
        option reload 1

config include
        option path /etc/firewall.d/without_reload/firewall.include.sh
        option reload 0

config rule
        option src              wan
        option dest             lan
        option proto            esp
        option target           ACCEPT

config rule
        option src              wan
        option dest             lan
        option dest_port        500
        option proto            udp
        option target           ACCEPT
"""
    with open("/etc/config/firewall", "w") as f:
        f.write(firewall_config)
        f.flush()

    yield None
    os.remove("/etc/config/wireless")
    os.remove("/etc/config/dhcp")
    os.remove("/etc/config/network")
    os.remove("/etc/config/sqm")
    os.remove("/etc/config/firewall")


def test_get_settings(lan_uci_configs, infrastructure, ubusd_test):
    res = infrastructure.process_message({
        "module": "lan",
        "action": "get_settings",
        "kind": "request",
    })
    assert set(res.keys()) == {"action", "kind", "data", "module"}
    assert "ip" in res["data"].keys()
    assert "netmask" in res["data"].keys()
    assert "dhcp" in res["data"].keys()
    assert "enabled" in res["data"]["dhcp"].keys()
    assert "start" in res["data"]["dhcp"].keys()
    assert "limit" in res["data"]["dhcp"].keys()
    assert "guest_network" in res["data"].keys()
    assert "enabled" in res["data"]["guest_network"].keys()
    assert "ip" in res["data"]["guest_network"].keys()
    assert "netmask" in res["data"]["guest_network"].keys()
    assert "qos" in res["data"]["guest_network"].keys()
    assert "enabled" in res["data"]["guest_network"]["qos"].keys()
    assert "upload" in res["data"]["guest_network"]["qos"].keys()
    assert "download" in res["data"]["guest_network"]["qos"].keys()


def test_update_settings(lan_uci_configs, infrastructure, ubusd_test):

    def update(data):
        notifications = infrastructure.get_notifications()
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'lan'
        }
        notifications = infrastructure.get_notifications(notifications)
        assert notifications[-1]["module"] == "lan"
        assert notifications[-1]["action"] == "update_settings"
        assert notifications[-1]["kind"] == "notification"
        assert match_subdict(data, notifications[-1]["data"])

        res = infrastructure.process_message({
            "module": "lan",
            "action": "get_settings",
            "kind": "request",
        })
        assert res["module"] == "lan"
        assert res["action"] == "get_settings"
        assert res["kind"] == "reply"
        assert match_subdict(data, res["data"])

    update({
        u"ip": u"192.168.5.8",
        u"netmask": u"255.255.255.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.0.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": True,
            u"start": 10,
            u"limit": 50,
        },
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.2.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.8.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": False,
            },
        },
    })
    update({
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.9.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": True,
                u"download": 1200,
                u"upload": 1000,
            },
        },
    })


@pytest.mark.only_backends(['openwrt'])
def test_guest_openwrt_backend(
        lan_uci_configs, lock_backend, infrastructure, ubusd_test):

    uci = get_uci_module(lock_backend)

    def update(data):
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert res == {
            u'action': u'update_settings',
            u'data': {u'result': True},
            u'kind': u'reply',
            u'module': u'lan'
        }

    # test guest network
    update({
        u"ip": u"10.2.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.8.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": False,
            },
        },
    })
    with uci.UciBackend() as backend:
        data = backend.read()

    assert uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    assert uci.get_option_named(data, "network", "guest_turris", "type") == "bridge"
    assert set(uci.get_option_named(data, "network", "guest_turris", "ifname")) == {
        "guest_turris_0", "guest_turris_1"
    }
    assert uci.get_option_named(data, "network", "guest_turris", "proto") == "static"
    assert uci.get_option_named(data, "network", "guest_turris", "ipaddr") == "192.168.8.1"
    assert uci.get_option_named(data, "network", "guest_turris", "netmask") == "255.255.255.0"
    assert uci.get_option_named(data, "network", "guest_turris", "bridge_empty") == "1"

    assert not uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert uci.get_option_named(data, "dhcp", "guest_turris", "interface") == "guest_turris"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "start") == "200"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "limit") == "50"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "leasetime") == "1h"
    assert uci.get_option_named(data, "dhcp", "guest_turris", "dhcp_option") == ["6,192.168.8.1"]

    assert uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert uci.get_option_named(data, "firewall", "guest_turris", "name") == "guest_turris"
    assert uci.get_option_named(data, "firewall", "guest_turris", "input") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "forward") == "REJECT"
    assert uci.get_option_named(data, "firewall", "guest_turris", "output") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "enabled"))
    assert uci.get_option_named(
            data, "firewall", "guest_turris_forward_wan", "src") == "guest_turris"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_forward_wan", "dest") == "wan"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "enabled"))
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dns_rule", "src") == "guest_turris"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dns_rule", "proto") == "tcpudp"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dns_rule", "dest_port") == "53"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dns_rule", "target") == "ACCEPT"
    assert uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "enabled"))
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dhcp_rule", "src") == "guest_turris"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dhcp_rule", "proto") == "udp"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dhcp_rule", "src_port") == "67-68"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dhcp_rule", "dest_port") == "67-68"
    assert uci.get_option_named(
            data, "firewall", "guest_turris_dhcp_rule", "target") == "ACCEPT"

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")

    # test guest network + qos
    update({
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.9.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": True,
                u"download": 1200,
                u"upload": 1000,
            },
        },
    })
    with uci.UciBackend() as backend:
        data = backend.read()
    assert uci.parse_bool(uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled"))
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "interface") \
            == "br-guest_turris"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "qdisc") == "fq_codel"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "script") == "simple.qos"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "link_layer") == "none"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "verbosity") == "5"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "debug_logging") == "1"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "download") == "1000"
    assert uci.get_option_named(data, "sqm", "guest_limit_turris", "upload") == "1200"

    # test guest wi-fi disabled and other disabled
    update({
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": False,
        },
    })
    with uci.UciBackend() as backend:
        data = backend.read()
    assert not uci.parse_bool(uci.get_option_named(data, "network", "guest_turris", "enabled"))
    assert uci.parse_bool(uci.get_option_named(data, "dhcp", "guest_turris", "ignore"))
    assert not uci.parse_bool(uci.get_option_named(data, "firewall", "guest_turris", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_forward_wan", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dns_rule", "enabled"))
    assert not uci.parse_bool(uci.get_option_named(
        data, "firewall", "guest_turris_dhcp_rule", "enabled"))
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_0", "disabled"))
    assert uci.parse_bool(uci.get_option_named(data, "wireless", "guest_iface_1", "disabled"))

    with pytest.raises(UciRecordNotFound):
        assert uci.get_option_named(data, "sqm", "guest_limit_turris", "enabled")


def test_wrong_update(lan_uci_configs, infrastructure, ubusd_test):

    def update(data):
        notifications = infrastructure.get_notifications()
        res = infrastructure.process_message({
            "module": "lan",
            "action": "update_settings",
            "kind": "request",
            "data": data
        })
        assert "errors" in res["data"]

    update({
        u"ip": u"10.1.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {
            u"enabled": False,
            u"start": 10,
            u"limit": 50,
        },
        u"guest_network": {u"enabled": False},
    })
    update({
        u"ip": u"10.2.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": False,
            u"ip": u"192.168.8.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": False,
            },
        },
    })
    update({
        u"ip": u"10.3.0.3",
        u"netmask": u"255.255.0.0",
        u"dhcp": {u"enabled": False},
        u"guest_network": {
            u"enabled": True,
            u"ip": u"192.168.9.1",
            u"netmask": u"255.255.255.0",
            u"qos": {
                u"enabled": False,
                u"download": 1200,
                u"upload": 1000,
            },
        },
    })
