#
# foris-controller
# Copyright (C) 2018 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import logging
import json
import os
import uuid
import re
import sys
import threading
import time

from paho.mqtt import client as mqtt

from foris_controller.app import app_info
from foris_controller.message_router import Router
from foris_controller.utils import get_modules, get_module_class, LOGGER_MAX_LEN

from .base import BaseNotificationSender, BaseSocketListener, get_method_names_from_module

logger = logging.getLogger(__name__)


ID = "%012x" % uuid.getnode()  # returns nodeid based on mac addr


bus_info = {"state": "starting", "bus_thread": None}

ANNOUNCER_PERIOD = float(os.environ.get("FC_MQTT_ANNOUNCER_PERIOD", 1.0)) # in seconds
ANNOUNCER_TOPIC = "foris-controller/advertize"


def announcer_worker(host, port):

    def on_connect(client, userdata, flags, rc):
        logger.debug("On connect.")
        if rc == 0:
            bus_info["state"] = "running"  # this thread should be started after initialization
            logger.debug("Announcer thread connected.")
            msg = {"state": "started", "id": ID}
            client.publish(ANNOUNCER_TOPIC, json.dumps(msg))
            logger.debug("Announcer thread publishes: %s", msg)
        else:
            logger.error("Failed to connect announcer thread! No announcements will be send.")

    def on_publish(client, userdata, mid):
        if bus_info["state"] == "running":
            time.sleep(ANNOUNCER_PERIOD or 1.0)
            if bus_info["bus_thread"].is_alive():
                if ANNOUNCER_PERIOD:  # don't announce when period is set to zero
                    msg = {"state": "running", "id": ID}
                    client.publish(ANNOUNCER_TOPIC, json.dumps(msg))
            else:
                msg = {"state": "exitted", "id": ID}
                client.publish(ANNOUNCER_TOPIC, json.dumps(msg))
                bus_info["state"] = "exitted"

            logger.debug("Announcer thread publishes: %s", msg)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    logger.debug("Announcer thread started. Trying to connect to '%s':'%d'", host, port)
    client.connect(host, port, keepalive=30)

    while bus_info["state"] != "exitted":
        client.loop(ANNOUNCER_PERIOD)


