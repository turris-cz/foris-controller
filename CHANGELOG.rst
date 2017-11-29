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
