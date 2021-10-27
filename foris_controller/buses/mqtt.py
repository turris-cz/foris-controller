#
# foris-controller
# Copyright (C) 2019-2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import uuid
import os
import re
import socket
import sys
import threading
import time
import typing
import pkg_resources

from distutils.util import strtobool

from paho.mqtt import client as mqtt
from paho.mqtt.publish import single
from jsonschema import ValidationError

from foris_controller.app import app_info
from foris_controller.message_router import Router
from foris_controller.utils import get_modules

from .base import BaseNotificationSender, BaseSocketListener, get_method_names_from_module

logger = logging.getLogger(__name__)


bus_info = {"bus_thread": None}

ANNOUNCER_PERIOD_DEFAULT = 1.0  # in seconds
CLEAR_RETAIN_PERIOD = 10.0  # in seconds


class EntryPointAnnouncer:
    def __init__(self, period: int, callback: typing.Callable[[], typing.Optional[dict]]):
        self.callback = callback
        self.period = period
        self.last_called = 0

    def get_data(self, counter: int) -> typing.Optional[dict]:
        if self.period + self.last_called <= counter:
            self.last_called = counter
            return self.callback()


class AdvertizementBase:
    NETBOOT_FINAL = ["no", "ready"]  # "booting" should eventually become "ready"

    def __init__(self, state):
        self.state = state
        self.refresh()

    def refresh(self):
        self.id = app_info["controller_id"]
        self.hostname = socket.gethostname()
        self.modules = [{"name": k, "version": v.version} for k, v in app_info["modules"].items()]
        self.netboot = "unknown"  # initial state
        self.get_netboot()

    def get_netboot(self):
        """ Try to update obtain netboot status """
        if self.netboot in self.NETBOOT_FINAL:
            # netboot state will not change
            return
        try:
            self.netboot = app_info["modules"]["remote"].handler.get_netboot_status()
        except Exception:
            pass

    def build(self) -> dict:
        if strtobool(os.environ.get("FC_DISABLE_ADV_CACHE", "0")):
            self.refresh()
        self.get_netboot()  # try to update netboot state
        return {
            "state": self.state,
            "id": self.id,
            "hostname": self.hostname,
            "netboot": self.netboot,
            "modules": self.modules,
        }


def _publish(client: mqtt.Client, msg: dict):
    ANNOUNCER_TOPIC = (
        f"foris-controller/{app_info['controller_id']}/notification/"
        f"{msg['module']}/action/{msg['action']}"
    )
    try:
        logger.debug("Starting to validate announcement notification.")
        # Hope that calling validator is treadsafe otherwise
        # some locking mechanism should be implemented
        app_info["validator"].validate(msg)
        logger.debug("Publishing announcement notification. (%s)", msg)
        client.publish(ANNOUNCER_TOPIC, json.dumps(msg), qos=0)
    except ValidationError as exc:
        logger.error("Failed to validate announcement notification.")
        logger.debug("Error: \n%s" % str(exc))


def _publish_advertize(
    client: mqtt.Client,
    adv_base: AdvertizementBase,
    working_replies: typing.Dict[str, typing.Tuple[threading.Thread, float]],
    working_replies_lock: threading.Lock,
):
    data = adv_base.build()

    with working_replies_lock:
        data["working_replies"]: typing.List[str] = [e for e in working_replies.keys()]

    msg = {"module": "remote", "action": "advertize", "kind": "notification", "data": data}
    _publish(client, msg)


