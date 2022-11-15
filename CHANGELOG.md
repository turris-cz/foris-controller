# Changelog
All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Add new backend "ubus" for querying `/bin/ubus`.

### Changed
- lan+wan: refactor querying ubus from lan & wan backends.

## [5.4.0] - 2022-12-15
### Added
- wifi: Allow disabling Management Frame Protection (IEEE 802.11w) for WPA3
  encryption modes (WPA2/3 and WPA3). It might help when wifi clients are
  having trouble connecting to the wifi Access Point.
- wan: Allow setting VLAN ID for WAN interface
- networks: Add optional VLAN ID of interface to the json schema

### Changed
- setup: bump turrishw version to 0.10.0
- wan: Reuse shared 'vlan_id' definition in the json schema

## [5.3.0] - 2022-11-22
### Changed
- wan: store wan interface L2 options in separate device section
- lan: use ubus call instead of parsing odhcpd files to get DHCPv6 leases

## [5.2.0] - 2022-07-15
### Added
- updater: Use type annotations from updater supervisor

### Fixed
- updater: handling of "reboot is required" from updater supervisor;
    it is now possible to approve update request in reForis

### Changed
- setup.py: bump foris-controller-testtools version to 0.12.0

## [5.1.0] - 2022-06-27
### Fixed
- networks: Sort interfaces by port names and disregard order in uci config

### Changed
- wifi: refactor sorting of htmodes
- networks: allow managing of interfaces on Turris 1.x (previously disabled)
- setup.py: update turrishw dependency to 0.9.0, so we can tell which ethernet port
    belongs to which Mox module again on TOS 6.0.

## [5.0.0] - 2022-05-18
### Added
- lan: allow managing of DHCPv4 static leases (create, update, delete)

### Changed
- lan: make message data mandatory for update_settings
- lan: add static boolean flag to dhcpv4 clients list

## [4.2.0] - 2022-03-04
### Added
- wifi: 802.11ax HE modes (20, 40, 80 and 160); 80+80 is not supported yet

### Changed
- wifi: read and write OpenWrt 21.02 config syntax, while being able to read OpenWrt 19.07 config syntax

## [4.1.1] - 2022-02-16
### Fixed
- mDNS/zeroconf entry has invalid service type

## [4.1.0] - 2022-02-04
### Added
- read and write OpenWrt 21.02 network config, while being able to read OpenWrt 19.07 config

### Changed
- mqtt: make advertizments a bit more efficient

### Fixed
- lan: Disable IPv6 server and ra when DHCP is disabled
- networks: fix detection of wifi interfaces
- guest: fix guest network firewall rules

## [4.0.0] - 2021-11-02
### Added:
- wifi: allow setting wifi encryption modes; it is possible to set different modes for regular and guest wifi

### Changed:
- wifi: use WPA2/WPA3 as default encryption mode

## [3.0.0] - 2021-10-22
### Added:
- wan: qos limit on traffic

### Changed:
- web: `list_languages` now uses reForis translations instead of Foris translations to determine available localization,
    since Foris is no longer present in TOS 5.3.0
- time: timezone is now set by backend based on provided region and city

### Fixed:
- networks: fix reading multiple interfaces of wan (e.g. bridge)
- wan: ipv6_address in 6in4 may contain prefix as well

## [2.1.3] - 2022-04-26
### Fixed
- networks: backport enabling managing of interfaces on Turris 1.x

## [2.1.2] - 2022-03-31
### Fixed
- wifi: wifi: backport fixes for reading HT modes; it is now possible to save
    wifi settings on Turris 1.x router or any router with DNXA-H1 wireless card

## [2.1.1] - 2021-09-14
### Fixed:
- networks: fix reading multiple interfaces of wan (e.g. bridge)
- wan: ipv6_address in 6in4 may contain prefix as well

## [2.1.0] - 2021-08-02
### Added:
- utils: add `ip_network_address` helper function

### Changed:
- router_notifications: change default "from" and "host" of custom smtp server to empty string

### Fixed:
- dns: fix setting custom forwarder port for non-TLS servers
- lan: update openvpn server push route configuration on lan update
- lan: fix crash on dhcp host which has multiple MAC addresses (contributed by ktetzlaff)
- lan: fix crash on negative dhcpv6 lease time; set it to 0 for now
- wan: add missing fw rule for 6to4
- zeroconf: Foris-controller won't fully start when something is running on port 5353

