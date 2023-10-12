#
# foris-controller
# Copyright (C) 2017-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import pathlib

import pytest
# load common fixtures
from foris_controller_testtools.fixtures import FILE_ROOT_PATH, UCI_CONFIG_DIR_PATH
from foris_controller_testtools.utils import get_uci_module, FileFaker

DEFAULT_UCI_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "uci_configs", "defaults"
)

SCRIPT_ROOT_DIR = str(pathlib.Path(__file__).parent / "test_root")


@pytest.fixture(scope="function")
def lan_dnsmasq_files():
    leases = "\n".join(
        [
            "1539350186 11:22:33:44:55:66 192.168.1.101 prvni *",
            "1539350188 99:88:77:66:55:44 192.168.2.1 * *",
        ]
    )
    conntrack = "\n".join(
        [
            "ipv4     2 udp      17 30 src=10.10.2.1 dst=217.31.202.100 sport=36378 dport=123 "
            "packets=1 bytes=76 src=217.31.202.100 dst=172.20.6.87 sport=123 dport=36378 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 unknown  2 491 src=0.0.0.0 dst=224.0.0.1 packets=509 bytes=16288 [UNREPLIED] "
            "src=224.0.0.1 dst=0.0.0.0 packets=0 bytes=0 mark=0 zone=0 use=2",
            "ipv4     2 tcp      6 7383 ESTABLISHED src=172.20.6.100 dst=172.20.6.87 sport=48328 "
            "dport=80 packets=282 bytes=18364 src=172.20.6.87 dst=172.20.6.100 sport=80 dport=48328 "
            "packets=551 bytes=31002 [ASSURED] mark=0 zone=0 use=2",
            "ipv4     2 udp      17 30 src=10.111.222.213 dst=37.157.198.150 sport=60162 dport=123 "
            "packets=1 bytes=76 src=37.157.198.150 dst=172.20.6.87 sport=123 dport=60162 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 udp      17 34 src=10.111.222.213 dst=192.168.1.101 sport=57085 dport=123 "
            "packets=1 bytes=76 src=80.211.195.36 dst=172.20.6.87 sport=123 dport=57085 packets=1 "
            "bytes=76 mark=0 zone=0 use=2",
            "ipv4     2 tcp      6 7440 ESTABLISHED src=172.20.6.100 dst=172.20.6.87 sport=35774 "
            "dport=22 packets=244 bytes=17652 src=172.20.6.87 dst=172.20.6.100 sport=22 dport=35774 "
            "packets=190 bytes=16637 [ASSURED] mark=0 zone=0 use=2",
            "ipv4     2 udp      17 173 src=127.0.0.1 dst=127.0.0.1 sport=42365 dport=53 packets=2 "
            "bytes=120 src=127.0.0.1 dst=127.0.0.1 sport=53 dport=42365 packets=2 bytes=164 [ASSURED] "
            "mark=0 zone=0 use=2",
            "ipv6     10 udp      17 41 src=fd52:ad42:910e:0000:0000:0000:0000:64fa "
            "dst=fd21:36f9:644e:0000:0000:0000:0000:0001 sport=59532 dport=53 packets=1 bytes=102 "
            "src=fd21:36f9:644e:0000:0000:0000:0000:0001 dst=fd52:ad42:910e:0000:0000:0000:0000:64fa "
            "sport=53 dport=59532 packets=1 bytes=263 mark=0 zone=0 use=2"
        ]
    )
    with FileFaker(
        FILE_ROOT_PATH, "/tmp/dhcp.leases", False, leases
    ) as lease_file,\
        FileFaker(
        FILE_ROOT_PATH, "/proc/net/nf_conntrack", False, conntrack
    ) as conntrack_file:
        yield lease_file, conntrack_file


@pytest.fixture(scope="function")
def mount_on_netboot():
    script = """\
#!/bin/sh
cat << EOF
tmpfs on /tmp type tmpfs (rw,nosuid,nodev,noatime)
tmpfs on /dev type tmpfs (rw,nosuid,relatime,size=512k,mode=755)
EOF
"""
    with FileFaker(SCRIPT_ROOT_DIR, "/bin/mount", True, script) as mount_script:
        yield mount_script


@pytest.fixture(scope="function")
def mount_on_normal():
    script = """\
#!/bin/sh
cat << EOF
/dev/mmcblk0p1 on / type btrfs (rw,noatime,ssd,noacl,space_cache,commit=5,subvolid=397,subvol=/@)
devtmpfs on /dev type devtmpfs (rw,relatime,size=1033476k,nr_inodes=189058,mode=755)
proc on /proc type proc (rw,nosuid,nodev,noexec,noatime)
sysfs on /sys type sysfs (rw,nosuid,nodev,noexec,noatime)
cgroup on /sys/fs/cgroup type cgroup (rw,nosuid,nodev,noexec,relatime,cpuset,cpu,cpuacct,blkio,memory,devices,freezer,\
net_cls,pids,rdma,debug)
tmpfs on /tmp type tmpfs (rw,nosuid,nodev,noatime)
tmpfs on /dev type tmpfs (rw,nosuid,relatime,size=512k,mode=755)
devpts on /dev/pts type devpts (rw,nosuid,noexec,relatime,mode=600,ptmxmode=000)
debugfs on /sys/kernel/debug type debugfs (rw,noatime)
EOF
"""
    with FileFaker(SCRIPT_ROOT_DIR, "/bin/mount", True, script) as mount_script:
        yield mount_script


@pytest.fixture(scope="function")
def netboot_configured():
    with FileFaker(FILE_ROOT_PATH, "/tmp/netboot-configured", False, "") as configured_indicator:
        yield configured_indicator


@pytest.fixture(scope="module")
def env_overrides():
    return {
        "FC_DISABLE_ADV_CACHE": "1",
    }


@pytest.fixture(scope="function")
def fix_mox_wan(infrastructure, device):
    """ Uci networks.wan.ifname should be eth0 on mox and eth2 on turris1x"""
    if device.startswith("mox"):
        uci = get_uci_module(infrastructure.name)
        with uci.UciBackend(UCI_CONFIG_DIR_PATH) as backend:
            backend.set_option("network", "wan", "device", "eth0")


@pytest.fixture(scope="session")
def uci_config_default_path():
    return DEFAULT_UCI_CONFIG_DIR


@pytest.fixture(scope="session")
def cmdline_script_root():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_root")


@pytest.fixture(scope="session")
def file_root():
    # default src dirctory will be the same as for the scripts  (could be override later)
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_root")


@pytest.fixture(scope="module")
def controller_modules():
    return [
        "about",
        "web",
        "dns",
        "maintain",
        "password",
        "updater",
        "lan",
        "system",
        "time",
        "wan",
        "router_notifications",
        "wifi",
        "networks",
        "guest",
        "remote",
        "introspect",
    ]
