MQTT
====
A message bus which can be used to deliver messages to particular entities (publish/subscribe only).
Based on network sockets. Program which provides MQTT capabilities on our routers is called Fosquitto (instance of mosquitto).

Fosquitto
---------

* can some kind of interdevice message bus (forwards)
* multiple controllers can be attached
* multiple clients can be attached
* local connections autheticated by username and password
* remote connections protected authenticated by client TLS certificate

Protocol
--------

Subsribing for notifications is quite easy. Mqtt client just subscribes to *foris-controller/<ID>/notification/<module>/action/<action>* topic.
Or to *foris-controller/+/notification/+/action/+* to recieve all notifications from all controllers.

The request/reply pattern is harder to achieve, because it is not a basic part of the mqtt protocol and it has to be implemented using subscribe/publish.

basic overview::

         +------------------+---------------------------------------------------------+-------------------+
         |    Client        |    Fosquitto                                            | Controller        |
         |------------------|---------------------------------------------------------|-------------------|
      1. | Subscribe        >  foris-controller/<ID>/reply/<UUID>                     |                   |
      2. | Publish          >  foris-controller/<ID>/request/<module>/action/<action> |                   |
      3. |                  |  foris-controller/<ID>/request/<module>/action/<action> > Message           |
      4. |                  |  foris-controller/<ID>/reply/<UUID>                     < Publish           |
      5. | Message          <  foris-controller/<ID>/reply/<UUID>                     |                   |
      6. | Unsubscribe      >  foris-controller/<ID>/reply/<UUID>                     |                   |
         +------------------+---------------------------------------------------------+-------------------+

Restarts
********
A problem may appeare when a fosquitto is restarted between the protocol states (1-6).
Fosquitto itself should restore the subscriptions state (*persistence* option), but
it might not help in some situations and the message might get lost.

1 to 2
______

Problem
  Client is notified that a message was not published.

Remedy
  Client should wait till connected and resend it.

2 to 3
______

Problem
  Client timeouts. Controller doesn't recieve the message.

Remedy
  If it take a bit long client should send a query to controller whether controller recieved the message.

3 to 4
______

Problem
  Controller got the messages but it was disconnected afterwards.

Remedy
  Controller should try to publish response once it is connected.

4 to 5
______

Problem
  Client doens't get the response although the response is send from the controller point of view.

Remedy
  Retain of message (fosquitto feature) might help here. If message is marked as retained. The last message of the topic is resend.

5 to 6
______

Problem
  Client is unable to unsubscribe a topic.

Remedy
  Client should retry to unsubscribe the topic.


Details
*******

Step 1
______

A **client** **subscribes** for topic *foris-controller/<ID>/reply/<UUID>* where

*<ID>*
  is controller id that client is about to query

*<UUID>*
  is randomly generated UUID (has to be generated for each request/reply call)

Step 2
______

A **client** **pulishes** a message into topic *foris-controller/<ID>/request/<module>/action/<action>* where

*<ID>*
  is controller id that client is about to query

*<module>*
  is a module name which will be used

*<action>*
  is the name of the action to be performed

The message format here is a bit different from the standard foris message protocol::

   {
     "reply_msg_id": "<UUID>",
     "data": {
       ...
     }
   }

*<UUID>*
  is UUID generated in the previous step

*data*
  are the actual data which are required for the action


Step 3
______

**Fosquitto** delivers the message to particular **controller**.

Step 4
______

**Controller** prepares the response and **publishes** it to *foris-controller/<ID>/reply/<UUID>* where

*<ID>*
  is controller id that client is about to query

*<UUID>*
  is unique UUID which was recieved as a part of the request (*reply_msg_id* field)

Step 5
______

**Fosquitto** delivers the message to particular **client**.

Step 6
______

**Client** unsubscribes from *foris-controller/<ID>/reply/<UUID>* topic.


Advertizements
--------------

Every controller connected to fosquitto signals to the clients that it is available
by periodically sending following notification::

   {
     "module": "remote",
     "action": "advertize",
     "kind": "notification",
     "data": {
       "state": "running",
       "id": "0000000B00009CD6",
       "working_replies": [
         "0abb63a5-66cc-4ff2-91ed-606ece8ef93f"
       ],
       "netboot": "no",
       "modules": [
         {
           "name": "about",
           "version": "1.0.1"
         },
         {
           "name": "data_collect",
           "version": "1.1"
         },
         ...
       ]
     }
   }

*id*
  is the controler id which send the advertizement

*working_replies*
  list of UUIDs of the replies which is controller currently processing

*modules*
  list of all modules including its version

*netboot*
  state of netbooted devices (*no* - normal device, *booted* - unconfigured netbooted device, *ready* - configured netboot device)


Note that to recieve advertizements you need to subscribe to  *foris-controller/+/notification/remote/action/advertize* topic.

Monitoring
----------

The best way to figure out how does the protocol acutally works is to connect to the device via SSH and start the monitoring::

   fosquitto-monitor listen

The actual output can look like this::

   ===================== message recieved for 'foris-controller/0000000B00009CD6/request/web/action/set_language' =====================
   {
     "reply_msg_id": "d4956689-883f-4ba7-af16-1802c9b1d1e0",
     "data": {
       "language": "cs"
     }
   }
   ====================================================================================================================================
   ===================== message recieved for 'foris-controller/0000000B00009CD6/notification/web/action/set_language' =====================
   {
     "module": "web",
     "kind": "notification",
     "action": "set_language",
     "data": {
       "language": "cs"
     }
   }
   =========================================================================================================================================
   ===================== message recieved for 'foris-controller/0000000B00009CD6/reply/d4956689-883f-4ba7-af16-1802c9b1d1e0' =====================
   {
     "kind": "reply",
     "module": "web",
     "action": "set_language",
     "data": {
       "result": true
     }
   }
   ===============================================================================================================================================
   ===================== message recieved for 'foris-controller/0000000B00009CD6/reply/d4956689-883f-4ba7-af16-1802c9b1d1e0' =====================
   b''
   ===============================================================================================================================================


The output above can be generated by running::

   foris-client-wrapper -m web -a set_language -I '{"language":"en"}'


The last record is controller telling mosquitto to remove the reply from mosquitto's cache.

Note than if you want to see advertizements as well use::

   fosquitto monitor -a
