#
# foris-controller
# Copyright (C) 2019-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import ipaddress
import logging
import typing

import pkg_resources

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
                    network_data, "network", "lan", "netmask", LanUci.DEFAULT_NETMASK
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

    def get_ipv6_client_list(self, interface="br-lan"):
        lease_data = UbusBackend.call_ubus("dhcp", "ipv6leases")
        res = []

        # Interface (e.g. `br-lan`) might not be actively managed by odhcpd,
        # if for instance, IPv6 is explicitely disabled on it.
        # Do not rely on assumption that interface has IPv6 always enabled.
        if lease_data and interface in lease_data["device"]:
            for lease in lease_data["device"][interface]["leases"]:
                if "ipv6-addr" not in lease:
                    # If assigned IPv6 prefix is large enough, downstream router might get both
                    # IPv6 address ('ipv6-addr') and IPv6 prefix ('ipv6-prefix') from upstream dhcpv6 server.
                    #
                    # Currently we just care about IPv6 address leases, e.g. devices in network, so ignore
                    # the IPv6 prefixes part or anything else.
                    continue

                addresses = lease["ipv6-addr"]
                for address in addresses:
                    res.append(
                        {
                            "expires": int(lease["valid"]),
                            "duid": lease["duid"],
                            "ipv6": address["address"],
                            "hostname": lease["hostname"],
                            "active": "bound" in lease["flags"],
                        }
                    )
        return res

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
            mode_managed["dhcp"]["ipv6clients"] = self.get_ipv6_client_list()
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
        for entry_point in pkg_resources.iter_entry_points("lan_range_changed"):
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
        """ Determine whether ip is in range defined by (start_ip + start .. start_ip + start, + limit)
        :param ip: ip to be compared
        :param start_ip: ip for where is range calculated
        :param start: start offset
        :param limit: count of ips
        :return: True if ip is in range False otherwise
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
