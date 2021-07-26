#
# foris-controller
# Copyright (C) 2019-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import typing
import logging
import ipaddress
import pkg_resources

from foris_controller.exceptions import UciException
from foris_controller_backends.services import OpenwrtServices
from foris_controller_backends.uci import (
    UciBackend,
    get_option_named,
    parse_bool,
    store_bool,
    get_sections_by_type,
    section_exists,
)


from foris_controller.utils import parse_to_list, unwrap_list
from foris_controller_backends.files import BaseFile, path_exists
from foris_controller_backends.maintain import MaintainCommands

logger = logging.getLogger(__name__)


def _get_interface(ip: str, netmask: str) -> str:
    ''' Get CIDR ipv4 address notation. '''
    interface = ipaddress.ip_interface(
        f"{ip}/{netmask}"
    )
    return str(interface)


class LanFiles(BaseFile):
    ODHCPD_FILE = "/var/hosts/odhcpd"
    DNSMASQ_LEASE_FILE = "/tmp/dhcp.leases"
    CONNTRACK_FILE = "/proc/net/nf_conntrack"

    def _bare_ip(self, iface):
        return ipaddress.ip_interface(iface).ip

    def _check_active(self, ip):
        conntrack = self._file_content(LanFiles.CONNTRACK_FILE)
        ip_exploded = ip.exploded
        return f"src={ip_exploded}" in conntrack or f"dst={ip_exploded}" in conntrack

    def get_dhcp_clients(self, network, netmask):
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
                f"{network}/{netmask}", strict=False
            ):
                res.append(
                    {
                        "expires": timestamp,
                        "mac": mac.upper().strip(),
                        "ip": ip,
                        "hostname": hostname,
                        "active": self._check_active(address),
                    }
                )

        return res

    def get_ipv6_dhcp_clients(self, odhcpd_file):
        if not path_exists(odhcpd_file):
            return []
        leasefile = self._file_content(odhcpd_file)
        lines = leasefile.strip().split("\n")

        res = []
        for line in lines:
            if line.startswith("#"):
                data = line.split(" ")
                properties, addresses = data[:8], data[8:]
                _, _, duid, _, hostname, timestamp, _, _ = properties
                ipv6 = list(map(self._bare_ip, addresses))
                timestamp = int(timestamp)
                for address in ipv6:
                    res.append(
                        {
                            "expires": 0,
                            "duid": duid,
                            "ipv6": str(address),
                            "hostname": hostname,
                            "active": self._check_active(address),
                        }
                    )
        return res


class LanUci(object):
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

    def get_client_list(self, uci_data, network, netmask):
        file_records = LanFiles().get_dhcp_clients(network, netmask)
        uci_data = get_sections_by_type(uci_data, "dhcp", "host")

        for record in uci_data:
            if "mac" in record["data"]:
                # handle a simple string or a list of MAC addresses
                if isinstance(record["data"]["mac"], str):
                    record["data"]["mac"] = [record["data"]["mac"]]
                record["data"]["mac"] = " ".join([e.strip().upper() for e in record["data"]["mac"]])

        uci_map = {
            e["data"]["mac"]: e["data"]
            for e in uci_data
            if "mac" in e["data"]
            and len(e["data"]["mac"].split(" ")) == 1  # ignore multi mac records
            and "ip" in e["data"]
            and (
                e["data"]["ip"] == "ignore"
                or self.in_network(e["data"]["ip"], network, netmask)  # has to be in lan
            )
        }
        for record in file_records:
            if record["mac"] in uci_map:
                # override actual ip by the one which is supposed to be set
                record["ip"] = uci_map[record["mac"]]["ip"]
                hostname = uci_map[record["mac"]].get("name", "")
                record["hostname"] = hostname if hostname else record["hostname"]
                del uci_map[record["mac"]]
        for record in uci_map.values():
            file_records.append(
                {
                    "ip": record["ip"],
                    "hostname": record.get("name", ""),
                    "mac": record["mac"],
                    "active": False,
                    "expires": 0,
                }
            )
        return file_records

    def get_ipv6_client_list(self, uci_data):
        odhcpd_file = get_option_named(uci_data,"dhcp", "odhcpd", "leasefile", "")
        if not odhcpd_file:
            odhcpd_file = LanFiles().ODHCPD_FILE
        records = LanFiles().get_ipv6_dhcp_clients(odhcpd_file)
        return records

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
            mode_managed["dhcp"]["ipv6clients"] = self.get_ipv6_client_list(dhcp_data)
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
                backend.set_option("dhcp", "lan", "ra", "server")
                backend.set_option("dhcp", "lan", "dhcpv6", "server")

                # set dhcp part (this device acts as a server here)
                if dhcp["enabled"]:
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

    def set_dhcp_client(self, ip: str, mac: str, hostname: str) -> typing.Optional[str]:
        """ Creates / updates a configuration of a single dhcp client
        :param ip: ip address to be assigned (or 'ignore' - don't assign any ip)
        :param mac: mac address of the client
        :param hostname: hostname of the client (can be empty)
        :returns: None if update passes error string otherwise
        """
        mac = mac.upper()

        with UciBackend() as backend:
            dhcp_data = backend.read("dhcp")
            network_data = backend.read("network")

            router_ip, netmask, _ = LanUci.get_network_combo(network_data)

            start = int(
                get_option_named(dhcp_data, "dhcp", "lan", "start", LanUci.DEFAULT_DHCP_START)
            )
            limit = int(
                get_option_named(dhcp_data, "dhcp", "lan", "limit", LanUci.DEFAULT_DHCP_LIMIT)
            )

            if ip != "ignore":  # ignore means that dhcp server won't provide ip for givem macaddr
                if LanUci.in_range(ip, router_ip, start, limit):
                    return "in-dynamic"

                if not LanUci.in_network(ip, router_ip, netmask):
                    return "out-of-network"

                mode = get_option_named(network_data, "network", "lan", "_turris_mode", "managed")
                if mode != "managed":
                    return "disabled"

                dhcp_enabled = not parse_bool(
                    get_option_named(dhcp_data, "dhcp", "lan", "ignore", "0")
                )
                if not dhcp_enabled:
                    return "disabled"

            section_name = None
            for section in get_sections_by_type(dhcp_data, "dhcp", "host"):
                if "mac" not in section["data"]:
                    continue
                macs = [e.upper() for e in section["data"]["mac"].split(" ")]
                if mac in macs:
                    if len(macs) == 1:
                        section_name = section["name"]
                        break
                    else:
                        # Split record => remove mac
                        backend.set_option(
                            "dhcp", section["name"], "mac", " ".join([e for e in macs if e != mac])
                        )
                        break

            if section_name is None:
                # section was not found or the record was splitted
                section_name = backend.add_section("dhcp", "host")

            backend.set_option("dhcp", section_name, "mac", mac)
            backend.set_option("dhcp", section_name, "ip", ip)
            backend.set_option("dhcp", section_name, "name", hostname)

        with OpenwrtServices() as services:
            services.restart("dnsmasq")

        return None  # everyting went ok
