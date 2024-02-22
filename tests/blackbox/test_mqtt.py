#
# foris-controller
# Copyright (C) 2020 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import collections
import json
import pytest
import uuid


from paho import mqtt as mqtt_module
from paho.mqtt import client as mqtt

from foris_controller_testtools.infrastructure import MQTT_ID, MQTT_PORT, MQTT_HOST

from foris_controller import __version__


def query_bus(topic):
    result = {"data": None}

    msg_id = uuid.uuid1()
    reply_topic = "foris-controller/%s/reply/%s" % (MQTT_ID, msg_id)

    def on_connect(client, userdata, flags, rc):
        client.subscribe(reply_topic)

    def on_subscribe(client, userdata, mid, granted_qos):
        client.publish(topic, json.dumps({"reply_msg_id": str(msg_id)}))

    def on_message(client, userdata, msg):
        try:
            parsed = json.loads(msg.payload)
        except Exception:
            return
        result["data"] = parsed
        client.loop_stop()
        client.disconnect()

    if mqtt_module.__version__.split(".")[0] not in ["1", "0"]:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()

    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_connect = on_connect
    client.connect(MQTT_HOST, MQTT_PORT, 30)
    client.loop_start()
    client._thread.join(3)

    return result["data"]


@pytest.mark.only_message_buses(["mqtt"])
def test_advertize(infrastructure, file_root_init, mount_on_normal):

    filters = [("remote", "advertize")]
    notifications = infrastructure.get_notifications(filters=filters)

    # wait for at least 3 new notifications
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    notifications = infrastructure.get_notifications(notifications, filters=filters)

    # test format
    for notification in notifications:
        assert notification.keys() == {"module", "action", "kind", "data"}
        assert notification["module"] == "remote"
        assert notification["action"] == "advertize"
        assert notification["kind"] == "notification"
        assert notification["data"]["state"] in ["running", "started", "exited"]
        assert notification["data"]["id"] == MQTT_ID
        assert "hostname" in notification["data"]
        assert notification["data"]["netboot"] == "no"
        assert isinstance(notification["data"]["working_replies"], list)
        assert {"name": "remote", "version": __version__ in notification["data"]["modules"]}


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.only_message_buses(["mqtt"])
def test_advertize_netboot_booted(infrastructure, file_root_init, mount_on_netboot):

    filters = [("remote", "advertize")]
    notifications = infrastructure.get_notifications(filters=filters)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1]["data"]["netboot"] == "booted"


@pytest.mark.only_backends(["openwrt"])
@pytest.mark.only_message_buses(["mqtt"])
def test_advertize_netboot_ready(
    infrastructure, file_root_init, mount_on_netboot, netboot_configured
):

    filters = [("remote", "advertize")]
    notifications = infrastructure.get_notifications(filters=filters)
    notifications = infrastructure.get_notifications(notifications, filters=filters)
    assert notifications[-1]["data"]["netboot"] == "ready"


@pytest.mark.only_message_buses(["mqtt"])
def test_modules_list(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/list" % MQTT_ID
    modules = query_bus(topic)
    assert len(modules) > 0
    assert all([set(e.keys()) == {"name", "actions"} for e in modules])
    assert all([isinstance(e["name"], str) for e in modules])
    assert all([isinstance(e["actions"], collections.abc.Iterable) for e in modules])


@pytest.mark.only_message_buses(["mqtt"])
def test_schema(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/jsonschemas" % MQTT_ID
    schemas = query_bus(topic)
    assert len(schemas) > 1


@pytest.mark.only_message_buses(["mqtt"])
def test_action_list(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/list" % MQTT_ID
    modules = [e["name"] for e in query_bus(topic)]
    for module in modules:
        topic = "foris-controller/%s/request/%s/list" % (MQTT_ID, module)
        actions = query_bus(topic)
        assert len(actions) > 0


@pytest.mark.only_message_buses(["mqtt"])
def test_working_replies(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/working_replies" % MQTT_ID
    assert isinstance(query_bus(topic), list)


@pytest.mark.only_message_buses(["mqtt"])
def test_wrong_id(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()

    # timeouts
    res = query_bus("foris-controller/invalid_id/list")
    assert res is None
    res = query_bus("foris-controller/invalid_id/schema")
    assert res is None
    res = query_bus("foris-controller/invalid_id/request/about/list")
    assert res is None


@pytest.mark.only_message_buses(["mqtt"])
def test_wrong_module_id(infrastructure, file_root_init):
    infrastructure.wait_mqtt_connected()
    # should fail instantly

    res = query_bus("foris-controller/%s/request/%s/list" % (MQTT_ID, "non-existing"))
    assert res == []
