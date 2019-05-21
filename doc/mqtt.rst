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

   +------------------+-------------------+-------------------+
   |    Client        |   Fosquitto       | Controller        |
   |------------------|-------------------|-------------------|
1. | Subscribe        >  ../XXX-XXX-XXX   |                   |
2. | Publish          >  ../module/action |                   |
3. |                  |  ../module/action > Message           |
4. |                  |  ../XXX-XXX-XXX   < Publish           |
5. | Message          <  ../XXX-XXX-XXX   |                   |
6. | Unsubscribe      >  ../XXX-XXX-XXX   |                   |
   +------------------+-------------------+-------------------+

Restarts
--------
A problem may appeare when a fosquitto is restarted between the protocol states (1-6).
Fosquitto itself should restore the subscriptions state (`persistence` option), but
it might not help in some situations and the message might get lost.

1 to 2
______

Client is notified that a message was not published.

Client should wait till connected and resend it.

2 to 3
______

Client timeouts. Controller doesn't recieve the message.

If it take a bit long client should send a query to controller whether controller recieved the message.

3 to 4
______

Controller got the messages but it was disconnected afterwards.

Controller should try to publish response once it is connected.

4 to 5
______

Client doens't get the response although the response is send from the controller point of view.

Retain of message (fosquitto feature) might help here. If message is marked as retained. The last message of the topic is resend.

5 to 6
______

Client is unable to unsubscribe a topic.

Client should retry to unsubscribe the topic.
