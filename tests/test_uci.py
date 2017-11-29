#
# foris-controller
# Copyright (C) 2017 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

import pytest
import subprocess
import re

from collections import OrderedDict

from foris_controller.exceptions import UciException, UciTypeException, UciRecordNotFound

from .fixtures import lock_backend, uci_config_dir


def get_uci_module(lock_backend):
    from foris_controller.app import app_info
    app_info["lock_backend"] = lock_backend
    from foris_controller_backends import uci
    return uci


def show(config_dir):
    process = subprocess.Popen(["uci", "-c", config_dir, "show"], stdout=subprocess.PIPE)
    stdout, _ = process.communicate()
    return stdout


def test_init(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    with backend_class(uci_config_dir):
        pass


def test_add_named_section(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.named1=named" in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        res1 = backend.add_section("test1", "test_section", "named1")
        res2 = backend.add_section("test2", "named", "named1")

    assert res1 is None
    assert res2 is None
    assert "test1.named1=test_section" in show(uci_config_dir)
    assert "test2.named1=named" in show(uci_config_dir)


def test_add_anonymous_section(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    with backend_class(uci_config_dir) as backend:
        name = backend.add_section("test1", "test_section")

    name = name.strip()
    assert re.search(r"^cfg[0-9a-f]{6}$", name)

    assert "test1.@test_section[0]=test_section" in show(uci_config_dir)


def test_del_named_section(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.named2=named" in show(uci_config_dir)
    assert "test2.named3=named" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.del_section("test2", "named2")
        with pytest.raises(UciException):
            backend.del_section("test2", "named3")

    assert "test2.named2=named" not in show(uci_config_dir)
    assert "test2.named3=named" not in show(uci_config_dir)


def test_del_anonymous_section(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1]=anonymous" in show(uci_config_dir)
    assert "test2.@anonymous[2]=anonymous" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        with pytest.raises(UciException):
            backend.del_section("test2", "@anonymous[2]")
        backend.del_section("test2", "@anonymous[1]")

    assert "test2.@anonymous[1]=anonymous" not in show(uci_config_dir)
    assert "test2.@anonymous[2]=anonymous" not in show(uci_config_dir)


def test_set_option(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1]=anonymous" in show(uci_config_dir)
    assert "test2.named2=named" in show(uci_config_dir)
    assert "test2.@anonymous[1].option1='aeb bb'" in show(uci_config_dir)
    assert "test2.named2.option1='aeb bb'" in show(uci_config_dir)
    assert "test2.named3.option1='non-existing'" not in show(uci_config_dir)
    assert "non_existing.named3.option1='non-existing'" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.set_option("test2", "@anonymous[1]", "new_option", "val 1")
        backend.set_option("test2", "named2", "new_option", "val 2")
        backend.set_option("test2", "@anonymous[1]", "option1", "val 1")
        backend.set_option("test2", "named2", "option1", "val 2")
        with pytest.raises(UciException):
            backend.set_option("test2", "named3", "option1", "non-existing")
        with pytest.raises(UciException):
            backend.set_option("non_existing", "named3", "option1", "non-existing")

    assert "test2.@anonymous[1].new_option='val 1'" in show(uci_config_dir)
    assert "test2.named2.new_option='val 2'" in show(uci_config_dir)
    assert "test2.@anonymous[1].option1='val 1'" in show(uci_config_dir)
    assert "test2.named2.option1='val 2'" in show(uci_config_dir)
    assert "test2.named3.option1='non-existing'" not in show(uci_config_dir)
    assert "non_existing.named3.option1='non-existing'" not in show(uci_config_dir)


def test_del_option(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1].option2='xxx'" in show(uci_config_dir)
    assert "test2.named2.option2='xxx'" in show(uci_config_dir)
    assert "test2.named3.option2='xxx'" not in show(uci_config_dir)
    assert "non_existing.named3.option2='xxx'" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.del_option("test2", "@anonymous[1]", "option2")
        backend.del_option("test2", "named2", "option2")
        with pytest.raises(UciException):
            backend.del_option("test2", "named3", "option2")
        with pytest.raises(UciException):
            backend.del_option("non_existing", "named3", "option2")

    assert "test2.@anonymous[1].option2='xxx'" not in show(uci_config_dir)
    assert "test2.named2.option2='xxx'" not in show(uci_config_dir)
    assert "test2.named3.option2='xxx'" not in show(uci_config_dir)
    assert "non_existing.named3.option2='xxx'" not in show(uci_config_dir)


def test_add_to_list(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[0].new_list" not in show(uci_config_dir)
    assert "test2.named1.new_list" not in show(uci_config_dir)
    assert "test2.@anonymous[1].list1='single item'" in show(uci_config_dir)
    assert "test2.named2.list1='single item'" in show(uci_config_dir)
    assert "test2.named3.list1='non' 'existing'" not in show(uci_config_dir)
    assert "non_existing.named3.list1='existing' 'non'" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.add_to_list("test2", "@anonymous[0]", "new_list", ["1 2", "3 4", "5 6"])
        backend.add_to_list("test2", "named1", "new_list", ["2 1", "4 3", "6 5"])
        backend.add_to_list("test2", "@anonymous[1]", "list1", ["3 4", "5 6"])
        backend.add_to_list("test2", "named2", "list1", ["4 3", "6 5"])
        with pytest.raises(UciException):
            backend.add_to_list("test2", "named3", "list1", ["non", "existing"])
        with pytest.raises(UciException):
            backend.add_to_list("non_existing", "named3", "list1", ["existing", "non"])

    assert "test2.@anonymous[0].new_list='1 2' '3 4' '5 6'" in show(uci_config_dir)
    assert "test2.named1.new_list='2 1' '4 3' '6 5'" in show(uci_config_dir)
    assert "test2.@anonymous[1].list1='single item' '3 4' '5 6'" in show(uci_config_dir)
    assert "test2.named2.list1='single item' '4 3' '6 5'" in show(uci_config_dir)
    assert "test2.named3.list1='non' 'existing'" not in show(uci_config_dir)
    assert "non_existing.named3.list1='existing' 'non'" not in show(uci_config_dir)


def test_del_from_list(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1].list1='single item'" in show(uci_config_dir)
    assert "test2.named2.list2='item 1' 'item 2' 'item 3' 'item 4'" in show(uci_config_dir)
    assert "test2.named2.list3='itema' 'itemb'" in show(uci_config_dir)
    assert "test2.named2.non_existing" not in show(uci_config_dir)
    assert "test2.non_existing.non_existing" not in show(uci_config_dir)
    assert "non_existing.non_existing.non_existing" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.del_from_list("test2", "@anonymous[1]", "list1", ["single item"])
        backend.del_from_list("test2", "named2", "list2", ["item 2", "item 4", "item 6"])
        backend.del_from_list("test2", "named2", "list3")
        with pytest.raises(UciException):
            backend.del_from_list("test2", "named2", "non_existing")
        with pytest.raises(UciException):
            backend.del_from_list("test2", "non_existing", "non_existing")
        with pytest.raises(UciException):
            backend.del_from_list("non_existing", "non_existing", "non_existing")

    assert "test2.@anonymous[1].list1" not in show(uci_config_dir)
    assert "test2.named2.list2='item 1' 'item 3'" in show(uci_config_dir)
    assert "test2.named2.list3" not in show(uci_config_dir)
    assert "test2.named2.non_existing" not in show(uci_config_dir)
    assert "test2.non_existing.non_existing" not in show(uci_config_dir)
    assert "non_existing.non_existing.non_existing" not in show(uci_config_dir)


def test_replace_list(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1].list1='single item'" in show(uci_config_dir)
    assert "test2.named2.list1='single item'" in show(uci_config_dir)
    assert "test2.named2.list2='item 1' 'item 2' 'item 3' 'item 4'" in show(uci_config_dir)
    assert "test2.named2.non_existing" not in show(uci_config_dir)
    assert "test2.named2.new_list" not in show(uci_config_dir)
    assert "test2.non_existing.non_existing" not in show(uci_config_dir)
    assert "non_existing.non_existing.non_existing" not in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.replace_list("test2", "@anonymous[1]", "list1", ["my items", "are", "brand new"])
        backend.replace_list("test2", "named2", "list2", ["item 2", "item 3", "item 5"])
        backend.replace_list("test2", "named2", "list1", [])
        backend.replace_list("test2", "named2", "non_existing", [])
        backend.replace_list("test2", "named2", "new_list", ["new 1", "new 2", "new 3"])
        with pytest.raises(UciException):
            backend.replace_list("test2", "non_existing", "new_list", ["new 2", "new 3"])
        with pytest.raises(UciException):
            backend.replace_list("non_existing", "non_existing", "new_list", ["new 3"])

    assert "test2.@anonymous[1].list1='my items' 'are' 'brand new'" in show(uci_config_dir)
    assert "test2.named2.list2='item 2' 'item 3' 'item 5'" in show(uci_config_dir)
    assert "test2.named2.list1" not in show(uci_config_dir)
    assert "test2.named2.non_existing2" not in show(uci_config_dir)
    assert "test2.named2.new_list='new 1' 'new 2' 'new 3'" in show(uci_config_dir)


def test_replace_session(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    assert "test2.@anonymous[1]=anonymous" in show(uci_config_dir)
    assert "test2.@anonymous[1].list1" in show(uci_config_dir)
    assert "test2.named2=named" in show(uci_config_dir)
    assert "test2.named2.list1" in show(uci_config_dir)

    with backend_class(uci_config_dir) as backend:
        backend.del_section("test2", "named2")
        backend.add_section("test2", "named", "named2")
        backend.set_option("test2", "named2", "new_option", "value1")
        backend.add_to_list("test2", "named2", "new_list", ["val1", "val2", "val3"])

        backend.del_section("test2", "@anonymous[1]")
        a_name = backend.add_section("test2", "anonymous").strip()
        backend.set_option("test2", a_name, "new_option", "valuea")
        backend.add_to_list("test2", a_name, "new_list", ["vala", "valb", "valc"])

    assert "test2.@anonymous[1].list1" not in show(uci_config_dir)
    assert "test2.named2.list1" not in show(uci_config_dir)
    assert "test2.named2=named" in show(uci_config_dir)
    assert "test2.named2.new_option='value1'" in show(uci_config_dir)
    assert "test2.named2.new_list='val1' 'val2' 'val3'" in show(uci_config_dir)
    assert "test2.@anonymous[1]=anonymous" in show(uci_config_dir)
    assert "test2.@anonymous[1].new_option='valuea'" in show(uci_config_dir)
    assert "test2.@anonymous[1].new_list='vala' 'valb' 'valc'" in show(uci_config_dir)


def test_read(lock_backend, uci_config_dir):
    backend_class = get_uci_module(lock_backend).UciBackend

    with backend_class(uci_config_dir) as backend:
        res1 = backend.read('test1')
        res2 = backend.read('test2')
        res3 = backend.read()
        with pytest.raises(UciException):
            backend.read('non-existing')

    assert res1 == {"test1": []}
    assert res2 == {
        'test2': [
            {'data': OrderedDict(), 'type': 'anonymous', 'name': None},
            {
                'data': OrderedDict([
                    ('option1', 'aeb bb'),
                    ('option2', 'xxx'),
                    ('list1', ['single item']),
                    ('list2', ['item 1', 'item 2', 'item 3', 'item 4']),
                    ('list3', ['itema', 'itemb']),
                ]),
                'type': 'anonymous', 'name': None
            },
            {'data': OrderedDict(), 'type': 'named', 'name': 'named1'},
            {
                'data': OrderedDict([
                    ('option1', 'aeb bb'),
                    ('option2', 'xxx'),
                    ('list1', ['single item']),
                    ('list2', ['item 1', 'item 2', 'item 3', 'item 4']),
                    ('list3', ['itema', 'itemb']),
                ]),
                'type': 'named', 'name': 'named2'
            }
        ]
    }
    assert res3 == {
        'test1': [],
        'test2': [
            {'data': OrderedDict(), 'type': 'anonymous', 'name': None},
            {
                'data': OrderedDict([
                    ('option1', 'aeb bb'),
                    ('option2', 'xxx'),
                    ('list1', ['single item']),
                    ('list2', ['item 1', 'item 2', 'item 3', 'item 4']),
                    ('list3', ['itema', 'itemb']),
                ]),
                'type': 'anonymous', 'name': None
            },
            {'data': OrderedDict(), 'type': 'named', 'name': 'named1'},
            {
                'data': OrderedDict([
                    ('option1', 'aeb bb'),
                    ('option2', 'xxx'),
                    ('list1', ['single item']),
                    ('list2', ['item 1', 'item 2', 'item 3', 'item 4']),
                    ('list3', ['itema', 'itemb']),
                ]),
                'type': 'named', 'name': 'named2'
            }
        ]
    }


def test_bool(lock_backend, uci_config_dir):
    TRUE = ["1", "on", "true", "yes", "enabled"]
    FALSE = ["0", "off", "false", "no", "disabled"]
    uci = get_uci_module(lock_backend)
    for value in TRUE:
        assert True is uci.parse_bool(value)
    for value in FALSE:
        assert False is uci.parse_bool(value)

    for value in ("", "adf", "ON", "OFF"):
        with pytest.raises(UciTypeException):
            uci.parse_bool(value)

    for value in TRUE + FALSE:
        uci.store_bool(value) == value

    assert uci.store_bool(True) == "1"
    assert uci.store_bool(False) == "0"


def test_parse_read_data(lock_backend, uci_config_dir):
    uci = get_uci_module(lock_backend)

    backend_class = get_uci_module(lock_backend).UciBackend
    with backend_class(uci_config_dir) as backend:
        res1 = backend.read('test1')
        res2 = backend.read('test2')

    assert uci.get_config(res1, 'test1') == []
    assert uci.get_section(res2, 'test2', 'named1') == {'data': OrderedDict(), 'type': 'named', 'name': 'named1'}
    assert uci.get_option_named(res2, 'test2', 'named2', 'option2') == 'xxx'
    assert uci.get_sections_by_type(res2, 'test2', 'anonymous') == [
        {'data': OrderedDict(), 'type': 'anonymous', 'name': None},
        {
            'data': OrderedDict([
                ('option1', 'aeb bb'),
                ('option2', 'xxx'),
                ('list1', ['single item']),
                ('list2', ['item 1', 'item 2', 'item 3', 'item 4']),
                ('list3', ['itema', 'itemb']),
            ]),
            'type': 'anonymous', 'name': None
        },
    ]
    assert uci.get_section_idx(res2, 'test2', 'anonymous', 0) == {'data': OrderedDict(), 'type': 'anonymous', 'name': None}
    assert uci.get_option_anonymous(res2, 'test2', 'anonymous', 1, 'option2') == 'xxx'

    with pytest.raises(UciRecordNotFound):
        uci.get_config(res1, 'non_existing')
    with pytest.raises(UciRecordNotFound):
        uci.get_section(res2, 'test2', 'non_existing')
    with pytest.raises(UciRecordNotFound):
        uci.get_option_named(res2, 'test2', 'named2', 'non_existing')
    assert "def1" == uci.get_option_named(res2, 'test2', 'named2', 'non_existing', default="def1")
    with pytest.raises(UciRecordNotFound):
        uci.get_sections_by_type(res2, 'test2', 'non_existing')
    with pytest.raises(UciRecordNotFound):
        uci.get_section_idx(res2, 'test2', 'anonymous', 99)
    with pytest.raises(UciRecordNotFound):
        uci.get_option_anonymous(res2, 'test2', 'anonymous', 1, 'non_existing')
    assert "def2" == uci.get_option_anonymous(
        res2, 'test2', 'anonymous', 1, 'non_existing', default="def2")
