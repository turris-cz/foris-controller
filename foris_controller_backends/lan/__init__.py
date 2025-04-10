#
# foris-controller
# Copyright (C) 2019-2025 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import abc
import ipaddress
import logging
import time
import typing

from importlib import metadata

from copy import deepcopy

from foris_controller.exceptions import UciException
from foris_controller.utils import parse_to_list, unwrap_list
from foris_controller_backends.files import BaseFile, path_exists
from foris_controller_backends.maintain import MaintainCommands
from foris_controller_backends.services import OpenwrtServices
from foris_controller_backends.ubus import UbusBackend
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    get_sections_by_type,
    parse_bool,
    section_exists,
    store_bool,
)

logger = logging.getLogger(__name__)


class ForwardingException(Exception, metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def api_response(self) -> typing.List[dict]:
        pass

    def __init__(self, rule_name):
        self.rule_name = rule_name


class NotInLanException(ForwardingException):
    def api_response(self) -> typing.List[dict]:
        return [{"new_rule": self.rule_name, "msg": "not-in-lan"}]


class NotUserDefinedException(ForwardingException):
    def api_response(self) -> typing.List[dict]:
        return [{"new_rule": self.rule_name, "msg": "not-user-defined"}]


class AlreadyUsedException(ForwardingException):
    def __init__(self, rule_name: str, overlaps: dict):
        self.rule_name = rule_name
        self.overlaps = overlaps

    def api_response(self) -> typing.List[dict]:
        return [
            {
                "old_rule": e["old_rule"],
                "new_rule": self.rule_name,
                "range": e["range"],
                "msg": "range-already-used",
            }
            for e in self.overlaps
        ]


def _get_interface(ip: str, netmask: str) -> str:
    ''' Get CIDR ipv4 address notation. '''
    interface = ipaddress.ip_interface(
        f"{ip}/{netmask}"
    )
    return str(interface)


class LanFiles(BaseFile):
    DNSMASQ_LEASE_FILE = "/tmp/dhcp.leases"
    CONNTRACK_FILE = "/proc/net/nf_conntrack"

    def _check_active(self, ip):
        conntrack = self._file_content(LanFiles.CONNTRACK_FILE)
        ip_exploded = ip.exploded
        return f"src={ip_exploded}" in conntrack or f"dst={ip_exploded}" in conntrack

    def get_dhcp_clients(self, network_ip: str, netmask: str) -> typing.List[dict]:
        if not path_exists(LanFiles.DNSMASQ_LEASE_FILE):
            return []
        lines = self._file_content(LanFiles.DNSMASQ_LEASE_FILE).strip("\n \t").split("\n")
        res = []
        for line in lines:
            try:
                timestamp, mac, ip, hostname, _ = line.split(" ")
                timestamp = int(timestamp)
            except ValueError:
                continue
            address = ipaddress.ip_address(ip)

            # filter by network and netmask
            if address in ipaddress.ip_network(
                f"{network_ip}/{netmask}", strict=False
            ):
                res.append(
                    {
                        "expires": timestamp,
                        "mac": mac.upper().strip(),
                        "ip": ip,
                        "hostname": hostname,
                        "active": self._check_active(address),
                        "static": False,
                    }
                )

        return res


class LanUci:
    DEFAULT_DHCP_START = 100
    DEFAULT_DHCP_LIMIT = 150
    DEFAULT_LEASE_TIME = 12 * 60 * 60
    DEFAULT_ROUTER_IP = "192.168.1.1"
    DEFAULT_NETMASK = "255.255.255.0"
    FW_ALLOWED_KEYS = ("name", "dest_ip", "src_dport", "dest_port", "enabled")

    @staticmethod
    def get_network_combo(network_data) -> typing.Tuple[str, str, str]:
        ''' In case CIDR ipv4 address notation is used in Uci
        convert lan address.

        return router_ip, netmask, gateway
        '''
        ipaddr_option = unwrap_list(
            get_option_named(
                network_data, "network", "lan", "ipaddr", LanUci.DEFAULT_ROUTER_IP
            )
        )
        gateway = get_option_named(
            network_data, "network", "lan", "gateway", LanUci.DEFAULT_ROUTER_IP
        )
        if ipaddr_option.count("/") == 1:
            ip_iface = ipaddress.ip_interface(ipaddr_option)
            return (str(ip_iface.ip), str(ip_iface.netmask), gateway)
        else:
            return (
                ipaddr_option,
                get_option_named(
                    network_data,
                    "network",
                    "lan",
                    "netmask",
                    LanUci.DEFAULT_NETMASK,
                ),
                gateway
            )

    @staticmethod
    def _set_lan(backend, router_ip, netmask):
        ''' Helper function to save ipv4 address to uci in CIDR format. '''
        backend.del_option("network", "lan", "ipaddr", fail_on_error=False)
        backend.del_option("network", "lan", "netmask", fail_on_error=False)

        backend.add_to_list(
            "network", "lan", "ipaddr",
            parse_to_list(
                _get_interface(router_ip, netmask)
            )
        )

    def get_client_list(self, uci_data: dict, router_ip: str, netmask: str) -> typing.List[dict]:
        file_records = LanFiles().get_dhcp_clients(router_ip, netmask)

        static_uci_data = get_sections_by_type(uci_data, "dhcp", "host")

        for record in static_uci_data:
            if "mac" in record["data"]:
                # Use only first mac and ignore the rest in case multiple MACs are detected
                record["data"]["mac"] = LanUci._process_uci_mac_addresses(record["data"]["mac"])[0]

        static_leases_map = {
            e["data"]["mac"]: e["data"]
            for e in static_uci_data
            if "mac" in e["data"]
            and "ip" in e["data"]  # `mac` and `ip` are mandatory for dhcp host, so ignore incomplete hosts
            and (
                e["data"]["ip"] == "ignore"
                or self.in_network(e["data"]["ip"], router_ip, netmask)  # has to be in lan
            )
        }
        for record in file_records:
            if record["mac"] in static_leases_map:
                # override actual ip by the one which is supposed to be set
                record["ip"] = static_leases_map[record["mac"]]["ip"]
                hostname = static_leases_map[record["mac"]].get("name", "")
                record["hostname"] = hostname if hostname else record["hostname"]
                record["static"] = True
                del static_leases_map[record["mac"]]

        for record in static_leases_map.values():
            file_records.append(
                {
                    "ip": record["ip"],
                    "hostname": record.get("name", ""),
                    "mac": record["mac"],
                    "active": False,
                    "expires": 0,
                    "static": True,
                }
            )
        return file_records

    @staticmethod
    def _get_ipv6_client_list(interface="br-lan") -> typing.List[dict]:
        """Get dhcpv6 leases info from json data provided by odhcpd.

        NOTE: We are getting this data via ubus, so this function could break anytime
        the odhcpd json output structure changes.
        """
        lease_data = UbusBackend.call_ubus("dhcp", "ipv6leases")
        res = []

        # Interface (e.g. `br-lan`) might not be actively managed by odhcpd,
        # if for instance, IPv6 is explicitely disabled on it.
        # Do not rely on assumption that interface has IPv6 always enabled.
        if lease_data and interface in lease_data["device"]:
            # use the same base timestamp for all the leases
            now = int(time.time())

            for lease in lease_data["device"][interface]["leases"]:
                if "ipv6-addr" not in lease:
                    # If assigned IPv6 prefix is large enough, downstream router might get both
                    # IPv6 address ('ipv6-addr') and IPv6 prefix ('ipv6-prefix') from upstream dhcpv6 server.
                    #
                    # Currently we just care about IPv6 address leases, e.g. devices in network, so ignore
                    # the IPv6 prefixes part or anything else.
                    continue

                expires_time = LanUci._sanitize_dhcpv6_lease_time(lease["valid"])
                if expires_time is None:
                    continue  # something is wrong with lease time, ignore this lease

                addresses = lease["ipv6-addr"]
                expires_time = LanUci._sanitize_dhcpv6_lease_time(lease["valid"])
                if expires_time is None:
                    continue  # something is wrong with lease time, ignore this lease

                expires_timestamp = LanUci._make_timestamp_from_dhcpv6_lease_time(now, expires_time)

                for address in addresses:
                    res.append(
                        {
                            "expires": expires_timestamp,
                            "duid": lease["duid"],
                            "ipv6": address["address"],
                            "hostname": lease["hostname"],
                            "active": "bound" in lease["flags"],
                        }
                    )
        return res

    @staticmethod
    def _sanitize_dhcpv6_lease_time(leasetime: str) -> typing.Optional[int]:
        """Sanitize dhcpv6 lease time string.

        Fallback to `None` on unexpected values (i.e. lease time that can't be converted to int).
        """
        try:
            expires = int(leasetime)
        except ValueError as exc:
            # odhcpd should already process "junk" values as "-1" (see source code),
            # so this is intended for really unexpected values from odhcpd.
            logger.warning("Malformed DHCPv6 lease time. Cannot convert lease time to numeric value. Reason: %r", exc)
            return None

        # '-1' or other negative numbers points to some kind of error with lease time (see odhcpd source code).
        # Fallback to 0 in case of negative lease time.
        return expires if expires >= 0 else 0

    @staticmethod
    def _make_timestamp_from_dhcpv6_lease_time(now: int, lease_duration: int) -> int:
        """Make lease end time timestamp from lease time duration.

        odhcpd reports lease time *duration* in seconds, while dnsmasq reports
        dhcpv4 lease timestamp as time of the *end* of the lease.
        Therefore we would like to have the timestamp meaning in sync with DHCPv4 timestamps.
        """
        if lease_duration == 0:
            # Previous processing should sanitize lease time to positive numbers.
            # Lease time 0 is considered special value: some kind of error with lease time, but not fatal one.
            # To highlight this unusual value to consumer (frontend), do not return now + lease_duration
            # (effectively just `now`) timestamp, which might look as good valid timestamp.
            # Return 0 instead.
            return 0

        return now + lease_duration

    @staticmethod
    def _normalize_lease(value):
        leasetime = str(value)
        if leasetime == "infinite":
            return 0
        elif leasetime.endswith("m"):
            return int(leasetime[:-1]) * 60
        elif leasetime.endswith("h"):
            return int(leasetime[:-1]) * 60 * 60
        elif leasetime.endswith("d"):
            return int(leasetime[:-1]) * 60 * 60 * 24
        else:
            return int(leasetime)

    def get_settings(self):

        with UciBackend() as backend:
            network_data = backend.read("network")
            sqm_data = backend.read("sqm")
            dhcp_data = backend.read("dhcp")
            firewall_data = backend.read("firewall")
            try:
                wireless_data = backend.read("wireless")
            except UciException:
                wireless_data = {}

        mode = get_option_named(network_data, "network", "lan", "_turris_mode", "managed")

        mode_managed = {"dhcp": {}}
        router_ip, netmask, gateway = LanUci.get_network_combo(network_data)
        mode_managed["router_ip"], mode_managed["netmask"] = router_ip, netmask
        mode_managed["dhcp"]["enabled"] = not parse_bool(
            get_option_named(dhcp_data, "dhcp", "lan", "ignore", "0")
        )
        mode_managed["dhcp"]["start"] = int(
            get_option_named(dhcp_data, "dhcp", "lan", "start", self.DEFAULT_DHCP_START)
        )
        mode_managed["dhcp"]["limit"] = int(
            get_option_named(dhcp_data, "dhcp", "lan", "limit", self.DEFAULT_DHCP_LIMIT)
        )
        mode_managed["dhcp"]["lease_time"] = LanUci._normalize_lease(
            get_option_named(dhcp_data, "dhcp", "lan", "leasetime", self.DEFAULT_LEASE_TIME)
        )
        if mode_managed["dhcp"]["enabled"]:
            mode_managed["dhcp"]["clients"] = self.get_client_list(
                dhcp_data, mode_managed["router_ip"], mode_managed["netmask"]
            )
            mode_managed["dhcp"]["ipv6clients"] = LanUci._get_ipv6_client_list()
        else:
            mode_managed["dhcp"]["clients"] = []

        mode_unmanaged = {}
        mode_unmanaged["lan_type"] = get_option_named(network_data, "network", "lan", "proto")
        hostname = get_option_named(network_data, "network", "lan", "hostname", "")

        mode_unmanaged["lan_dhcp"] = {"hostname": hostname} if hostname else {}
        mode_unmanaged["lan_static"] = {
            "ip": router_ip,
            "netmask": netmask,
            "gateway": gateway
        }
        dns = get_option_named(network_data, "network", "lan", "dns", [])
        dns = dns if isinstance(dns, (list, tuple)) else [e for e in dns.split(" ") if e]
        dns = reversed(dns)  # dns with higher priority should be added last
        try:
            # use ipv4 addresses only
            dns = [e for e in dns if isinstance(ipaddress.ip_address(e), ipaddress.IPv4Address)]
        except ValueError:
            dns = []
        mode_unmanaged["lan_static"].update(zip(("dns1", "dns2"), dns))

        from foris_controller_backends.networks import NetworksUci

        qos = {}
        qos["enabled"] = parse_bool(
            get_option_named(sqm_data, "sqm", "limit_lan_turris", "enabled", "0")
        )
        # upload is actually download limit nad vice versa
        qos["upload"] = int(
            get_option_named(sqm_data, "sqm", "limit_lan_turris", "download", 1024)
        )
        qos["download"] = int(
            get_option_named(sqm_data, "sqm", "limit_lan_turris", "upload", 1024)
        )

        result = {
            "mode": mode,
            "mode_managed": mode_managed,
            "mode_unmanaged": mode_unmanaged,
            "interface_count": NetworksUci.get_interface_count(network_data, wireless_data, "lan"),
            "interface_up_count": NetworksUci.get_interface_count(
                network_data, wireless_data, "lan", True
            ),
            "qos": qos
        }

        # quick hack for shield redirect to 192.168.1.1
        lan_redirect_exists = section_exists(firewall_data, "firewall", "redirect_192_168_1_1")

        if lan_redirect_exists:
            result["lan_redirect"] = parse_bool(
                get_option_named(firewall_data, "firewall", "redirect_192_168_1_1", "enabled", "1")
            )

        return result

    def filter_dhcp_client_records(
        self,
        backend: UciBackend,
        dhcp_data,
        old_router_ip: typing.Optional[str],
        old_netmask: typing.Optional[str],
        new_router_ip: str,
        new_netmask: str,
        new_start: int,
        new_limit: int,
    ):
        for record in get_sections_by_type(dhcp_data, "dhcp", "host"):
            if "ip" in record["data"] and record["data"]["ip"] != "ignore":
                # remove if in dynamic range
                if self.in_range(record["data"]["ip"], new_router_ip, new_start, new_limit):
                    backend.del_section("dhcp", record["name"])

                # remove if it was in old network and is not in the new
                if old_router_ip and old_netmask:
                    if self.in_network(
                        record["data"]["ip"], old_router_ip, old_netmask
                    ) and not self.in_network(record["data"]["ip"], new_router_ip, new_netmask):
                        backend.del_section("dhcp", record["name"])

    @staticmethod
    def _store_lan_redirect(backend, enabled):
        """ quick hack for shield redirect to 192.168.1.1
        store only if there is section redirect_192_168_1_1
        """

        firewall_data = backend.read("firewall")
        lan_redirect_exists = section_exists(firewall_data, "firewall", "redirect_192_168_1_1")

        # store redirect only if section exists, otherwise skip and don't create section
        if lan_redirect_exists:
            backend.set_option("firewall", "redirect_192_168_1_1", "enabled", store_bool(enabled))

    def update_settings(self, mode, mode_managed=None, mode_unmanaged=None, lan_redirect=None, qos=None):
        """  Updates the lan settings in uci

        :param mode: lan setting mode managed/unmanaged
        :type mode: str
        :param mode_managed: managed mode settings {"router_ip": ..., "netmask":..., "dhcp": ...}
        :type mode_managed: dict
        :param mode_unmanaged: {"lan_type": "none/dhcp/static", "lan_static": {}, ...}
        :type mode_unmanaged: dict
        :param qos: {'download': ..., 'enabled': False/True, 'upload': ...}
        :type qos: dict
        """

        with UciBackend() as backend:

            backend.add_section("network", "interface", "lan")
            backend.set_option("network", "lan", "_turris_mode", mode)

            if lan_redirect is not None:
                LanUci._store_lan_redirect(backend, lan_redirect)

            if mode == "managed":
                network_data = backend.read("network")
                dhcp_data = backend.read("dhcp")
                backend.set_option("network", "lan", "proto", "static")
                LanUci._set_lan(backend, mode_managed["router_ip"], mode_managed["netmask"])
                backend.add_section("dhcp", "dhcp", "lan")
                dhcp = mode_managed["dhcp"]
                backend.set_option("dhcp", "lan", "ignore", store_bool(not dhcp["enabled"]))

                # set dhcp part (this device acts as a server here)
                if dhcp["enabled"]:
                    backend.set_option("dhcp", "lan", "ra", "server")
                    backend.set_option("dhcp", "lan", "dhcpv6", "server")
                    backend.set_option("dhcp", "lan", "start", dhcp["start"])
                    backend.set_option("dhcp", "lan", "limit", dhcp["limit"])
                    backend.set_option(
                        "dhcp",
                        "lan",
                        "leasetime",
                        "infinite" if dhcp["lease_time"] == 0 else dhcp["lease_time"],
                    )

                    # this will override all user dhcp options
                    # TODO we might want to preserve some options
                    backend.replace_list(
                        "dhcp", "lan", "dhcp_option", ["6,%s" % mode_managed["router_ip"]]
                    )

                    # update dhcp records when changing lan ip+network or start+limit
                    # get old network
                    old_router_ip, old_netmask, _ = LanUci.get_network_combo(network_data)
                    self.filter_dhcp_client_records(
                        backend,
                        dhcp_data,
                        old_router_ip,
                        old_netmask,
                        mode_managed["router_ip"],
                        mode_managed["netmask"],
                        dhcp["start"],
                        dhcp["limit"],
                    )
                else:
                    backend.set_option("dhcp", "lan", "ra", "disabled")
                    backend.set_option("dhcp", "lan", "dhcpv6", "disabled")

            elif mode == "unmanaged":
                backend.set_option("network", "lan", "proto", mode_unmanaged["lan_type"])
                # disable dhcp for both protocols and ipv6 router-advertisments
                # since you are not managing this network...
                backend.add_section("dhcp", "dhcp", "lan")
                backend.set_option("dhcp", "lan", "ignore", store_bool(True))
                backend.set_option("dhcp", "lan", "ra", "disabled")
                backend.set_option("dhcp", "lan", "dhcpv6", "disabled")

                if mode_unmanaged["lan_type"] == "dhcp":
                    if "hostname" in mode_unmanaged["lan_dhcp"]:
                        backend.set_option(
                            "network", "lan", "hostname", mode_unmanaged["lan_dhcp"]["hostname"]
                        )
                elif mode_unmanaged["lan_type"] == "static":
                    LanUci._set_lan(backend, mode_unmanaged["lan_static"]["ip"], mode_unmanaged["lan_static"]["netmask"])
                    backend.set_option(
                        "network", "lan", "gateway", mode_unmanaged["lan_static"]["gateway"]
                    )
                    dns = [
                        mode_unmanaged["lan_static"][name]
                        for name in ("dns2", "dns1")
                        if name in mode_unmanaged["lan_static"]
                    ]  # dns with higher priority should be added last
                    backend.replace_list("network", "lan", "dns", dns)
                elif mode_unmanaged["lan_type"] == "none":
                    pass  # no need to handle

            if qos:
                try:
                    backend.del_section("sqm", "limit_lan_turris")
                except UciException:
                    pass

                if qos["enabled"]:
                    try:
                        backend.add_section("sqm", "queue", "limit_lan_turris")
                        backend.set_option("sqm", "limit_lan_turris", "enabled", store_bool(qos["enabled"]))
                        backend.set_option("sqm", "limit_lan_turris", "interface", "br-lan")
                        backend.set_option("sqm", "limit_lan_turris", "qdisc", "fq_codel")
                        backend.set_option("sqm", "limit_lan_turris", "script", "simple.qos")
                        backend.set_option("sqm", "limit_lan_turris", "link_layer", "none")
                        backend.set_option("sqm", "limit_lan_turris", "verbosity", "5")
                        backend.set_option("sqm", "limit_lan_turris", "debug_logging", "1")
                        # We need to swap dowload and upload
                        # "upload" means upload to the guest network
                        # "download" means dowload from the guest network
                        backend.set_option("sqm", "limit_lan_turris", "upload", qos["download"])
                        backend.set_option("sqm", "limit_lan_turris", "download", qos["upload"])
                    except UciException as e:
                        logger.error("Unable to create sqm record for LAN")
                        raise UciException from e

        # trigger hooks in modules to perform related changes after LAN configuration was changed
        for entry_point in metadata.entry_points(group="lan_range_changed"):
            entry_point.load()()

        # update wizard passed in foris web (best effort)
        try:
            from foris_controller_backends.web import WebUciCommands

            WebUciCommands.update_passed("lan")
        except UciException:
            pass

        MaintainCommands().restart_network()

        return True

    @staticmethod
    def in_range(ip: str, start_ip: str, start: int, limit: int) -> bool:
        """ Determine whether ip is in range defined by (start_ip + start .. start_ip + start, + limit)
        :param ip: ip to be compared
        :param start_ip: ip for where is range calculated
        :param start: start offset
        :param limit: count of ips
        :return: True if ip is in range False otherwise
        """
        dynamic_first = ipaddress.ip_address(start_ip) + start
        dynamic_last = dynamic_first + limit
        return dynamic_first <= ipaddress.ip_address(ip) <= dynamic_last

    @staticmethod
    def in_network(ip: str, ip_root: str, netmask: str) -> bool:
        """ Determine whether ip is in network
        :param ip: ip to be compared
        :param ip_root: ip adress of router
        :param netmask: network mask address
        :return: True if ip is in network False otherwise
        """
        if ip_root.count("/") == 1:
            iface = ipaddress.ip_interface(f"{ip_root}")
            network = ipaddress.ip_network(f"{iface.ip}/{iface.netmask}", strict=False)
        else:
            network = ipaddress.ip_network(f"{ip_root}/{netmask}", strict=False)
        return ipaddress.ip_address(ip) in network

    @staticmethod
    def _process_uci_mac_addresses(mac_addrs: typing.Union[str, typing.List[str]]) -> typing.List[str]:
        """Parse MAC address/addresses uci value and return result in unified format.

        Distinguish between MAC addresses as string or list of strings.
        Also strip MAC addresses of unnecessary whitespaces.

        Return list of addresses (uppercase).
        """
        if isinstance(mac_addrs, str):
            macs = [e.strip().upper() for e in mac_addrs.split(" ")]
        elif isinstance(mac_addrs, list):
            macs = [e.strip().upper() for e in mac_addrs]
        else:
            raise ValueError("Unexpected datatype of mac address record")

        return macs

    @staticmethod
    def _host_record_exists(dhcp_data: dict, mac: str) -> bool:
        """Check whether host record with provided MAC address exists

        :param dhcp_data: uci config data
        :param mac: MAC address
        :returns: True if exists, otherwise False
        """
        return bool(LanUci._get_host_record_section(dhcp_data, mac))

    @staticmethod
    def _get_host_record_section(dhcp_data: dict, mac: str) -> typing.Optional[dict]:
        """Get DHCP host uci config section based on MAC address

        Useful for manipulation with anonymous uci config sections.
        Return either section (dict) or None if no fitting section is found.
        """
        for section in get_sections_by_type(dhcp_data, "dhcp", "host"):
            if "mac" not in section["data"]:
                continue

            macs = LanUci._process_uci_mac_addresses(section["data"]["mac"])
            if mac.upper() in macs:  # search for substring match in case of multiple MACs
                section["data"]["mac"] = macs
                return section

        return None

    @staticmethod
    def _minimal_valid_host_section(uci_section: dict) -> bool:
        """Check whether DHCP host section contains minimal set of mandatory options

        Properly configured DHCP host should have at least option mac and ip present
        """
        if "mac" not in uci_section["data"]:
            logger.debug("Option 'mac' is missing in section '%s'", uci_section["name"])
            return False

        if "ip" not in uci_section["data"]:
            logger.debug("Option 'ip' is missing in section '%s'", uci_section["name"])
            return False

        # It is possible to set lease without hostname via LuCI,
        # so don't consider hostname as mandatory option and just stick to minimal config

        return True

    @staticmethod
    def _ip_is_unique(dhcp_data: dict, ip: str) -> bool:
        """Check whether IP address is unique among DHCP hosts"""
        for section in get_sections_by_type(dhcp_data, "dhcp", "host"):
            if not LanUci._minimal_valid_host_section(section):
                continue

            if section["data"]["ip"] == ip:
                return False

        return True

    @staticmethod
    def _hostname_is_unique(dhcp_data: dict, hostname: str) -> bool:
        """Check whether hostname is unique among DHCP hosts"""
        for section in get_sections_by_type(dhcp_data, "dhcp", "host"):
            if not LanUci._minimal_valid_host_section(section):
                continue

            if section["data"].get("name") == hostname:
                return False

        return True

    @staticmethod
    def _validate_dhcp_host_ip(
        network_data: dict,
        dhcp_data: dict,
        ip: str,
        router_ip: str,
        netmask: str,
    ) -> typing.Optional[str]:
        """Validate DHCP host IP address

        Check whether it fits the target network, DHCP is enabled and so on

        :param network_data dict: network config uci data
        :param dhcp_data dict: dhcp config uci data
        :param ip str: host IP address
        :param router_ip str: router IP address
        :param netmask str: netmask of ...
        :returns: None on success or string with the reason of failure
        """
        if ip != "ignore":  # ignore means that dhcp server won't provide ip for givem macaddr
            if not LanUci.in_network(ip, router_ip, netmask):
                return "out-of-network"

            turris_mode = get_option_named(network_data, "network", "lan", "_turris_mode", "managed")
            if turris_mode != "managed":
                return "disabled"

            dhcp_enabled = not parse_bool(
                get_option_named(dhcp_data, "dhcp", "lan", "ignore", "0")
            )
            if not dhcp_enabled:
                return "disabled"

            # IP address is already taken
            # Either by another host or we are updating the same host, but not IP
            if not LanUci._ip_is_unique(dhcp_data, ip):
                return "ip-exists"

        return None  # data looks OK

    def set_dhcp_client(self, ip: str, mac: str, hostname: str) -> typing.Optional[str]:
        """ Create configuration of a single dhcp client

        Distiction between create and update is that creating new client config
        should not overwrite existing configuration
        If configuration already exists, error message 'already-exists' should be returned

        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: None if update passes, error string otherwise
        """
        mac = mac.upper()

        with UciBackend() as backend:
            dhcp_data = backend.read("dhcp")
            network_data = backend.read("network")

            router_ip, netmask, _ = LanUci.get_network_combo(network_data)

            if LanUci._host_record_exists(dhcp_data, mac):
                return "mac-exists"

            err_msg = LanUci._validate_dhcp_host_ip(network_data, dhcp_data, ip, router_ip, netmask)
            if err_msg:
                return err_msg

            if not LanUci._hostname_is_unique(dhcp_data, hostname):
                return "hostname-exists"

            section_name = backend.add_section("dhcp", "host")
            backend.set_option("dhcp", section_name, "mac", mac)
            backend.set_option("dhcp", section_name, "ip", ip)
            backend.set_option("dhcp", section_name, "name", hostname)
            backend.set_option("dhcp", section_name, "leasetime", "infinite")
            backend.set_option("dhcp", section_name, "dns", store_bool(True))

        with OpenwrtServices() as services:
            services.restart("dnsmasq")

        return None  # everything went ok

    def update_dhcp_client(self, ip: str, old_mac: str, mac: str, hostname: str) -> typing.Optional[str]:
        """ Update configuration of a single dhcp client

        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param old_mac: previous mac address of the client
        :param mac: updated mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: None if update passes, error string otherwise
        """
        old_mac = old_mac.upper()
        new_mac = mac.upper()

        with UciBackend() as backend:
            dhcp_data = backend.read("dhcp")
            network_data = backend.read("network")

            router_ip, netmask, _ = LanUci.get_network_combo(network_data)

            # 1) section lookup by old_mac
            config_section = LanUci._get_host_record_section(dhcp_data, old_mac)
            if config_section is None:  # nothing to update
                return "mac-not-exists"

            current_config = {
                "name": config_section["name"],
                "ip": config_section["data"]["ip"],
                "mac": config_section["data"]["mac"],
                "hostname": config_section["data"]["name"],
            }

            if (current_config["hostname"] == hostname
                    and current_config["ip"] == ip
                    and new_mac in current_config["mac"]):
                # updated values are the same as stored ones, there is no need to update anything
                return None

            # 2) input data validation
            err_msg = LanUci._validate_dhcp_host_ip(network_data, dhcp_data, ip, router_ip, netmask)
            if err_msg is not None:
                if err_msg != "ip-exists":
                    return err_msg
                elif err_msg == "ip-exists" and ip != current_config["ip"]:  # IP is already used for another dhcp host
                    return err_msg

            if not LanUci._hostname_is_unique(dhcp_data, hostname) and hostname != current_config["hostname"]:
                return "hostname-exists"  # hostname is already used for another dhcp host

            if LanUci._host_record_exists(dhcp_data, new_mac) and new_mac not in current_config["mac"]:
                # check for substring in case of multimac, instead of exact string match
                return "mac-exists"  # MAC address is already used for another dhcp host

            # 3) do the actual update
            section_name = current_config["name"]
            macs = current_config["mac"]
            if len(macs) > 1:
                # Records with multiple MACs per IP address should not be used and usage is discouraged,
                # because it might not even work with dnsmasq.
                # We can't safely update the multimac record without possible hostname/ip collisions,
                # so it is safer to delete whole record and re-create it again.
                backend.del_section("dhcp", section_name)

                # Original section was removed so we need to start again with new section
                section_name = backend.add_section("dhcp", "host")

            backend.set_option("dhcp", section_name, "mac", new_mac)
            backend.set_option("dhcp", section_name, "ip", ip)
            backend.set_option("dhcp", section_name, "name", hostname)

        with OpenwrtServices() as services:
            services.restart("dnsmasq")

        return None  # everything went ok

    def delete_dhcp_client(self, mac: str) -> typing.Optional[str]:
        """Delete configuration of single dhcp client
        :param mac: mac address of dhcp client
        """
        mac = mac.upper()

        with UciBackend() as backend:
            dhcp_data = backend.read("dhcp")

            section = LanUci._get_host_record_section(dhcp_data, mac)
            if section is None:
                return "mac-not-exists"  # there is nothing to delete

            macs = section["data"]["mac"]
            if len(macs) == 1:
                backend.del_section("dhcp", section["name"])
            else:
                # Handle multi-mac record
                # Remove only particular mac, but keep others
                backend.set_option(
                    "dhcp", section["name"], "mac", " ".join([e for e in macs if e != mac])
                )

        with OpenwrtServices() as services:
            services.restart("dnsmasq")

        return None  # everything went ok

    def _get_user_defined_dhcp_clients(self, dhcp_data) -> typing.List[dict]:
        """ Helper function to determine user-defined dhcp leases that are used with forwarding. """
        hosts = get_sections_by_type(dhcp_data, "dhcp", "host")
        return hosts

    @staticmethod
    def _convert_ports(data) -> typing.Optional[dict]:
        """Converts dashed `-` range to dictionary
        :param data: firewall rules for port forwarding

        Replaces `src_dport` and `dest_port` of source `data` as dicts with keys:
            ["value"] in case port is single and <int>
            ["start","end","value"] in case port is <str> range
        """

        def unwrap(port_range):
            """Helper function"""
            try:
                # it is integer anyway
                res = {"value": int(port_range)}
            except (ValueError, TypeError):
                if isinstance(port_range, str) and "-" in port_range:
                    # make the full dict
                    res = dict(
                        zip(
                            ("start","end", "value"),
                            [int(i) for i in port_range.split("-")] + [port_range]
                        )
                    )

            return res

        # target keys
        for setting in {"src_dport", "dest_port"} & data.keys():
            data[setting] = unwrap(data[setting])

    @staticmethod
    def _deconvert_ports(data):
        """Reverts previous function
        :param data: dict, forwarding data
        """
        for setting in {"src_dport", "dest_port"} & data.keys():
            data[setting] = data[setting]["value"]

    def _extract_range(self, port: dict[str,int]):
        """Extracts range from port object
        :param port: dict
        """
        if {"start", "end"} <= port.keys():
            return self._make_range_set(port["start"], port["end"])
        else:
            return self._make_range_set(port["value"])

    def _get_all_forwardings(self, fw_data) -> typing.List[dict]:
        """ Provides all current forwardings in UCI
        src_dport and dest_port are converted to dictionary
        whether there is dashed `-` range or plain int
        """
        forwardings = deepcopy(get_sections_by_type(fw_data, "firewall", "redirect"))

        for index, item in enumerate(forwardings):
            item["data"]["index"] = index

            # unwrap possible ranges
            self._convert_ports(item["data"])

        return [e["data"] for e in forwardings]

    @staticmethod
    def _make_range_set(start:int, end: typing.Optional[int] = None) -> typing.Set[int]:
        """ Helper func. to create set of port ranges to interpolate. """
        if end is None:
            return {start}
        else:
            return set(range(start, end + 1))

    def _check_port_range_not_used(self, fw_data, src_dport:dict, name: str) -> typing.Optional[typing.List[str]]:
        """ Checks for possible port interference.
        :retval: None or List of objects related to an error"""
        errors = []

        fwds: list[dict] = self._get_all_forwardings(fw_data)

        if fwds:
            new_range = self._extract_range(src_dport)

            for item in fwds:
                # skip forwarding with the same name
                # it probably be changed anyway
                if item["name"] == name:
                    continue

                if item["name"] != name and item["src"] == "wan":

                    old_range = self._extract_range(item.get("src_dport"))

                    intrs = old_range.intersection(new_range)

                    if len(intrs) > 0:
                        errors.extend([{
                            "old_rule" : item['name'],
                            "msg": "range-already-used",
                            "range": f'{min(intrs)}-{max(intrs)}' if len(intrs) > 1 else str(intrs.pop())}])

        logger.debug(f"Errors in port forwarding: {errors}")

        return errors if len(errors) > 0 else None

    def get_port_forwardings(self) -> typing.List[typing.Dict[str,str]]:
        """ API method, gets all current forwardings. """
        with UciBackend() as backend:
            firewall_data = backend.read("firewall")
        raw_fwds = self._get_all_forwardings(firewall_data)
        res = []

        for fwd in raw_fwds:

            fwd["enabled"] = parse_bool(fwd.get("enabled", "true"))
            self._deconvert_ports(fwd)

            res.append({k: v for k,v in fwd.items() if k in LanUci.FW_ALLOWED_KEYS})
        return {"rules": res}

    def _update_forwarding(
        self,
        dhcp_clients,
        network_data,
        firewall_data,
        backend,
        name,
        dest_ip,
        src_dport,
        dest_port=None,
        enabled=True,
        old_name=None,
    ):
        """ Creates/updates/deletes configuration of single firewall rule
        :dhcp_clients, network_data, firewall_data, bakend: Uci parameters to set the rules
        :name: string rule name
        :dest_ip: ip address of traffic recipient
        :src_dport: integer | dict
        :dest_port: integer | dict ; destination port, leave empty in case of source port range
        :enabled: determine if rule should be applied
        :raises ForwardingException when improperly configured
        """
        # assert lease name is unique as it is the only identifier

        leases = self._get_all_forwardings(firewall_data)
        for item in leases:
            #  delete it, we will change it
            if item["name"] == name:
                self._delete_rule(firewall_data, backend, name)
                # we need to update the leases in order to perform the second delete
                # - index of anonymous rule changed
                firewall_data = backend.read("firewall")
                leases = self._get_all_forwardings(firewall_data)

        for item in leases:
            #  delete the old one as well
            if item["name"] == old_name:
                self._delete_rule(firewall_data, backend, old_name)

        # refresh firewall data possible delete
        firewall_data = backend.read("firewall")

        # determine if required ip address has user-defined lease
        if dest_ip not in dhcp_clients:
            raise NotUserDefinedException(name)

        # make sure lease is part of LAN
        router_ip, netmask, _ = LanUci.get_network_combo(network_data)

        if not self.in_network(dest_ip, router_ip, netmask):
            raise NotInLanException(name)

        # check if this new settings does not overlap with existing (firewall_data)
        chck_range = self._check_port_range_not_used(firewall_data, src_dport, name)

        if isinstance(chck_range, list):
            raise AlreadyUsedException(name, chck_range)

        # create new in UCI, rule does not exist or is being modified (while deleted above)
        redirect = backend.add_section("firewall", "redirect")
        backend.set_option("firewall", redirect, "name", name)
        backend.set_option("firewall", redirect, "target", "DNAT")
        backend.set_option("firewall", redirect, "src", "wan")
        backend.set_option("firewall", redirect, "dest", "lan")
        backend.set_option("firewall", redirect, "dest_ip", dest_ip)
        backend.set_option("firewall", redirect, "src_dport", src_dport["value"])

        if dest_port:
            backend.set_option("firewall", redirect, "dest_port", dest_port["value"])
        backend.set_option("firewall", redirect, "enabled", store_bool(enabled))

        return None  # update successful

    def _delete_rule(
        self,
        fw_data,
        backend,
        name
    ) -> None:
        """ Delete rule based on name in list. """
        current = self._get_all_forwardings(fw_data)
        for item in current:
            if item['name'] == name:
                backend.del_section("firewall", f"@redirect[{item['index']}]")

    def port_forwarding_delete(self, names: typing.List[str]) -> bool:
        with UciBackend() as backend:
            fw_data = backend.read("firewall")
            for rule_name in names:
                self._delete_rule(fw_data, backend, rule_name)

        # restart the firewall
        with OpenwrtServices() as services:
            services.reload("firewall")

        return True

    def port_forwarding_set(
        self,
        **kwargs,
    ) -> list:
        try:
            with UciBackend() as backend:
                fw_data = backend.read("firewall")
                dhcp_data = backend.read("dhcp")
                network_data = backend.read("network")

                if not kwargs.get("dest_port"):
                    # remove `"dest_port": None`
                    kwargs.pop("dest_port")

                _hosts = get_sections_by_type(dhcp_data,"dhcp", "host")
                dhcp_clients = [e["data"]["ip"] for e in _hosts if "ip" in e["data"]]

                self._convert_ports(kwargs)

                self._update_forwarding(
                    dhcp_clients,
                    network_data,
                    fw_data,
                    backend,
                    **kwargs,
                )

        except ForwardingException as e:
            return e.api_response()

        return []
