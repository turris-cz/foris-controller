Foris Controller
================
Read messages from message bus.
Stores and obtains data from backends (uci/augeas).

Language
--------
Python (2/3 or both)

Componets
---------

Listener
########
* listens to bus and recieves/sends messages back to bus
* should be replacible ubus/dbus ...
* it might change to content of the message (e.g. add / remove unique messsage-id)
* when a message is recieved a schema check should be performed (foris-schema lib)

Message Router
##############
* makes sure that the message is passed to a targeted module
* raises an exception when a module is missing

Modules
#######
* independent
* each module contains an json schema which describes a schema of the incomming messages
* each module is able to translate recieved messages to backend functions

Backend Router
##############
* locking / serialization / timeout
* exposes supported functions and links them with actual functions of some backends

Backends
########
* a bunch of backend classes (tree structure)

Protocol
--------

example1
########

>>> {"id": "1234", "kind": "request", "module": "wifi", "action": "get"}
Listener - input verification (thread calls a function)
>>> {"module": "wifi", "action": "get"}
Message Router
>>> {"action": "get"}
Wifi Module
>>> backend.get_current_wifi_settings()
>>> backend.obtain_card_info()
Backend Router (lock)
>>> configuration_backend.get_current_wifi_settings()
>>> command_backend.obtain_card_info()
Configuration backend(UCI backend) + Command backend(Shell backend)
>>> uci show wireless
>>> iw list
Configuration backend(UCI backend) + Command backend(Shell backend) - parsing
<<< {"card1": {...}, "card2": {...}} - configuration_backend.get_current_wifi_settings()
<<< {"phy0": {...}, "phy1": {...}} - command_backend.obtain_card_info()
Backend Router (unlock)
<<< {"card1": {...}, "card2": {...}} - backend.get_current_wifi_settings()
<<< {"phy0": {...}, "phy1": {...}} - backend.obtain_card_info()
Wifi Module
<<< {"card1": {"phy1": ...}, "card2": {"phy2": ...}}
Message Router
<<< {"module": "wifi", "action":"get", "data": {"card1": {"phy1": ...}, "card2": {"phy2": ...}}}
Listener - output verification
<<< {"id": "1234", "kind": "reply", "module": "wifi", "action":"get", "data": {"card1": {"phy1": ...}, "card2": {"phy2": ...}}}

example2
########

>>> {"id": "2345", "kind": "request", "module": "wifi", "action": "set", "data": {"card1": {"phy1": ...}, "card2": {"phy2": ...}}}
Listener - input verification (thread calls a function)
>>> {"module": "wifi", "action": "set", "data": {"card1": {"phy1": ...}, "card2": {"phy2": ...}}}
Message Router
>>> {"action": "set", "data": {"card1": {"phy1": ...}, "card2": {"phy2": ...}}}
Wifi Module
>>> backend.update_current_wifi_settings()
Backend Router (lock)
>>> configuration_backend.update_current_wifi_settings()
Configuration backend(UCI backend) + Service backend(procd)
>>> uci set wireless.card1.optionx=y
>>> ...
>>> uci commit
>>> /etc/init.d/network reload
Configuration backend(UCI backend) + Service backend(procd) - check response
<<< {"result": "OK"} - configuration_backend.update_wifi_settings()
Backend Router (unlock)
<<< {"result": "OK"} - backend.update_wifi_settings()
Wifi Module
<<< {"result": "OK"}
Message Router
<<< {"module": "wifi", "action":"set", "data": {"result": "OK"}}
Listener - output verification
<<< {"id": "2345", "kind": "reply", "module": "wifi", "action":"set", "data": {"result": "OK"}} (send as a reply)
<<< {"id": "3456", "kind": "notification", "module": "wifi", "action": "set"} (send as a notification - clients can reload page)