## [2.0.2] - 2021-07-12
### Fixed
- time: ntp default servers location

## [2.0.1] - 2021-07-02
### Fixed
- updater: provide URLs of package lists options
- updater: update package lists mock and tests (drop nikola, use fwlogs)

## [2.0.0] - 2021-06-24
### Added
- lan: enable qos control
- lan: provide IPv6 DHCP leases
- wan: provide MAC address of WAN interface
- time: add possibility to change NTP servers

### Changed
- uci: delete uci options gracefully

### Fixed
- computer mode: disable dhcpv6 server
- disable IPv6 DNS when IPv6 is disabled
- missing `ipv6_address` in 6in4 wan proto
- guest: enable dhcpv6
- wan: return empty strings when `wan6` uci options (`ip`, `network`, `gateway`) are not set

### Removed
- remove Manifest.in and simplify package_data

## [1.2] - 2021-02-02
### Added
- networks: include MAC address of interfaces

### Fixed
- zeroconf: update zconf service when IP changes
- wan: allow 6in4 tunnel without routed IPv6 prefix

## [1.1.0] - 2020-12-11
### Added
- about: get software customization
- updater: add installed packages query

### Changed
- wan: handle uci ip6prefix set as list
- zeroconf: export all IP addresses as properties
- example: set license for modules skeleton
- python2 to python3 refactoring
- Migrate CHANGELOG to Keep a Changelog style

### Fixed
- uci: perform `reload_config` command after uci commit

## [1.0.20] - 2020-10-29
- lan: allow control of 192.168.1.1 redirect
- tests: minor cleanup

## [1.0.19] - 2020-10-02
- example: fix typo in example test
- services: add openwrt service enabled state detection
- zeroconf: opt-in registration of a service
- system: add new core module
- about: suppress error log for get_contract()

## [1.0.18] - 2020-08-26

- web: Add 'shield' guide profile
- dns: more robust reading of custom DNS resolvers

## [1.0.17] - 2020-08-20

- wifi: fix reading of 802.11ac HT & VHT modes

## [1.0.16] - 2020-07-15
- wifi: return HT and VHT modes in natural sort order

## [1.0.15] - 2020-07-10
- wifi: basic detection of wireless capabilities through ubus

## [1.0.14] - 2020-07-01
- dns: save domain to 'option domain'
- updater: run updater after update of package lists and languages from reforis
- various fixes and improvements under the hood

## [1.0.13] - 2020-05-22
- updater: package lists api overhaul

## [1.0.12] - 2020-04-20
- wifi: remove wifi detect which is deprecated

## [1.0.11] - 2020-03-13
- dns: allow multiple ip addresses for DNS resolver

## [1.0.10] - 2020-02-11
- introspect: add new module

## [1.0.9] - 2020-01-09
- time: fix reading of three-level names timezones
- mqtt: fix advertizement state name when exitting

## [1.0.8] - 2019-11-13
- advertizements: fix incorrect state

## [1.0.7] - 2019-10-31
- cmdline: add env parameter to update newly created process env

## [1.0.6] - 2019-10-24
- about: fix typo in function call

## [1.0.5] - 2019-10-21
- dns: Fix add_forwarder WS notifications

## [1.0.4] - 2019-10-18
- about: get os branch from svupdater
- dns: add add_forwarder action
- tests: refactoring of tests

## [1.0.3] - 2019-08-29
- networks: get_network_info fix
- mqtt: custom announcements via python entry_points
- example project: using cookiecutter for generating new projects

## [1.0.2] - 2019-08-08
- client_socket: use controller_id - mqtt fix
- use ipaddress module instead of foris_controller_utils.IPv4 and remove IPv4
- removing python version ifs
- doc: protocol documentation added + mqtt doc extended
- lan: fix list dhcp clients (whitespace in mac field)
- remote: add hostname into advertize
- lan: show only valid ipv4 addresses in dns

## [1.0.1] - 2019-05-31
- remote: include module names and version into advertizements

## [1.0] - 2019-05-27
- mqtt: retry to send messages (with a small timeout)
- remote: add working_replies field into advertizements
- mqtt: allow to process messages concurrently
- mqtt: doc file which describes erroneous situations added
- mqtt: use retain and clean the messages afterwards
- tests: fix fork bomb
- router_notifications: making lang optional

