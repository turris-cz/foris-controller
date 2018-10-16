0.10.8 (2018-10-16)
-------------------

* lan+guest: show list of connected DHCP clients
* wan+lan+guest: display interface count
* lan: unmanaged mode added (device can act as a client /DHCP or static/ on LAN)
* guide: bridge workflow added
* turrishw integration (currently it obtains information about network interfaces)
* wifi: detect fix

0.10.7 (2018-09-26)
-------------------

* maintain: move some logic to /usr/bin/maintain-reboot script
* setup.py: packages fix

0.10.6 (2018-09-21)
-------------------

* guest+lan: added dhcp lease time option

0.10.5 (2018-09-20)
-------------------

* pytest: deprecation warnings removed
* web: various guide updates regarding workflows
* maintain: reboot and restart network are done using external script
* lan: module splitted to lan and guest
* networks: module added
* wifi: making it compatible with newer version of openwrt

0.10.4 (2018-08-29)
-------------------

* time module fixes
* python 3.7 compatilility fix
* web module language detect update

0.10.3 (2018-08-17)
-------------------

* data_collect - get_registered fix and test update

0.10.2 (2018-08-10)
-------------------

* test updates
* sample plugin updates
* display version + --version option
* support for locales with territory code (e.g. nb_NO)
* python3 compatibility
* CI with python3 integration
* create entrypoints for scripts

0.10.1 (2018-06-19)
------------------

* reflect foris-schema api update (it should boost the performace significantly)
* log how long some operations took
* ubus: message format changed
* wifi: when option path is missing try to detect the device based on mac address
* wifi: make reset to be compatible with newer version of openwrt
* wifi: set encryption only when it is unset or none
* wifi: too long SSID and guest wifi fix
* time: use ntpd instead of ntpdate to trigger time update

0.10.0 (2018-05-22)
------------------

* web: guide integration attempt

0.9.4 (2018-05-22)
------------------

* lan: guest network and sqm service fix
* wan: 6in4 support
* wan: 6to4 support
* wan: handle missing wan6 section
* uci: character `'` in values
* time: default value for ntp.enabled

0.9.3 (2018-04-26)
------------------

* wifi module: possible device path fix

0.9.2 (2018-04-17)
------------------

* updater module: new call get_enabled
* data_collect module: redownload registration code when router is not found
* wan module: new configuration options (duid, dhcp hostname) + some fixes
* wifi module: reset action added
* uci backend: import command added

0.9.1 (2018-03-23)
------------------

* syslog support removed (should be handled elsewhere)
* data_collect: remove i_agree_datacollect
* wifi: api updates

0.9 (2018-03-21)
----------------

* wifi module
* uci api update (reading anonymous section)
* foris-notify (some fixes)
* updater module & updater integration into other modules (maintain, web, data_collect)
* wan module - small fixes
* client socket (see doc/client_socket)

0.8.4 (2018-02-23)
------------------

* wan module added
* CI install updates
* connection test moved from dns to wan module
* router_notifications module added
* some schema fixes
* notifications count added to web module (get_data)

0.8.3 (2018-02-07)
------------------

* data_collect fixes
* services backend fail_on_error fix
* time module added

0.8.2 (2018-01-15)
------------------

* CI test are using openwrt backend as well as mock backend
* tests for sample plugin integrated into our CI
* tests can use a varios kind of overrides of fixtures (mostly to alter files paths)
* bigger tests refactoring (part of the tests moved to foris-controller-testtools repo)
* lan module implemented
* new functionality added to data_collect module

0.8.1 (2017-12-20)
------------------

* new password module added
* cmdline backend multiline fixes
* about module version parsing fixes

0.8 (2017-12-13)
----------------

* web module api updates
* maintain module added
* support for long messages (>1MB)
* --extra-module-path (set extra modules from cmdline)
* cmdline changes `-m mod1,mod2` -> `-m mod1 -m mod2`

0.7.3 (2017-12-07)
------------------

* about module - fix for older turris

0.7.2 (2017-11-29)
------------------

* dns module - use default value when an option is not present in uci
* uci - default argument to get_{named,anonymous}_option

0.7.1 (2017-11-16)
------------------

* async commands - python buffer fixes
* async commands - match stderr as well
* uci - added replace_list function

0.7 (2017-11-07)
----------------

* added backend to handle async commands
* dns module - connection check handling

0.6.2 (2017-10-31)
------------------

* uci backend fix
* web module - language switch fix

0.6.1 (2017-10-24)
------------------

* dns module reload fix
* calling external programs should be faster

0.6 (2017-10-20)
----------------

* support for sending notifications added (+docs +tests)
* added an option to put logging output into a file
* some fixes
* some code cleanup
* some documentation added

0.5 (2017-10-02)
----------------

* dns module (several option regarding dns)
* web module (language switch)
* wrapper around system services (start, stop, reload, ...)
* wrapper around uci command

0.4 (2017-09-06)
----------------

* docs updates
* put stack traces to error msgs
* write stack traces to debug console
* syslog integration

0.3 (2017-09-04)
----------------

* registration number call added
* contract valid call added
* router registered call added

0.2 (2017-08-23)
----------------

* --single argument for ubus
* making modules and backends modular
* locking moved to backends


0.1 (2017-08-07)
----------------

* initial version