def announcer_worker(host, port, working_replies, working_replies_lock):
    def on_connect(client, userdata, flags, rc):
        logger.debug("Announcer handles connect.")
        if rc == 0:
            logger.debug("Announcer thread connected.")
            _publish_advertize(
                client, AdvertizementBase("started"), working_replies, working_replies_lock
            )
        else:
            logger.error("Failed to connect announcer thread!")

    def on_publish(client, userdata, mid):
        logger.debug("Announcer thread published.")

    client = mqtt.Client(client_id=f"{uuid.uuid4()}-controller-announcer", clean_session=False)
    client.on_connect = on_connect
    client.on_publish = on_publish
    logger.debug("Announcer thread started. Trying to connect to '%s':'%d'", host, port)
    if app_info["mqtt_credentials"]:
        client.username_pw_set(*app_info["mqtt_credentials"])
    client.connect(host, port, keepalive=30)

    client.loop_start()

    counter = 1

    # perpare entry points
    announcers: typing.List[EntryPointAnnouncer] = []
    for entry_point in pkg_resources.iter_entry_points("foris_controller_announcer"):
        logger.debug("Loading announcer entry point %s", entry_point.name)
        period, callback = entry_point.load()()
        announcers.append(EntryPointAnnouncer(period, callback))

    running_adv = AdvertizementBase("running")
    while bus_info["bus_thread"].is_alive():
        time.sleep(app_info["mqtt_announcer_period"] or ANNOUNCER_PERIOD_DEFAULT)
        if app_info["mqtt_announcer_period"]:
            _publish_advertize(
                client, running_adv, working_replies, working_replies_lock
            )
            for announcer in announcers:
                res = announcer.get_data(counter)
                if res:
                    _publish(client, res)

        counter += app_info["mqtt_announcer_period"]

    _publish_advertize(
        client, AdvertizementBase("exited"), working_replies, working_replies_lock
    )
    client.loop_stop()