## [0.11.14] - 2019-05-03
- updater: approval max delay period extended from 7 to 31 days

## [0.11.13] - 2019-04-29
- about: remove board_name
- lan: don't fail when mac is missing in static lease record
- time: don't require wifi uci file to save time settings
- lan: fix schema description

## [0.11.12] - 2019-04-05
- wan: wan6 defaults from 'none' to 'dhcpv6'
- updater: get enabled fix
- maintain: lighttpd restart command added

## [0.11.11] - 2019-04-01
- remote: display netboot status in advertize and add set_netboot_configured call
- all python source code reformatted using black
- updater: reflect api changes of svupdater
- time: properly set regulatory domain after timezone was updated
- lan: support for customizing static dhcp clients added
- wifi: update notification contains all new data
- router_notification: add separate functions for setting emails and reboots
- router_notification: different default

## [0.11.10] - 2019-03-13
- wifi+time: properly set regulatory domain (country)

## [0.11.9] - 2019-03-12
- wifi hack to tame iw command
- async cmds fix

## [0.11.8] - 2019-03-08
- suboridnates: api changes
- subordinates: send notification before restarting mqtt server
- mqtt: nicer client_id
- set proper controller_id in notifications
- subordinates: reload -> restart when managing (sub)subordinates
- about: atsha204 -> cryptowrapper migration
- remote module splitted into remote and subordinates
- remote: handlig of subsubordinates implemented

## [0.11.7] - 2019-02-14
- controller-id program arg fix
- remote: adding subordinates

## [0.11.6] - 2019-02-08
- updater: list api changes
- password: refuse to set compromised passwords
- socket_client: mqtt fix

## [0.11.5] - 2019-01-31
- mqtt: can set path to credentials file
- make controller_id configurable + update its format

## [0.11.4.1] - 2019-01-30
- updater: setting approval fix

## [0.11.4] - 2019-01-29
- updater: api chnaged (no need to use uci)
- make ubus and mqtt buses optional

## [0.11.3.1] - 2019-01-22
- mqtt: advertisement format fix

## [0.11.3] - 2019-01-21
- mqtt: request - reply protocol change
- mqtt: more resilent message handling

## [0.11.2] - 2019-01-20
- converting advertizements to regular notifications (remote.advertize)
- small code cleanups
- python2 is no longer supported

## [0.11.1] - 2019-01-16
- mqtt: more resilent announcer
- remote: module added
- guest+lan: handle '1d' as leasetime in uci

## [0.11] - 2018-12-21
- test structure reworked
- support for mqtt bus implemented

## [0.10.15] - 2018-12-12
- wan,lan: dns list backward compatibility

## [0.10.14] - 2018-12-05
- lan,wan,guest: interface_up_count attribute added
- networks: network_change notification added
- networks: display SSIDs

## [0.10.13] - 2018-11-30
- setup.py: cleanup + PEP508 updated
- networks: wifi handling updated

## [0.10.12] - 2018-11-07
- lan+wan+guest: handle missing wireless config
- networks: configurable and non-configurable interfaces
- turrishw: api update
- lan+wan: uci option fix when reading dns servers
- lan+guest: check dhcp range

## [0.10.11] - 2018-10-29
- time: display list of ntp servers used in get_settings
- about: remove temperature

## [0.10.10] - 2018-10-25
- about: remove contract related calls
- lan: get_settings more resilent
- web: new workflow (unset) and step(finished) added

## [0.10.9] - 2018-10-23
- dns: forwarders settings added
- small test updates
- about: firewall/ucollect sending info moved to foris-data_collect-module
- data_collect: module moved to a separate module (foris-data_collect-module)

## [0.10.8] - 2018-10-16
- lan+guest: show list of connected DHCP clients
- wan+lan+guest: display interface count
- lan: unmanaged mode added (device can act as a client /DHCP or static/ on LAN)
- guide: bridge workflow added
- turrishw integration (currently it obtains information about network interfaces)
- wifi: detect fix

## [0.10.7] - 2018-09-26
- maintain: move some logic to /usr/bin/maintain-reboot script
- setup.py: packages fix

## [0.10.6] - 2018-09-21
- guest+lan: added dhcp lease time option

## [0.10.5] - 2018-09-20
- pytest: deprecation warnings removed
- web: various guide updates regarding workflows
- maintain: reboot and restart network are done using external script
- lan: module splitted to lan and guest
- networks: module added
- wifi: making it compatible with newer version of openwrt

