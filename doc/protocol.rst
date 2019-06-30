Protocol
========

The protocol uses json to exchange data.
It consists of three kinds of messages.

Kinds
*****

Request
-------

Created by the **client**. It can have 4 kinds of fields:

* kind *mandatory* - fixed string `request`
* module *mandatory* - some kind of namespace - `wan`, `lan`, `dns`
* action *mandatory* - the name of the action to be triggered - `update_setting`, `get_settings`
* data *optional* - JSON data for the action can - `{"hostname": "localhost"}`

Exapmles::

   {
      "kind": "request",
      "module": "lan",
      "action": "get_settings",
   }

   {
      "kind": "request",
      "module": "lan",
      "action": "update_settings",
      "data": {"router_ip": "192.168.1.1", ...}
   }


Reply
-----

Created by the **controller**. It can have 5 kinds of fields:

* kind *mandatory* - fixed string `reply`
* module *mandatory* - some kind of namespace - `wan`, `lan`, `dns`
* action *mandatory* - the name of the action to be triggered - `update_setting`, `get_settings`
* data *optional* - JSON data for the action can - `{"result": true}`
* errors *optional* - list of internal errors

Reply should not contain `data` when `errors` is present.

Examples::

   {
      "kind": "reply",
      "module": "lan",
      "action": "get_settings",
      "data": {"router_ip": "192.168.1.1", ...}
   }

   {
      "kind": "reply,
      "module": "lan",
      "action": "update_settings",
      "errors": [{"description": "...", "stacktrace": "..."}]
   }


Notification
------------

Created by the  **controller**. It can have 4 kinds of fields:

* kind *mandatory* - fixed string `notification`
* module *mandatory* - some kind of namespace - `wan`, `lan`, `dns`
* action *mandatory* - name of the event which occured - `update_setting`, `reboot`
* data *optional* - JSON data for the action can - `{"hostname": "localhost"}`


Examples::

   {
      "kind": "notification",
      "module": "lan",
      "action": "update_settings",
      "data": {"router_ip": "192.168.1.1", ...}
   }


Basic rules
***********

Client sends request and waits for the reply from the controller
Only one reply per request is allowed.
The request and reply are supposed to have the same action name.


Notification are send only by the controller. Notification can be related to request/reply (e.g. settings were updated) or
they can be independent (reboot will be performed). Notification are send to all connected clients.


Typical Workflows
*****************

Synchronous
-----------
Client sends a request and it awaits immediate response from the controller.
The controller MAY generate a notification.

Example::

   -> {"kind": "request", "module": "updater", "update_settings", "data": {"enabled": false}}
   <- {"kind": "reply", "module": "updater", "update_settings", "data": {"result": true}}
   <= {"kind": "notification", "module": "updater", "update_settings", "data": {"enabled": false}}


Asynchronous
------------
Some action can take a significant amount of time and the clients are not supposed to be blocked
while waiting for the results. In this case it is possible to perform the commands in the async way.
This means that the reply doesn't contain the actual response, but only some kind of async identifier,
which can be used to determine the list of related notifications.

Example::

   -> {"kind": "request", "module": "remote", "generate_ca"}
   <- {"kind": "reply", "module": "remote", "generate_ca", "data": {"task_id": "aaaa-bbbb-cccc"}}
   <= {"kind": "notification", "module": "remote", "generate_ca", "data": {"task_id": "aaaa-bbbb-cccc", "status": "ca_done"}}
   <= {"kind": "notification", "module": "remote", "generate_ca", "data": {"task_id": "aaaa-bbbb-cccc", "status": "server_done"}}
   <= {"kind": "notification", "module": "remote", "generate_ca", "data": {"task_id": "aaaa-bbbb-cccc", "status": "succeeded"}}


System State
------------
When a system event occurs a set of notifications may be generated report the new state/situation.

Example::

   <= {"kind": "notification", "module": "maintain", "reboot", "data": {"remains": 300, ...}}
   <= {"kind": "notification", "module": "maintain", "reboot", "data": {"remains": 200, ...}}
   <= {"kind": "notification", "module": "maintain", "reboot", "data": {"remains": 100, ...}}
   <= {"kind": "notification", "module": "maintain", "reboot", "data": {"remains": 0, ...}}
