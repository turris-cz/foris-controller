#!/usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2022, CZ.NIC z.s.p.o. (https://www.nic.cz/)

import argparse
import json
import sys

WIFI_DATA = {
    "info": {
        "radio0": {
            "phy": "phy0",
            "bssid": "AA:BB:CC:DD:EE:FF",
            "country": "US",
            "mode": "Client",
            "frequency_offset": 0,
            "txpower": 6,
            "txpower_offset": 0,
            "quality_max": 70,
            "noise": 0,
            "htmodes": [
                "HT20",
                "HT40",
                "VHT20",
                "VHT40",
                "VHT80",
                "VHT160",
                "HE20",
                "HE40",
                "HE80",
                "HE160"
            ],
            "hwmodes": [
                "ac",
                "ax",
                "n"
            ],
            "hwmode": "a/g",
            "htmode": "20",
            "hardware": {
                "id": [
                    5315,
                    30997,
                    5315,
                    30997
                ],
                "name": "MediaTek MT7915E"
            }
        },
        "radio1": {
            "phy": "phy1",
            "country": "US",
            "frequency_offset": 0,
            "txpower_offset": 0,
            "quality_max": 70,
            "noise": 0,
            "htmodes": [
                "HT20",
                "HT40"
            ],
            "hwmodes": [
                "b",
                "g",
                "n"
            ],
            "hardware": {
                "id": [
                    5772,
                    46,
                    5772,
                    12452
                ],
                "name": "Atheros AR9287"
            }
        },
    },
    "freqlist": {
        "radio0": {
            "results": [
                {
                    "channel": 1,
                    "mhz": 2412,
                    "restricted": False
                },
                {
                    "channel": 2,
                    "mhz": 2417,
                    "restricted": False
                },
                {
                    "channel": 3,
                    "mhz": 2422,
                    "restricted": False
                },
                {
                    "channel": 4,
                    "mhz": 2427,
                    "restricted": False
                },
                {
                    "channel": 5,
                    "mhz": 2432,
                    "restricted": False
                },
                {
                    "channel": 6,
                    "mhz": 2437,
                    "restricted": False
                },
                {
                    "channel": 7,
                    "mhz": 2442,
                    "restricted": False
                },
                {
                    "channel": 8,
                    "mhz": 2447,
                    "restricted": False
                },
                {
                    "channel": 9,
                    "mhz": 2452,
                    "restricted": False
                },
                {
                    "channel": 10,
                    "mhz": 2457,
                    "restricted": False
                },
                {
                    "channel": 11,
                    "mhz": 2462,
                    "restricted": False
                },
                {
                    "channel": 12,
                    "mhz": 2467,
                    "restricted": False
                },
                {
                    "channel": 13,
                    "mhz": 2472,
                    "restricted": False
                },
                {
                    "channel": 36,
                    "mhz": 5180,
                    "restricted": False
                },
                {
                    "channel": 40,
                    "mhz": 5200,
                    "restricted": False
                },
                {
                    "channel": 44,
                    "mhz": 5220,
                    "restricted": False
                },
                {
                    "channel": 48,
                    "mhz": 5240,
                    "restricted": False
                },
                {
                    "channel": 52,
                    "mhz": 5260,
                    "restricted": False
                },
                {
                    "channel": 56,
                    "mhz": 5280,
                    "restricted": False
                },
                {
                    "channel": 60,
                    "mhz": 5300,
                    "restricted": False
                },
                {
                    "channel": 64,
                    "mhz": 5320,
                    "restricted": False
                },
                {
                    "channel": 68,
                    "mhz": 5340,
                    "restricted": False
                },
                {
                    "channel": 72,
                    "mhz": 5360,
                    "restricted": False
                },
                {
                    "channel": 76,
                    "mhz": 5380,
                    "restricted": False
                },
                {
                    "channel": 80,
                    "mhz": 5400,
                    "restricted": False
                },
                {
                    "channel": 84,
                    "mhz": 5420,
                    "restricted": False
                },
                {
                    "channel": 88,
                    "mhz": 5440,
                    "restricted": False
                },
                {
                    "channel": 92,
                    "mhz": 5460,
                    "restricted": False
                },
                {
                    "channel": 96,
                    "mhz": 5480,
                    "restricted": False
                },
                {
                    "channel": 100,
                    "mhz": 5500,
                    "restricted": False
                },
                {
                    "channel": 104,
                    "mhz": 5520,
                    "restricted": False
                },
                {
                    "channel": 108,
                    "mhz": 5540,
                    "restricted": False
                },
                {
                    "channel": 112,
                    "mhz": 5560,
                    "restricted": False
                },
                {
                    "channel": 116,
                    "mhz": 5580,
                    "restricted": False
                },
                {
                    "channel": 120,
                    "mhz": 5600,
                    "restricted": False
                },
                {
                    "channel": 124,
                    "mhz": 5620,
                    "restricted": False
                },
                {
                    "channel": 128,
                    "mhz": 5640,
                    "restricted": False
                },
                {
                    "channel": 132,
                    "mhz": 5660,
                    "restricted": False
                },
                {
                    "channel": 136,
                    "mhz": 5680,
                    "restricted": False
                },
                {
                    "channel": 140,
                    "mhz": 5700,
                    "restricted": False
                },
                {
                    "channel": 144,
                    "mhz": 5720,
                    "restricted": False
                },
                {
                    "channel": 149,
                    "mhz": 5745,
                    "restricted": False
                },
                {
                    "channel": 153,
                    "mhz": 5765,
                    "restricted": False
                },
                {
                    "channel": 157,
                    "mhz": 5785,
                    "restricted": False
                },
                {
                    "channel": 161,
                    "mhz": 5805,
                    "restricted": False
                },
                {
                    "channel": 165,
                    "mhz": 5825,
                    "restricted": False
                },
                {
                    "channel": 169,
                    "mhz": 5845,
                    "restricted": False
                },
                {
                    "channel": 173,
                    "mhz": 5865,
                    "restricted": False
                },
                {
                    "channel": 177,
                    "mhz": 5885,
                    "restricted": False
                },
                {
                    "channel": 181,
                    "mhz": 5905,
                    "restricted": False
                }
            ]
        },
        "radio1": {
            "results": [
                {
                    "channel": 1,
                    "mhz": 2412,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 2,
                    "mhz": 2417,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 3,
                    "mhz": 2422,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 4,
                    "mhz": 2427,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 5,
                    "mhz": 2432,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 6,
                    "mhz": 2437,
                    "restricted": False,
                    "active": True
                },
                {
                    "channel": 7,
                    "mhz": 2442,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 8,
                    "mhz": 2447,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 9,
                    "mhz": 2452,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 10,
                    "mhz": 2457,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 11,
                    "mhz": 2462,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 12,
                    "mhz": 2467,
                    "restricted": False,
                    "active": False
                },
                {
                    "channel": 13,
                    "mhz": 2472,
                    "restricted": False,
                    "active": False
                }
            ]
        },
    }
}