class MqttListener(BaseSocketListener):
    router = Router()
    subscriptions = {}

    @staticmethod
    def handle_on_connect(client, userdata, flags, rc):
        if rc != 0:
            logger.error("Failed to connect to the message bus (rc=%d).", rc)
            sys.exit(1)  # can't connect to bus -> exitting

        logger.debug(
            "Connected to mqtt server. (client='%s', userdata='%s', flags='%s', rc='%s')",
            client, userdata, flags, rc,
        )

        def check_subscription(rc, mid, topic):
            if rc != 0:
                logger.error("Failed to subscribe to '%s' (rc=%d, mid=%d).", topic, rc, mid)
                sys.exit(1)  # can't connect to bus -> exitting
            MqttListener.subscriptions[mid] = False

        # subscription for listing modules
        list_modules_topic = "foris-controller/%s/list" % ID
        rc, mid = client.subscribe(list_modules_topic)
        check_subscription(rc, mid, list_modules_topic)
        logger.debug("Subscribing to '%s'." % list_modules_topic)

        # subscription for obtaining the entire schema
        schema_topic = "foris-controller/%s/jsonschemas" % ID
        rc, mid = client.subscribe(schema_topic)
        check_subscription(rc, mid, schema_topic)
        logger.debug("Subscribing to '%s'." % schema_topic)

        # subscription for listing module actions
        action_topic = "foris-controller/%s/request/+/list" % ID
        rc, mid = client.subscribe(action_topic)
        check_subscription(rc, mid, action_topic)
        logger.debug("Subscribing to '%s'." % action_topic)

        # listen to all requests for my node
        request_topics = "foris-controller/%s/request/+/action/+" % ID
        rc, mid = client.subscribe(request_topics)
        check_subscription(rc, mid, request_topics)
        logger.debug("Subscribing to '%s'." % request_topics)

    @staticmethod
    def list_modules():
        res = []
        for module_name, module in get_modules(
            app_info["filter_modules"], app_info["extra_module_paths"]
        ):
            res.append({
                "name": module_name,
                "actions": get_method_names_from_module(module) or [],
            })
        return res

    @staticmethod
    def get_schema():
        return [app_info["validator"].base_validator.schema, app_info["validator"].error_schema] \
            + [e.schema for e in app_info["validator"].validators.values()]

    @staticmethod
    def list_actions(module_name):
        modules_dict = dict(
            get_modules(app_info["filter_modules"], app_info["extra_module_paths"]))
        return get_method_names_from_module(modules_dict.get(module_name)) or []

    @staticmethod
    def handle_on_message(client, userdata, msg):
        logger.debug(
            "Msg recieved. (client='%s', userdata='%s', topic='%s', payload='%s')",
            client, userdata, msg.topic, msg.payload,
        )

        try:
            parsed = json.loads(msg.payload)
        except ValueError:
            logger.warning("Payload is not a JSON (msg.payload='%s')", msg.payload)
            return  # message in wrong format

        if 'reply_topic' not in parsed:
            logger.warning("Missing mandatory reply_topic (data='%s')", parsed)
            return  # missing reply topic
        reply_topic = parsed['reply_topic']

        response = None

        # parse topic
        match = re.match(r"^foris-controller/[^/]+/list$", msg.topic)
        if match:
            response = MqttListener.list_modules()

        match = re.match(r"^foris-controller/[^/]+/jsonschemas$", msg.topic)
        if match:
            response = MqttListener.get_schema()

        match = re.match(r"^foris-controller/[^/]+/request/([^/]+)/list$", msg.topic)
        if match:
            module_name = match.group(1)
            response = MqttListener.list_actions(module_name)

        match = re.match(r"^foris-controller/[^/]+/request/([^/]+)/action/([^/]+)$", msg.topic)
        if match:
            module_name, action_name = match.group(1, 2)
            msg = {
                'module': module_name,
                'kind': 'request',
                'action': action_name,
            }
            if 'data' in parsed:
                msg['data'] = parsed['data']
            response = MqttListener.router.process_message(msg)

        if response is not None:
            client.publish(reply_topic, json.dumps(response))
        else:
            # This should not happen
            logger.error("Don't know how to respond.")

    def __init__(self, host, port):
        def on_subscribe(client, userdata, mid, granted_qos):
            MqttListener.subscriptions[mid] = True
            logger.debug("Subscribed to %d", mid)
            if not [e for e in MqttListener.subscriptions.values() if not e]:
                logger.debug("All subscriptions passed.")
                logger.debug("Starting announcer thread.")
                bus_info["bus_thread"] = threading.current_thread()
                announcer_thread = threading.Thread(
                    name="announcer_thread", target=announcer_worker, kwargs={
                        "host": host, "port": port,
                    },
                )
                announcer_thread.daemon = True
                announcer_thread.start()

        self.client = mqtt.Client()
        self.client.on_connect = MqttListener.handle_on_connect
        self.client.on_message = MqttListener.handle_on_message
        self.client.on_subscribe = on_subscribe
        self.client.connect(host, port, keepalive=30)

    def serve_forever(self):
        self.client.loop_forever()


class MqttNotificationSender(BaseNotificationSender):

    def _connect(self):
        def on_connect(client, userdata, flags, rc):
            self._connected = True
            if rc != 0:
                logger.error("Failed to connect to the message bus (rc=%d).", rc)
                sys.exit(1)  # can't connect to bus -> exitting

            logger.debug(
                "Notification sender connected to mqtt server. "
                "(client='%s', userdata='%s', flags='%s', rc='%s')",
                client, userdata, flags, rc,
            )

        def on_disconnect(client, userdata, rc):
            self._connected = False

        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.connect(self.host, self.port, keepalive=30)

    def __init__(self, host, port):
        logger.debug("Connecting to mqtt server.")

        self.host = host
        self.port = port
        self._connect()
        self._connected = True

    def _send_message(self, msg, module, action, data=None):
        logger.debug(
            "Sending notificaton (module='%s', action='%s', data='%s')" % (module, action, data))
        if not self._connected:
            self._connect()

        publish_topic = "^foris-controller/[^/]+/request/([^/]+)/action/([^/]+)$"
        publish_topic = "foris-controller/%s/notification/%s/action/%s" % (ID, module, action)
        self.client.publish(publish_topic, json.dumps(msg))
        logger.debug("Notification published. (topic=%s, msg=%s)", publish_topic, msg)

    def disconnect(self):
        if self._connected:
            logger.debug("Disconnecting mqtt")
            self.client.disconnect()

    def reset(self):
        logger.debug("Resetting connection (skipped no need to reset this bus).")