## [0.10.4] - 2018-08-29
- time module fixes
- python 3.7 compatilility fix
- web module language detect update

## [0.10.3] - 2018-08-17
- data_collect - get_registered fix and test update

## [0.10.2] - 2018-08-10
- test updates
- sample plugin updates
- display version + --version option
- support for locales with territory code (e.g. nb_NO)
- python3 compatibility
- CI with python3 integration
- create entrypoints for scripts

## [0.10.1] - 2018-06-19
- reflect foris-schema api update (it should boost the performace significantly)
- log how long some operations took
- ubus: message format changed
- wifi: when option path is missing try to detect the device based on mac address
- wifi: make reset to be compatible with newer version of openwrt
- wifi: set encryption only when it is unset or none
- wifi: too long SSID and guest wifi fix
- time: use ntpd instead of ntpdate to trigger time update

## [0.10.0] - 2018-05-22
- web: guide integration attempt

## [0.9.4] - 2018-05-22
- lan: guest network and sqm service fix
- wan: 6in4 support
- wan: 6to4 support
- wan: handle missing wan6 section
- uci: character `'` in values
- time: default value for ntp.enabled

## [0.9.3] - 2018-04-26
- wifi module: possible device path fix

## [0.9.2] - 2018-04-17
- updater module: new call get_enabled
- data_collect module: redownload registration code when router is not found
- wan module: new configuration options (duid, dhcp hostname) + some fixes
- wifi module: reset action added
- uci backend: import command added

## [0.9.1] - 2018-03-23
- syslog support removed (should be handled elsewhere)
- data_collect: remove i_agree_datacollect
- wifi: api updates

## [0.9] - 2018-03-21
- wifi module
- uci api update (reading anonymous section)
- foris-notify (some fixes)
- updater module & updater integration into other modules (maintain, web, data_collect)
- wan module - small fixes
- client socket (see doc/client_socket)

## [0.8.4] - 2018-02-23
- wan module added
- CI install updates
- connection test moved from dns to wan module
- router_notifications module added
- some schema fixes
- notifications count added to web module (get_data)

## [0.8.3] - 2018-02-07
- data_collect fixes
- services backend fail_on_error fix
- time module added

## [0.8.2] - 2018-01-15
- CI test are using openwrt backend as well as mock backend
- tests for sample plugin integrated into our CI
- tests can use a varios kind of overrides of fixtures (mostly to alter files paths)
- bigger tests refactoring (part of the tests moved to foris-controller-testtools repo)
- lan module implemented
- new functionality added to data_collect module

## [0.8.1] - 2017-12-20
- new password module added
- cmdline backend multiline fixes
- about module version parsing fixes

## [0.8] - 2017-12-13
- web module api updates
- maintain module added
- support for long messages (>1MB)
- --extra-module-path (set extra modules from cmdline)
- cmdline changes `-m mod1,mod2` -> `-m mod1 -m mod2`

## [0.7.3] - 2017-12-07
- about module - fix for older turris

## [0.7.2] - 2017-11-29
- dns module - use default value when an option is not present in uci
- uci - default argument to get_{named,anonymous}_option

## [0.7.1] - 2017-11-16
- async commands - python buffer fixes
- async commands - match stderr as well
- uci - added replace_list function

## [0.7] - 2017-11-07
- added backend to handle async commands
- dns module - connection check handling

## [0.6.2] - 2017-10-31
- uci backend fix
- web module - language switch fix

## [0.6.1] - 2017-10-24
- dns module reload fix
- calling external programs should be faster

## [0.6] - 2017-10-20
- support for sending notifications added (+docs +tests)
- added an option to put logging output into a file
- some fixes
- some code cleanup
- some documentation added

## [0.5] - 2017-10-02
- dns module (several option regarding dns)
- web module (language switch)
- wrapper around system services (start, stop, reload, ...)
- wrapper around uci command

## [0.4] - 2017-09-06
- docs updates
- put stack traces to error msgs
- write stack traces to debug console
- syslog integration

## [0.3] - 2017-09-04
- registration number call added
- contract valid call added
- router registered call added

## [0.2] - 2017-08-23
- --single argument for ubus
- making modules and backends modular
- locking moved to backends


## [0.1] - 2017-08-07
- initial version