class MqttListener(BaseSocketListener):
    router = Router()
    subscriptions: typing.Dict[int, bool] = {}

    @staticmethod
    def handle_on_connect(client, userdata, flags, rc):
        if rc != 0:
            logger.error("Failed to connect to the message bus (rc=%d).", rc)
            sys.exit(1)  # can't connect to bus -> exitting

        logger.debug(
            "Connected to mqtt server. (client='%s', userdata='%s', flags='%s', rc='%s')",
            client,
            userdata,
            flags,
            rc,
        )

        def check_subscription(rc, mid, topic):
            if rc != 0:
                logger.error("Failed to subscribe to '%s' (rc=%d, mid=%d).", topic, rc, mid)
                sys.exit(1)  # can't connect to bus -> exitting
            MqttListener.subscriptions[mid] = False

        def subscribe(topic):
            rc, mid = client.subscribe(topic, qos=0)
            check_subscription(rc, mid, topic)
            logger.debug("Subscribing to '%s'." % topic)

        # subscription for listing modules
        subscribe(f"foris-controller/{app_info['controller_id']}/list")

        # subscription for listing working replies
        subscribe(f"foris-controller/{app_info['controller_id']}/working_replies")

        # subscription for obtaining the entire schema
        subscribe(f"foris-controller/{app_info['controller_id']}/jsonschemas")

        # subscription for listing module actions
        subscribe(f"foris-controller/{app_info['controller_id']}/request/+/list")

        # listen to all requests for my node
        subscribe(f"foris-controller/{app_info['controller_id']}/request/+/action/+")

    @staticmethod
    def list_modules():
        res = []
        for module_name, module in get_modules(
            app_info["filter_modules"], app_info["extra_module_paths"]
        ):
            res.append({"name": module_name, "actions": get_method_names_from_module(module) or []})
        return res

    @staticmethod
    def get_schema():
        return [app_info["validator"].base_validator.schema, app_info["validator"].error_schema] + [
            e.schema for e in app_info["validator"].validators.values()
        ]

    @staticmethod
    def list_actions(module_name):
        modules_dict = dict(get_modules(app_info["filter_modules"], app_info["extra_module_paths"]))
        return get_method_names_from_module(modules_dict.get(module_name)) or []

    def list_working_replies(self):
        with self.working_replies_lock:
            return [e for e in self.working_replies.keys()]

    def start_message_worker(self, reply_topic: str, reply_id: str, msg: dict):
        """ Performs the work and sends the reply
        :param reply_topic: where the reply is supposed to be send
        :param reply_id: id of reply
        :param msg: message to be processed
        """
        auth: typing.Optional[typing.Dict[str, str]] = None
        if app_info.get("mqtt_credentials", None) and app_info["mqtt_credentials"]:
            auth = {
                "username": app_info["mqtt_credentials"][0],
                "password": app_info["mqtt_credentials"][1],
            }

        def work():
            # mark reply_id as working reply
            with self.working_replies_lock:
                self.working_replies[reply_id] = (threading.current_thread(), time.monotonic())

            response = MqttListener.router.process_message(msg)
            raw_response = json.dumps(response)
            kwargs = dict(
                payload=raw_response,
                qos=0,
                retain=True,
                hostname=self.host,
                port=self.port,
                auth=auth,
            )
            logger.debug("Publishing response '%s' to '%s'", response, reply_topic)
            try:
                single(reply_topic, **kwargs)
            except ConnectionRefusedError:
                # retry in case the connection was interrupted (due to fosquitto restart)
                logger.warning("Publishing response to '%s' failed (resending)", reply_topic)
                time.sleep(0.3)
                try:
                    single(reply_topic, **kwargs)
                except ConnectionAbortedError:
                    logger.error(
                        "Publishing response to '%s' failed (failed - message not sent))",
                        reply_topic,
                    )
                    raise
            logger.debug("Reply '%s' published.", reply_id)

            # clear retains
            time.sleep(CLEAR_RETAIN_PERIOD)
            logger.debug("Clearing retained messages '%s'", reply_topic)
            single(
                reply_topic,
                payload="",
                qos=2,
                retain=True,
                hostname=self.host,
                port=self.port,
                auth=auth,
            )
            logger.debug("Retained messages '%s' should be cleared", reply_topic)

            # unmark reply_id as working reply
            with self.working_replies_lock:
                try:
                    del self.working_replies[reply_id]
                except KeyError:
                    pass
                # perform a cleanup
                # (if corresponding thread is not alive and retain period was reached)
                ids_to_delete = [
                    k
                    for k, v in self.working_replies.items()
                    if not v[0].is_alive() and time.monotonic() - v[1] > CLEAR_RETAIN_PERIOD
                ]
                for del_id in ids_to_delete:
                    del self.working_replies[del_id]

        thread = threading.Thread(target=work, name=f"worker-{reply_id}", daemon=False)
        thread.start()

    def __init__(self, host: str, port: int):
        self.announcer_thread_running: bool = False
        self.mqtt_client_id: str = f"{uuid.uuid4()}-controller-request"
        self.host: str = host
        self.port: int = port
        self.working_replies: typing.Set[typing.Dict[str, threading.Thread]] = dict()
        self.working_replies_lock: threading.Lock = threading.Lock()

        def on_publish(client, userdata, mid):
            logger.debug("Mid %s is published", mid)

        def on_subscribe(client, userdata, mid, granted_qos):
            MqttListener.subscriptions[mid] = True
            logger.debug("Subscribed to %d", mid)
            if not [e for e in MqttListener.subscriptions.values() if not e]:
                logger.debug("All subscriptions passed.")
                if not self.announcer_thread_running:
                    logger.debug("Starting announcer thread.")
                    bus_info["bus_thread"] = threading.current_thread()
                    announcer_thread = threading.Thread(
                        name="announcer_thread",
                        target=announcer_worker,
                        kwargs={
                            "host": host,
                            "port": port,
                            "working_replies": self.working_replies,
                            "working_replies_lock": self.working_replies_lock,
                        },
                    )
                    announcer_thread.daemon = False
                    announcer_thread.start()
                    self.announcer_thread_running = True

        def on_message(client, userdata, msg):
            logger.debug(
                "Msg recieved. (client='%s', userdata='%s', topic='%s', payload='%s')",
                client,
                userdata,
                msg.topic,
                msg.payload,
            )

            try:
                parsed = json.loads(msg.payload)
            except ValueError:
                logger.warning("Payload is not a JSON (msg.payload='%s')", msg.payload)
                return  # message in wrong format

            if "reply_msg_id" not in parsed:
                logger.warning("Missing mandatory reply_msg_id (data='%s')", parsed)
                return  # missing reply msg_id
            reply_topic = (
                f"foris-controller/{app_info['controller_id']}/reply/{parsed['reply_msg_id']}"
            )

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

            match = re.match(r"^foris-controller/[^/]+/working_replies$", msg.topic)
            if match:
                response = self.list_working_replies()

            match = re.match(r"^foris-controller/[^/]+/request/([^/]+)/action/([^/]+)$", msg.topic)
            if match:
                module_name, action_name = match.group(1, 2)
                msg = {"module": module_name, "kind": "request", "action": action_name}
                if "data" in parsed:
                    msg["data"] = parsed["data"]
                self.start_message_worker(reply_topic, parsed["reply_msg_id"], msg)
                return  # reply will be performed elsewhere

            if response is not None:
                raw_response = json.dumps(response)
                mqtt_message = client.publish(reply_topic, raw_response, qos=0, retain=True)
                logger.debug(
                    "Publishing message (mid=%s) for %s: %s",
                    mqtt_message.mid,
                    reply_topic,
                    response,
                )

            else:
                # This should not happen
                logger.error("Don't know how to respond.")

        self.client = mqtt.Client(client_id=self.mqtt_client_id, clean_session=False)
        self.client.on_connect = MqttListener.handle_on_connect
        self.client.on_message = on_message
        self.client.on_subscribe = on_subscribe
        self.client.on_publish = on_publish
        if app_info["mqtt_credentials"]:
            self.client.username_pw_set(*app_info["mqtt_credentials"])
        self.client.connect(host, port, keepalive=30)

    def serve_forever(self):
        self.client.loop_forever()


