Foris controller
================
An program which is placed in top of a message bus and translates requests to commands for backends.

Requirements
============

* python3
* foris-schema

Installation
============

..  code-block::

    pip install .

Usage
=====
To run foris-controller using unix-socket and mock-backend (debugging purposes)::


	foris-controller --backend mock unix-socket


To run foris-controller using ubus and openwrt-backend::

	foris-controller --backend openwrt ubus

You can also send notifications via contiguration backend back to listening clients::

	foris-notify -m web -a set_language ubus {"language": "en"}

or::

	foris-notify -m web -a set_language unix-socket {"language": "en"}

Running tests
=============

..  code-block::

    git submodule update --init
    tox -q -e py39


Pre-commit configuration
========================

..  code-block::

    pip install .[dev]
    pre-commit install -t pre-push
    pre-commit install -t pre-commit  # optional