IPV6_DHCP_DATA = {
    "device": {
        "br-lan": {
            "leases": [
                {
                    "duid": "00010003d8e63397f73ed8cd7cda",
                    "iaid": 987654321,
                    "hostname": "prvni",
                    "accept-reconf": False,
                    "assigned": 801,
                    "flags": [
                        "bound"
                    ],
                    "ipv6-addr": [
                        {
                            "address": "fd52:ad42:a6c9::64fe",
                            "preferred-lifetime": -1,
                            "valid-lifetime": -1
                        }
                    ],
                    "valid": 40029
                },
                {
                    "duid": "00020000df167896750a08ce0782",
                    "iaid": 123456789,
                    "hostname": "druhy",
                    "accept-reconf": False,
                    "assigned": 2033,
                    "flags": [
                        "bound"
                    ],
                    "ipv6-addr": [
                        {
                            "address": "fd52:ad42:a6c9::64fa",
                            "preferred-lifetime": -1,
                            "valid-lifetime": -1
                        },
                        {
                            "address": "fd52:ad42:910e::64fa",
                            "preferred-lifetime": -1,
                            "valid-lifetime": -1
                        }
                    ],
                    "valid": 39844
                }
            ]
        }
    }
}


def handle_dhcp(args):
    print(json.dumps(IPV6_DHCP_DATA, indent=2))


def handle_dummy_noreturn(args) -> None:
    # dummy service that does not return data (for instance: `ubus call umdns reload`)
    return None


def handle_iwinfo(args):
    if args.method not in ["info", "freqlist"]:
        print({})
    else:
        device = json.loads(args.message).get("device")
        print(json.dumps(WIFI_DATA[args.method].get(device, {}), indent=2))


UBUS_OBJECT_MAP = {
    "dhcp": handle_dhcp,
    "dummy_noreturn": handle_dummy_noreturn,
    "iwinfo": handle_iwinfo,
}


def main():
    parser = argparse.ArgumentParser(prog="ubus")
    parser.add_argument("command")
    parser.add_argument("object", help="ubus object")
    parser.add_argument("method", help="ubus object method")
    parser.add_argument("message", help="message", nargs="?")

    args = parser.parse_args()

    if args.command == "call":
        if args.object in UBUS_OBJECT_MAP:
            UBUS_OBJECT_MAP[args.object](args)
        else:
            sys.exit(1)  # querying nonexisting ubus object should return non-zero exit code to signalize failure
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