class MqttNotificationSender(BaseNotificationSender):
    def _connect(self):
        self._force_stop = False

        def on_connect(client, userdata, flags, rc):
            self._connected = True
            if rc != 0:
                logger.error("Failed to connect to the message bus (rc=%d).", rc)
                sys.exit(1)  # can't connect to bus -> exitting

            logger.debug(
                "Notification sender connected to mqtt server. "
                "(client='%s', userdata='%s', flags='%s', rc='%s')",
                client,
                userdata,
                flags,
                rc,
            )

        def on_disconnect(client, userdata, rc):
            logger.debug("Notification sender disconnected (rc=%d).", rc)
            self._connected = False
            if not self._force_stop:
                client.reconnect()

        def on_publish(client, userdata, mid):
            logger.debug("Notification inserted into publish queue (mid=%s)", mid)

        self.client = mqtt.Client(client_id=self.mqtt_client_id, clean_session=False)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_publish = on_publish
        if self.credentials:
            self.client.username_pw_set(*self.credentials)
        self.client.connect(self.host, self.port, keepalive=30)

    def __init__(self, host, port, credentials):
        logger.debug("Connecting to mqtt server.")

        self.host = host
        self.port = port
        self.credentials = credentials
        self.mqtt_client_id = f"{uuid.uuid4()}-controller-notification"

        self._connect()
        self._connected = True

    def _send_message(self, msg, controller_id, module, action, data=None):
        logger.debug(
            "Sending notificaton (controller_id='%s', module='%s', action='%s', data='%s')"
            % (controller_id, module, action, data)
        )
        if not self._connected:
            self._connect()

        publish_topic = "foris-controller/%s/notification/%s/action/%s" % (
            controller_id,
            module,
            action,
        )
        res = self.client.publish(publish_topic, json.dumps(msg), qos=0)

        for _ in range(3):  # retry to resend
            if res.rc == mqtt.MQTT_ERR_SUCCESS:
                break
            res = self.client.publish(publish_topic, json.dumps(msg), qos=0)

        logger.debug(
            "Notification published. (topic=%s, mid=%d, msg=%s)", publish_topic, res.mid, msg
        )

    def disconnect(self):
        if self._connected:
            logger.debug("Disconnecting mqtt")
            self.client.disconnect()
            self._force_stop = True

    def reset(self):
        logger.debug("Resetting connection (skipped no need to reset this bus).")
