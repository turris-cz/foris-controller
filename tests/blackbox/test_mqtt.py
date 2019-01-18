#
# foris-controller
# Copyright (C) 2019 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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
import jsonschema


from paho.mqtt import client as mqtt

from foris_controller_testtools.infrastructure import MQTT_ID, MQTT_PORT, MQTT_HOST

from foris_controller_testtools.fixtures import (
    only_message_buses, infrastructure, file_root_init, mosquitto_test, ubusd_test
)


def query_bus(topic):
        result = {"data": None}

        msg_id = uuid.uuid1()
        reply_topic = "foris-controller/%s/reply/%s" % (MQTT_ID, msg_id)

        def on_connect(client, userdata, flags, rc):
            client.subscribe(reply_topic)

        def on_subscribe(client, userdata, mid, granted_qos):
            client.publish(topic, json.dumps({"reply_topic": reply_topic}))

        def on_message(client, userdata, msg):
            try:
                parsed = json.loads(msg.payload)
            except Exception:
                return
            result["data"] = parsed
            client.loop_stop(True)
            client.disconnect()

        client = mqtt.Client()
        client.on_subscribe = on_subscribe
        client.on_message = on_message
        client.on_connect = on_connect
        client.connect(MQTT_HOST, MQTT_PORT, 30)
        client.loop_start()
        client._thread.join(3)

        return result["data"]


@pytest.mark.only_message_buses(['mqtt'])
def test_announcements(ubusd_test, infrastructure, file_root_init, mosquitto_test):

    data = dict(required_count=3)

    def on_connect(client, userdata, flags, rc):
        client.subscribe(f"foris-controller/{MQTT_ID}/notification/remote/action/advertize")

    def on_message(client, userdata, msg):
        try:
            parsed = json.loads(msg.payload)
            assert parsed["id"] == MQTT_ID
            if parsed["state"] in ["started", "running"]:
                data["required_count"] -= 1
                if data["required_count"] < 0:
                    client.loop_stop(True)
        except Exception:
            pass

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 30)
    client.loop_start()
    client._thread.join(10)


@pytest.mark.only_message_buses(['mqtt'])
def test_modules_list(ubusd_test, infrastructure, file_root_init, mosquitto_test):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/list" % MQTT_ID
    modules = query_bus(topic)
    assert len(modules) > 0
    assert all([set(e.keys()) == {"name", "actions"} for e in modules])
    assert all([isinstance(e['name'], str) for e in modules])
    assert all([isinstance(e['actions'], collections.Iterable) for e in modules])


@pytest.mark.only_message_buses(['mqtt'])
def test_schema(ubusd_test, infrastructure, file_root_init, mosquitto_test):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/jsonschemas" % MQTT_ID
    schemas = query_bus(topic)
    assert len(schemas) > 1


@pytest.mark.only_message_buses(['mqtt'])
def test_action_list(ubusd_test, infrastructure, file_root_init, mosquitto_test):
    infrastructure.wait_mqtt_connected()
    topic = "foris-controller/%s/list" % MQTT_ID
    modules = [e["name"] for e in query_bus(topic)]
    for module in modules:
        topic = "foris-controller/%s/request/%s/list" % (MQTT_ID, module)
        actions = query_bus(topic)
        assert len(actions) > 0


@pytest.mark.only_message_buses(['mqtt'])
def test_wrong_id(ubusd_test, infrastructure, file_root_init, mosquitto_test):
    infrastructure.wait_mqtt_connected()

    # timeouts
    res = query_bus("foris-controller/invalid_id/list")
    assert res is None
    res = query_bus("foris-controller/invalid_id/schema")
    assert res is None
    res = query_bus("foris-controller/invalid_id/request/about/list")
    assert res is None


@pytest.mark.only_message_buses(['mqtt'])
def test_wrong_module_id(ubusd_test, infrastructure, file_root_init, mosquitto_test):
    infrastructure.wait_mqtt_connected()
    # should fail instantly

    res = query_bus("foris-controller/%s/request/%s/list" % (MQTT_ID, "non-existing"))
    assert res == []
